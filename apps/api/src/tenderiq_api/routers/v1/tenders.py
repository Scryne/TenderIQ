"""/api/v1/tenders — ihale projeleri, doküman yükleme ve SSE canlı durum."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tenderiq_api.dependencies import (
    PrincipalDep,
    StorageDep,
    TenantSessionDep,
    require_role,
)
from tenderiq_api.errors import ConflictError, NotFoundError, ValidationFailedError
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.findings import (
    ComplianceStatus,
    DeliverableKind,
    GroundingResolution,
    RequirementKind,
    ReviewStatus,
    RiskCategory,
    RiskSeverity,
    TimelineKind,
)
from tenderiq_core.models import (
    AuditAction,
    ComplianceResult,
    Deliverable,
    Document,
    DocumentKind,
    DocumentStatus,
    Job,
    ParsedElement,
    Requirement,
    RiskFlag,
    Role,
    Tender,
    TenderStatus,
    TimelineEvent,
)
from tenderiq_core.services.audit import record_audit
from tenderiq_core.storage import safe_key_component
from tenderiq_core.uploads import is_allowed_content_type

router = APIRouter(prefix="/tenders", tags=["tenders"])

# Yazma işlemleri admin/üye gerektirir; izleyici yalnızca okuyabilir.
_writer = Depends(require_role(Role.ADMIN, Role.MEMBER))

# SSE: DB poll aralığı, heartbeat periyodu ve akış ömrü tavanı (poll tık sayısı).
_SSE_POLL_SECONDS = 1.0
_SSE_HEARTBEAT_TICKS = 15
_SSE_MAX_TICKS = 900  # ~15 dk; EventSource şeffaf yeniden bağlanır


class TenderCreate(BaseModel):
    """Yeni ihale projesi."""

    title: str = Field(min_length=1, max_length=500)


class TenderResponse(BaseModel):
    """İhale özeti."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: TenderStatus
    created_by: uuid.UUID | None


class DocumentCreate(BaseModel):
    """Yeni doküman kaydı (imzalı yükleme URL'i döner)."""

    filename: str = Field(min_length=1, max_length=1024)
    content_type: str = Field(min_length=1, max_length=255)
    kind: DocumentKind = DocumentKind.OTHER


class DocumentResponse(BaseModel):
    """Doküman özeti."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_id: uuid.UUID
    filename: str
    content_type: str
    kind: DocumentKind
    status: DocumentStatus
    size_bytes: int | None


class DocumentUploadResponse(BaseModel):
    """Doküman kaydı + süre-sınırlı imzalı yükleme URL'i."""

    document: DocumentResponse
    upload_url: str
    storage_key: str


class FindingSource(BaseModel):
    """Bulgunun kaynak konumu — citation zinciri: öğe → sayfa + bbox (§6.9).

    Kaynağa bağlanamayan bulgu API'den hiç dönmediği için (ADR-0006) tüm
    alanlar kaynak öğeden doludur; bbox yalnız konumsuz formatlarda (DOCX/XLSX)
    boştur.
    """

    element_id: uuid.UUID
    element_seq: int
    page: int
    section: str | None
    bbox_x0: float | None
    bbox_y0: float | None
    bbox_x1: float | None
    bbox_y1: float | None
    quote: str
    resolution: GroundingResolution


class FindingReview(BaseModel):
    """Bulgunun insan-döngüde inceleme durumu (Sprint 3.2, §4.3)."""

    status: ReviewStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None


class RequirementResponse(BaseModel):
    """Çıkarılmış gereksinim (kaynaklı)."""

    id: uuid.UUID
    document_id: uuid.UUID
    text: str
    kind: RequirementKind
    is_mandatory: bool
    source: FindingSource
    review: FindingReview


class DeliverableResponse(BaseModel):
    """Çıkarılmış istenen belge (kaynaklı)."""

    id: uuid.UUID
    document_id: uuid.UUID
    name: str
    kind: DeliverableKind
    is_mandatory: bool
    source: FindingSource
    review: FindingReview


class RiskResponse(BaseModel):
    """Çıkarılmış risk maddesi (kaynaklı)."""

    id: uuid.UUID
    document_id: uuid.UUID
    text: str
    severity: RiskSeverity
    category: RiskCategory
    source: FindingSource
    review: FindingReview


class TimelineEventResponse(BaseModel):
    """Çıkarılmış tarih/süre öğesi (kaynaklı)."""

    id: uuid.UUID
    document_id: uuid.UUID
    label: str
    kind: TimelineKind
    value_text: str
    source: FindingSource
    review: FindingReview


class ComplianceResultResponse(BaseModel):
    """Gereksinim ↔ yetkinlik profili değerlendirmesi (kaynaklı)."""

    id: uuid.UUID
    document_id: uuid.UUID
    requirement_text: str
    status: ComplianceStatus
    rationale: str
    source: FindingSource
    review: FindingReview


def _finding_source(
    element: ParsedElement, *, quote: str, resolution: GroundingResolution
) -> FindingSource:
    return FindingSource(
        element_id=element.id,
        element_seq=element.seq,
        page=element.page,
        section=element.section,
        bbox_x0=element.bbox_x0,
        bbox_y0=element.bbox_y0,
        bbox_x1=element.bbox_x1,
        bbox_y1=element.bbox_y1,
        quote=quote,
        resolution=resolution,
    )


def _finding_review(row: Any) -> FindingReview:
    """ReviewMixin kolonlarından inceleme özeti üretir (beş bulgu modelinde ortak)."""
    return FindingReview(
        status=row.review_status,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
    )


# Satır → yanıt kurucuları: liste uçları ve bulgu inceleme uçları (routers.v1.findings)
# aynı yanıt şeklini paylaşır — tek kaynaktan kurulur.


def requirement_response(row: Requirement, element: ParsedElement) -> RequirementResponse:
    return RequirementResponse(
        id=row.id,
        document_id=row.document_id,
        text=row.text,
        kind=row.kind,
        is_mandatory=row.is_mandatory,
        source=_finding_source(
            element, quote=row.source_quote, resolution=row.grounding_resolution
        ),
        review=_finding_review(row),
    )


def deliverable_response(row: Deliverable, element: ParsedElement) -> DeliverableResponse:
    return DeliverableResponse(
        id=row.id,
        document_id=row.document_id,
        name=row.name,
        kind=row.kind,
        is_mandatory=row.is_mandatory,
        source=_finding_source(
            element, quote=row.source_quote, resolution=row.grounding_resolution
        ),
        review=_finding_review(row),
    )


def risk_response(row: RiskFlag, element: ParsedElement) -> RiskResponse:
    return RiskResponse(
        id=row.id,
        document_id=row.document_id,
        text=row.text,
        severity=row.severity,
        category=row.category,
        source=_finding_source(
            element, quote=row.source_quote, resolution=row.grounding_resolution
        ),
        review=_finding_review(row),
    )


def timeline_event_response(row: TimelineEvent, element: ParsedElement) -> TimelineEventResponse:
    return TimelineEventResponse(
        id=row.id,
        document_id=row.document_id,
        label=row.label,
        kind=row.kind,
        value_text=row.value_text,
        source=_finding_source(
            element, quote=row.source_quote, resolution=row.grounding_resolution
        ),
        review=_finding_review(row),
    )


def compliance_result_response(
    row: ComplianceResult, element: ParsedElement
) -> ComplianceResultResponse:
    return ComplianceResultResponse(
        id=row.id,
        document_id=row.document_id,
        requirement_text=row.requirement_text,
        status=row.status,
        rationale=row.rationale,
        source=_finding_source(
            element, quote=row.source_quote, resolution=row.grounding_resolution
        ),
        review=_finding_review(row),
    )


@router.post(
    "", response_model=TenderResponse, status_code=status.HTTP_201_CREATED, dependencies=[_writer]
)
async def create_tender(
    body: TenderCreate, session: TenantSessionDep, principal: PrincipalDep
) -> TenderResponse:
    """Aktif kiracı için yeni bir ihale projesi oluşturur."""
    tender = Tender(
        id=uuid.uuid4(),
        tenant_id=principal.tenant_id,
        title=body.title,
        status=TenderStatus.DRAFT,
        created_by=principal.user_id,
    )
    session.add(tender)
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.TENDER_CREATED,
        resource_type="tender",
        resource_id=tender.id,
        actor_user_id=principal.user_id,
    )
    await session.flush()
    return TenderResponse.model_validate(tender)


@router.get("", response_model=list[TenderResponse])
async def list_tenders(session: TenantSessionDep) -> list[TenderResponse]:
    """Aktif kiracının ihalelerini listeler (RLS ile filtrelenir)."""
    result = await session.execute(select(Tender).order_by(Tender.created_at.desc()))
    return [TenderResponse.model_validate(t) for t in result.scalars().all()]


@router.get("/{tender_id}", response_model=TenderResponse)
async def get_tender(tender_id: uuid.UUID, session: TenantSessionDep) -> TenderResponse:
    """Tek bir ihaleyi döndürür (RLS: başka kiracınınki 404)."""
    tender = await session.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError("İhale bulunamadı.")
    return TenderResponse.model_validate(tender)


@router.post(
    "/{tender_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_writer],
)
async def create_document(
    tender_id: uuid.UUID,
    body: DocumentCreate,
    session: TenantSessionDep,
    principal: PrincipalDep,
    storage: StorageDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)] = None,
) -> DocumentUploadResponse:
    """Bir ihaleye doküman kaydı açar ve imzalı yükleme URL'i döndürür.

    ``Idempotency-Key`` başlığı verilirse aynı anahtarla tekrarlanan istek yeni
    kayıt açmaz; mevcut kaydı taze bir imzalı URL ile döndürür.
    """
    if not is_allowed_content_type(body.content_type):
        raise ValidationFailedError("Desteklenmeyen içerik türü. İzin verilenler: PDF, DOCX, XLSX.")

    tender = await session.get(Tender, tender_id)
    if tender is None:  # RLS: başka kiracının ihalesi de burada None döner
        raise NotFoundError("İhale bulunamadı.")

    if idempotency_key is not None:
        existing = await session.scalar(
            select(Document).where(Document.idempotency_key == idempotency_key)
        )
        if existing is not None:
            if existing.tender_id != tender_id:
                raise ConflictError("Bu Idempotency-Key başka bir kayıt için kullanılmış.")
            upload_url = storage.presigned_put_url(
                existing.storage_key, content_type=existing.content_type
            )
            return DocumentUploadResponse(
                document=DocumentResponse.model_validate(existing),
                upload_url=upload_url,
                storage_key=existing.storage_key,
            )

    document_id = uuid.uuid4()
    safe_filename = safe_key_component(body.filename)
    storage_key = f"{principal.tenant_id}/{tender_id}/{document_id}/{safe_filename}"
    document = Document(
        id=document_id,
        tenant_id=principal.tenant_id,
        tender_id=tender_id,
        filename=body.filename,
        content_type=body.content_type,
        storage_key=storage_key,
        kind=body.kind,
        status=DocumentStatus.PENDING_UPLOAD,
        idempotency_key=idempotency_key,
    )
    session.add(document)
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.DOCUMENT_CREATED,
        resource_type="document",
        resource_id=document_id,
        actor_user_id=principal.user_id,
        meta={"filename": body.filename, "content_type": body.content_type},
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        # Aynı Idempotency-Key ile eşzamanlı iki istek: ilk INSERT kazanır.
        raise ConflictError("Bu Idempotency-Key ile eşzamanlı bir istek işlendi.") from exc

    upload_url = storage.presigned_put_url(storage_key, content_type=body.content_type)
    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(document),
        upload_url=upload_url,
        storage_key=storage_key,
    )


@router.get("/{tender_id}/documents", response_model=list[DocumentResponse])
async def list_documents(tender_id: uuid.UUID, session: TenantSessionDep) -> list[DocumentResponse]:
    """Bir ihaleye bağlı dokümanları listeler."""
    result = await session.execute(
        select(Document).where(Document.tender_id == tender_id).order_by(Document.created_at.desc())
    )
    return [DocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.get("/{tender_id}/requirements", response_model=list[RequirementResponse])
async def list_requirements(
    tender_id: uuid.UUID, session: TenantSessionDep
) -> list[RequirementResponse]:
    """İhalenin çıkarılmış gereksinimlerini kaynaklarıyla listeler.

    Zorunlu grounding (ADR-0006): kaynak ``ParsedElement``e bağlanamayan bulgu
    bu uçtan DÖNMEZ — inner join kaynaksız satırı yapısal olarak dışarıda bırakır.
    """
    if await session.get(Tender, tender_id) is None:
        raise NotFoundError("İhale bulunamadı.")
    result = await session.execute(
        select(Requirement, ParsedElement)
        .join(ParsedElement, Requirement.source_element_id == ParsedElement.id)
        .where(Requirement.tender_id == tender_id)
        .order_by(Requirement.document_id, Requirement.seq)
    )
    return [requirement_response(row, element) for row, element in result.all()]


@router.get("/{tender_id}/deliverables", response_model=list[DeliverableResponse])
async def list_deliverables(
    tender_id: uuid.UUID, session: TenantSessionDep
) -> list[DeliverableResponse]:
    """İhalenin çıkarılmış istenen belgelerini kaynaklarıyla listeler.

    Grounding sözleşmesi ``list_requirements`` ile aynıdır (kaynaksız dönmez).
    """
    if await session.get(Tender, tender_id) is None:
        raise NotFoundError("İhale bulunamadı.")
    result = await session.execute(
        select(Deliverable, ParsedElement)
        .join(ParsedElement, Deliverable.source_element_id == ParsedElement.id)
        .where(Deliverable.tender_id == tender_id)
        .order_by(Deliverable.document_id, Deliverable.seq)
    )
    return [deliverable_response(row, element) for row, element in result.all()]


@router.get("/{tender_id}/risks", response_model=list[RiskResponse])
async def list_risks(tender_id: uuid.UUID, session: TenantSessionDep) -> list[RiskResponse]:
    """İhalenin çıkarılmış risk maddelerini kaynaklarıyla listeler.

    Grounding sözleşmesi ``list_requirements`` ile aynıdır (kaynaksız dönmez).
    """
    if await session.get(Tender, tender_id) is None:
        raise NotFoundError("İhale bulunamadı.")
    result = await session.execute(
        select(RiskFlag, ParsedElement)
        .join(ParsedElement, RiskFlag.source_element_id == ParsedElement.id)
        .where(RiskFlag.tender_id == tender_id)
        .order_by(RiskFlag.document_id, RiskFlag.seq)
    )
    return [risk_response(row, element) for row, element in result.all()]


@router.get("/{tender_id}/timeline", response_model=list[TimelineEventResponse])
async def list_timeline(
    tender_id: uuid.UUID, session: TenantSessionDep
) -> list[TimelineEventResponse]:
    """İhalenin çıkarılmış tarih/süre öğelerini kaynaklarıyla listeler.

    Grounding sözleşmesi ``list_requirements`` ile aynıdır (kaynaksız dönmez).
    """
    if await session.get(Tender, tender_id) is None:
        raise NotFoundError("İhale bulunamadı.")
    result = await session.execute(
        select(TimelineEvent, ParsedElement)
        .join(ParsedElement, TimelineEvent.source_element_id == ParsedElement.id)
        .where(TimelineEvent.tender_id == tender_id)
        .order_by(TimelineEvent.document_id, TimelineEvent.seq)
    )
    return [timeline_event_response(row, element) for row, element in result.all()]


@router.get("/{tender_id}/compliance", response_model=list[ComplianceResultResponse])
async def list_compliance(
    tender_id: uuid.UUID, session: TenantSessionDep
) -> list[ComplianceResultResponse]:
    """İhalenin gereksinim ↔ yetkinlik profili değerlendirmelerini listeler.

    Yalnız bir ``CapabilityProfile`` tanımlıysa üretilir. Grounding sözleşmesi
    ``list_requirements`` ile aynıdır: değerlendirme, değerlendirilen gereksinimin
    kaynak maddesine bağlıdır (kaynaksız dönmez).
    """
    if await session.get(Tender, tender_id) is None:
        raise NotFoundError("İhale bulunamadı.")
    result = await session.execute(
        select(ComplianceResult, ParsedElement)
        .join(ParsedElement, ComplianceResult.source_element_id == ParsedElement.id)
        .where(ComplianceResult.tender_id == tender_id)
        .order_by(ComplianceResult.document_id, ComplianceResult.seq)
    )
    return [compliance_result_response(row, element) for row, element in result.all()]


async def _tender_snapshot(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, tender_id: uuid.UUID
) -> dict[str, Any] | None:
    """SSE için ihale + doküman + son iş durumlarının anlık görüntüsü.

    Her tıkta kısa ömürlü ayrı bir transaction kullanılır; SSE bağlantısı boyunca
    açık transaction tutulmaz.
    """
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None
        documents = (
            (
                await session.execute(
                    select(Document)
                    .where(Document.tender_id == tender_id)
                    .order_by(Document.created_at)
                )
            )
            .scalars()
            .all()
        )
        document_ids = [d.id for d in documents]
        latest_job_by_document: dict[uuid.UUID, Job] = {}
        if document_ids:
            jobs = (
                (
                    await session.execute(
                        select(Job)
                        .where(Job.document_id.in_(document_ids))
                        .order_by(Job.created_at)
                    )
                )
                .scalars()
                .all()
            )
            for job in jobs:  # created_at artan sırada → sonuncu kazanır
                latest_job_by_document[job.document_id] = job
        return {
            "tender": {"id": str(tender.id), "status": tender.status.value},
            "documents": [
                {
                    "id": str(d.id),
                    "filename": d.filename,
                    "status": d.status.value,
                    "job": (
                        {
                            "id": str(latest_job.id),
                            "status": latest_job.status.value,
                            "attempts": latest_job.attempts,
                            "error_message": latest_job.error_message,
                        }
                        if (latest_job := latest_job_by_document.get(d.id)) is not None
                        else None
                    ),
                }
                for d in documents
            ],
        }


@router.get("/{tender_id}/stream", include_in_schema=False)
async def stream_tender_status(
    tender_id: uuid.UUID,
    request: Request,
    principal: PrincipalDep,
    max_ticks: Annotated[int, Query(ge=1, le=_SSE_MAX_TICKS)] = _SSE_MAX_TICKS,
) -> StreamingResponse:
    """SSE: ihalenin doküman/iş durumlarını canlı yayınlar.

    Durum değiştikçe ``status`` event'i, hareketsizlikte periyodik heartbeat
    yorumu gönderilir. İstemci koptuğunda döngü sonlanır; ayrıca akış en geç
    ``max_ticks`` poll turu sonunda sunucu tarafından kapatılır (EventSource
    şeffaf biçimde yeniden bağlanır) — sızan bağlantılar sınırsız yaşayamaz.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory

    async def _events() -> AsyncIterator[str]:
        last_payload: str | None = None
        idle_ticks = 0
        for _ in range(max_ticks):
            if await request.is_disconnected():
                return
            snapshot = await _tender_snapshot(factory, principal.tenant_id, tender_id)
            if snapshot is None:
                yield "event: not_found\ndata: {}\n\n"
                return
            payload = json.dumps(snapshot, ensure_ascii=False)
            if payload != last_payload:
                last_payload = payload
                idle_ticks = 0
                yield f"event: status\ndata: {payload}\n\n"
            else:
                idle_ticks += 1
                if idle_ticks >= _SSE_HEARTBEAT_TICKS:
                    idle_ticks = 0
                    yield ": keep-alive\n\n"
            await asyncio.sleep(_SSE_POLL_SECONDS)

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
