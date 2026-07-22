"""/api/v1/documents — yükleme tamamlama + dosya doğrulama (Sprint 1.1 güvenlik).

Tamamlama akışı: R2'de nesnenin varlığı/boyutu HEAD ile doğrulanır, magic-bytes
kontrolü yapılır, ``pending_upload → uploaded`` geçilir ve işleme job'ı kuyruğa
atılır. Doğrulamayı geçemeyen nesne depodan silinir, doküman ``failed`` olur.
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from tenderiq_api.dependencies import (
    EnqueueDep,
    PrincipalDep,
    SessionDep,
    SettingsDep,
    StorageDep,
    TenantSessionDep,
    require_role,
)
from tenderiq_api.errors import (
    ConflictError,
    NotFoundError,
    QuotaExceededError,
    ValidationFailedError,
)
from tenderiq_api.routers.v1.jobs import JobResponse
from tenderiq_api.routers.v1.tenders import DocumentResponse
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.models import (
    AuditAction,
    Document,
    DocumentStatus,
    Job,
    JobStatus,
    Role,
)
from tenderiq_core.services import quota
from tenderiq_core.services.audit import record_audit
from tenderiq_core.uploads import MAGIC_PROBE_LENGTH, matches_magic_bytes

router = APIRouter(prefix="/documents", tags=["documents"])

_writer = Depends(require_role(Role.ADMIN, Role.MEMBER))


class DocumentCompleteResponse(BaseModel):
    """Tamamlanan yükleme: güncel doküman + kuyruğa alınan iş."""

    document: DocumentResponse
    job: JobResponse | None


class DocumentFileResponse(BaseModel):
    """Önizleme için süre-sınırlı imzalı indirme URL'i (Sprint 3.1, §4.2)."""

    url: str
    content_type: str
    filename: str


@router.get("/{document_id}/file", response_model=DocumentFileResponse)
async def get_document_file(
    document_id: uuid.UUID,
    session: TenantSessionDep,
    storage: StorageDep,
) -> DocumentFileResponse:
    """İnceleme ekranı doküman önizlemesi için imzalı GET URL'i döndürür.

    URL süre-sınırlıdır (varsayılan 1 saat); erişim RLS ile kiracıya kapalıdır
    (başka kiracının dokümanı 404). Yüklemesi tamamlanmamış doküman için 409.
    """
    document = await session.get(Document, document_id)
    if document is None:
        raise NotFoundError("Doküman bulunamadı.")
    if document.status in (DocumentStatus.PENDING_UPLOAD, DocumentStatus.FAILED):
        raise ConflictError("Doküman yüklemesi tamamlanmadığı için önizlenemez.")
    return DocumentFileResponse(
        url=storage.presigned_get_url(document.storage_key),
        content_type=document.content_type,
        filename=document.filename,
    )


@router.post(
    "/{document_id}/complete",
    response_model=DocumentCompleteResponse,
    dependencies=[_writer],
)
async def complete_upload(
    document_id: uuid.UUID,
    session: SessionDep,
    principal: PrincipalDep,
    storage: StorageDep,
    settings: SettingsDep,
    enqueue: EnqueueDep,
) -> DocumentCompleteResponse:
    """Yüklemeyi doğrular, dokümanı ``uploaded`` yapar ve işleme job'ını kuyruklar.

    Idempotent: zaten ``uploaded`` bir doküman için mevcut son iş döndürülür.
    Kiracı bağlamı elle kurulur; job kuyruklama commit SONRASI yapılır (worker'ın
    henüz görünmeyen bir satırı okuma yarışını önler).
    """
    rejection_reason: str | None = None
    quota_exceeded: quota.QuotaExceededError | None = None
    response: DocumentCompleteResponse | None = None
    job_to_enqueue: Job | None = None

    async with session.begin():
        await set_tenant_context(session, principal.tenant_id)
        # with_for_update: eşzamanlı iki complete çağrısının ikişer job yaratmasını önler.
        document = await session.get(Document, document_id, with_for_update=True)
        if document is None:
            raise NotFoundError("Doküman bulunamadı.")

        if document.status is DocumentStatus.UPLOADED:
            existing_job = await session.scalar(
                select(Job)
                .where(Job.document_id == document.id)
                .order_by(Job.created_at.desc())
                .limit(1)
            )
            # Kuyruklama commit SONRASI yapıldığından ilk yayın broker kesintisinde
            # kaybolmuş olabilir; hâlâ queued görünen iş yeniden yayınlanır
            # (task idempotent — mükerrer teslim güvenlidir).
            if existing_job is not None and existing_job.status is JobStatus.QUEUED:
                job_to_enqueue = existing_job
            response = DocumentCompleteResponse(
                document=DocumentResponse.model_validate(document),
                job=JobResponse.model_validate(existing_job) if existing_job else None,
            )
        elif document.status is not DocumentStatus.PENDING_UPLOAD:
            raise ConflictError("Doküman yükleme bekleyen durumda değil.")
        else:
            info = await asyncio.to_thread(storage.head_object, document.storage_key)
            if info is None:
                raise ConflictError("Dosya nesne depolamada bulunamadı; yükleme tamamlanmamış.")

            if info.size_bytes > settings.upload_max_size_bytes:
                rejection_reason = "Dosya boyutu izin verilen sınırı aşıyor."
            elif info.size_bytes == 0:
                rejection_reason = "Yüklenen dosya boş."
            else:
                head = await asyncio.to_thread(
                    storage.read_prefix, document.storage_key, length=MAGIC_PROBE_LENGTH
                )
                if not matches_magic_bytes(document.content_type, head):
                    rejection_reason = "Dosya içeriği beyan edilen türle uyuşmuyor."

            # Yetkili kota denetimi: kayıt anındaki erken red aşılmış olabilir
            # (tamamlanmamış çok sayıda kayıt). Aşımda nesne yine silinir/failed
            # yapılır (ortak red yolu) ama HTTP 402 döner (içerik reddi 400).
            if rejection_reason is None:
                try:
                    await quota.enforce_document_quota(session, principal.tenant_id)
                except quota.QuotaExceededError as exc:
                    quota_exceeded = exc
                    label = quota.LIMIT_LABELS_TR.get(exc.limit_kind, exc.limit_kind)
                    rejection_reason = f"Aylık {label} kotanız dolu ({exc.used}/{exc.limit})."

            if rejection_reason is not None:
                # Doğrulamayı geçemeyen nesne depoda bırakılmaz (depolama istismarı).
                await asyncio.to_thread(storage.delete_object, document.storage_key)
                document.status = DocumentStatus.FAILED
                record_audit(
                    session,
                    tenant_id=principal.tenant_id,
                    action=AuditAction.DOCUMENT_UPLOAD_REJECTED,
                    resource_type="document",
                    resource_id=document.id,
                    actor_user_id=principal.user_id,
                    meta={"reason": rejection_reason, "size_bytes": info.size_bytes},
                )
            else:
                document.size_bytes = info.size_bytes
                document.status = DocumentStatus.UPLOADED
                job_to_enqueue = Job(
                    id=uuid.uuid4(),
                    tenant_id=principal.tenant_id,
                    document_id=document.id,
                    status=JobStatus.QUEUED,
                )
                session.add(job_to_enqueue)
                # Kota sayımı: doküman burada "kullanılmış" sayılır (pages=0;
                # gerçek sayfa sayısı parsing sonrası worker'da güncellenir).
                await quota.record_document_usage(session, principal.tenant_id, document.id)
                record_audit(
                    session,
                    tenant_id=principal.tenant_id,
                    action=AuditAction.DOCUMENT_UPLOAD_COMPLETED,
                    resource_type="document",
                    resource_id=document.id,
                    actor_user_id=principal.user_id,
                    meta={"size_bytes": info.size_bytes, "job_id": str(job_to_enqueue.id)},
                )
                await session.flush()
                response = DocumentCompleteResponse(
                    document=DocumentResponse.model_validate(document),
                    job=JobResponse.model_validate(job_to_enqueue),
                )

    # Transaction commit edildi; başarısızlık kalıcı, iş güvenle kuyruklanabilir.
    if quota_exceeded is not None:
        raise QuotaExceededError(
            (rejection_reason or "Aylık kotanız dolu.")
            + " Planınızı yükseltin veya bir sonraki döneme kadar bekleyin.",
            details=[
                {
                    "limit_kind": quota_exceeded.limit_kind,
                    "used": quota_exceeded.used,
                    "limit": quota_exceeded.limit,
                }
            ],
        )
    if rejection_reason is not None:
        raise ValidationFailedError(rejection_reason)
    assert response is not None  # noqa: S101 - tip daraltma
    if job_to_enqueue is not None:
        enqueue(job_to_enqueue.id, principal.tenant_id)
    return response
