"""/api/v1/tenders — ihale projeleri ve doküman yükleme (kiracı-özel, RLS + RBAC)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from tenderiq_api.dependencies import (
    PrincipalDep,
    StorageDep,
    TenantSessionDep,
    require_role,
)
from tenderiq_api.errors import NotFoundError
from tenderiq_core.models import (
    Document,
    DocumentKind,
    DocumentStatus,
    Role,
    Tender,
    TenderStatus,
)

router = APIRouter(prefix="/tenders", tags=["tenders"])

# Yazma işlemleri admin/üye gerektirir; izleyici yalnızca okuyabilir.
_writer = Depends(require_role(Role.ADMIN, Role.MEMBER))


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


class DocumentUploadResponse(BaseModel):
    """Doküman kaydı + süre-sınırlı imzalı yükleme URL'i."""

    document: DocumentResponse
    upload_url: str
    storage_key: str


@router.post(
    "", response_model=TenderResponse, status_code=status.HTTP_201_CREATED, dependencies=[_writer]
)
async def create_tender(
    body: TenderCreate, session: TenantSessionDep, principal: PrincipalDep
) -> TenderResponse:
    """Aktif kiracı için yeni bir ihale projesi oluşturur."""
    tender = Tender(
        tenant_id=principal.tenant_id,
        title=body.title,
        status=TenderStatus.DRAFT,
        created_by=principal.user_id,
    )
    session.add(tender)
    await session.flush()
    return TenderResponse.model_validate(tender)


@router.get("", response_model=list[TenderResponse])
async def list_tenders(session: TenantSessionDep) -> list[TenderResponse]:
    """Aktif kiracının ihalelerini listeler (RLS ile filtrelenir)."""
    result = await session.execute(select(Tender).order_by(Tender.created_at.desc()))
    return [TenderResponse.model_validate(t) for t in result.scalars().all()]


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
) -> DocumentUploadResponse:
    """Bir ihaleye doküman kaydı açar ve imzalı yükleme URL'i döndürür."""
    tender = await session.get(Tender, tender_id)
    if tender is None:  # RLS: başka kiracının ihalesi de burada None döner
        raise NotFoundError("İhale bulunamadı.")

    document_id = uuid.uuid4()
    storage_key = f"{principal.tenant_id}/{tender_id}/{document_id}/{body.filename}"
    document = Document(
        id=document_id,
        tenant_id=principal.tenant_id,
        tender_id=tender_id,
        filename=body.filename,
        content_type=body.content_type,
        storage_key=storage_key,
        kind=body.kind,
        status=DocumentStatus.PENDING_UPLOAD,
    )
    session.add(document)
    await session.flush()

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
