"""/api/v1/tenders/{id}/export — onaylı analizden Word/Excel rapor (Sprint 3.2, §4.1).

Rapora yalnız insan-onaylı bulgular girer (APPROVED + EDITED; istenirse
``include_pending`` ile onay bekleyenler de, "Onay bekliyor" etiketiyle).
REJECTED asla girmez. Kaynak referansları (doküman + sayfa no + bölüm + alıntı)
her satırda taşınır (citation-first, ADR-0006). Üretim API sürecinde senkron
koşar (birkaç yüz satır < ~100 ms); baytlar Content-Disposition ile döner.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from tenderiq_api.dependencies import PrincipalDep, TenantSessionDep, require_role
from tenderiq_api.errors import ConflictError, NotFoundError
from tenderiq_core.export import (
    COMPLIANCE_STATUS_LABELS,
    DELIVERABLE_KIND_LABELS,
    REQUIREMENT_KIND_LABELS,
    RISK_CATEGORY_LABELS,
    RISK_SEVERITY_LABELS,
    TIMELINE_KIND_LABELS,
    ReportItem,
    ReportSection,
    SourceRef,
    TenderReport,
    build_docx_report,
    build_xlsx_report,
)
from tenderiq_core.findings import ReviewStatus
from tenderiq_core.models import (
    AuditAction,
    ComplianceResult,
    Deliverable,
    Document,
    Organization,
    ParsedElement,
    Requirement,
    RiskFlag,
    Role,
    Tender,
    TimelineEvent,
)
from tenderiq_core.services.audit import record_audit
from tenderiq_core.storage import safe_key_component

router = APIRouter(prefix="/tenders", tags=["export"])

_writer = Depends(require_role(Role.ADMIN, Role.MEMBER))

_REPORT_TIMEZONE = ZoneInfo("Europe/Istanbul")

_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class ExportFormat(StrEnum):
    """Export dosya biçimi."""

    DOCX = "docx"
    XLSX = "xlsx"


class TenderExportRequest(BaseModel):
    """Export isteği: biçim + onay bekleyenler dahil mi."""

    model_config = ConfigDict(extra="forbid")

    format: ExportFormat = ExportFormat.DOCX
    include_pending: bool = False


def _yes_no(value: bool) -> str:
    return "Evet" if value else "Hayır"


# Kategori sözleşmesi: (bölüm başlığı, ORM modeli, tablo başlıkları, satır → hücreler).
_EXPORT_SECTIONS: tuple[
    tuple[str, type[Any], tuple[str, ...], Callable[[Any], tuple[str, ...]]], ...
] = (
    (
        "Gereksinimler",
        Requirement,
        ("Gereksinim", "Tür", "Zorunlu"),
        lambda r: (
            r.text,
            REQUIREMENT_KIND_LABELS.get(r.kind.value, r.kind.value),
            _yes_no(r.is_mandatory),
        ),
    ),
    (
        "İstenen Belgeler",
        Deliverable,
        ("Belge", "Tür", "Zorunlu"),
        lambda r: (
            r.name,
            DELIVERABLE_KIND_LABELS.get(r.kind.value, r.kind.value),
            _yes_no(r.is_mandatory),
        ),
    ),
    (
        "Riskler",
        RiskFlag,
        ("Risk Maddesi", "Önem", "Kategori"),
        lambda r: (
            r.text,
            RISK_SEVERITY_LABELS.get(r.severity.value, r.severity.value),
            RISK_CATEGORY_LABELS.get(r.category.value, r.category.value),
        ),
    ),
    (
        "Takvim",
        TimelineEvent,
        ("Öğe", "Tür", "Değer"),
        lambda r: (
            r.label,
            TIMELINE_KIND_LABELS.get(r.kind.value, r.kind.value),
            r.value_text,
        ),
    ),
    (
        "Uygunluk",
        ComplianceResult,
        ("Gereksinim", "Durum", "Gerekçe"),
        lambda r: (
            r.requirement_text,
            COMPLIANCE_STATUS_LABELS.get(r.status.value, r.status.value),
            r.rationale,
        ),
    ),
)


async def _collect_report(
    session: Any,
    *,
    tender: Tender,
    organization_name: str,
    include_pending: bool,
) -> TenderReport:
    """Beş kategoriden rapor verisini toplar (grounding join'i liste uçlarıyla aynı)."""
    statuses = [ReviewStatus.APPROVED, ReviewStatus.EDITED]
    if include_pending:
        statuses.append(ReviewStatus.PENDING)

    sections: list[ReportSection] = []
    for title, model, headers, to_cells in _EXPORT_SECTIONS:
        result = await session.execute(
            select(model, ParsedElement, Document.filename)
            .join(ParsedElement, model.source_element_id == ParsedElement.id)
            .join(Document, model.document_id == Document.id)
            .where(model.tender_id == tender.id, model.review_status.in_(statuses))
            .order_by(model.document_id, model.seq)
        )
        items = tuple(
            ReportItem(
                cells=to_cells(row),
                review_status=row.review_status,
                source=SourceRef(
                    document=filename,
                    page=element.page,
                    section=element.section,
                    quote=row.source_quote,
                ),
            )
            for row, element, filename in result.all()
        )
        sections.append(ReportSection(title=title, headers=headers, items=items))

    return TenderReport(
        organization=organization_name,
        tender_title=tender.title,
        generated_at=datetime.now(_REPORT_TIMEZONE),
        sections=tuple(sections),
    )


@router.post(
    "/{tender_id}/export",
    dependencies=[_writer],
    responses={
        200: {
            "description": "Üretilen rapor dosyası (Content-Disposition: attachment).",
            "content": {
                media_type: {"schema": {"type": "string", "format": "binary"}}
                for media_type in _MEDIA_TYPES.values()
            },
        }
    },
)
async def export_tender(
    tender_id: uuid.UUID,
    body: TenderExportRequest,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> Response:
    """Onaylı analizden yapılandırılmış Word/Excel raporu üretir ve indirir.

    Hiç rapora girecek bulgu yoksa 409 döner (önce inceleme/onay gerekir).
    Export AuditLog'a yazılır (kim-ne zaman-hangi biçim, §10.5).
    """
    tender = await session.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError("İhale bulunamadı.")
    organization = await session.get(Organization, principal.tenant_id)
    organization_name = organization.name if organization is not None else ""

    report = await _collect_report(
        session,
        tender=tender,
        organization_name=organization_name,
        include_pending=body.include_pending,
    )
    if report.is_empty():
        raise ConflictError(
            "Rapora girecek bulgu yok: önce bulguları onaylayın "
            "(veya include_pending ile onay bekleyenleri dahil edin)."
        )

    builder = build_docx_report if body.format is ExportFormat.DOCX else build_xlsx_report
    data = await asyncio.to_thread(builder, report)  # CPU işi event loop'u bloklamasın

    counts = {section.title: len(section.items) for section in report.sections}
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.TENDER_EXPORTED,
        resource_type="tender",
        resource_id=tender.id,
        actor_user_id=principal.user_id,
        meta={
            "format": body.format.value,
            "include_pending": body.include_pending,
            "counts": counts,
        },
    )
    await session.flush()

    filename = (
        f"tenderiq-{safe_key_component(tender.title, max_length=60)}"
        f"-{report.generated_at:%Y%m%d}.{body.format.value}"
    )
    ascii_fallback = (
        filename.encode("ascii", "ignore").decode() or f"tenderiq-rapor.{body.format.value}"
    )
    return Response(
        content=data,
        media_type=_MEDIA_TYPES[body.format.value],
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )
