"""Doküman işleme hattı task'ları — idempotent, retry/backoff'lu (§5.5).

Tasarım:
- Her faz (parsing/indexing/extracting) kendi transaction'ında ilerler; SSE
  akışı ara durumları canlı görür.
- Task yeniden çalıştığında (retry / duplicate teslim) kaldığı fazdan devam
  eder: tamamlanmış iş için no-op, ara durumda kalan iş için o fazdan devam.
- Deneme tükenince iş ``failed``'e çekilir ve hata mesajı kaydedilir.

Faz gövdeleri Sprint 1.2 (parsing), 1.3 (chunk/embed/index) ve Faz 2
(extraction) tarafından doldurulacak iskeletlerdir.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from celery import Task
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from tenderiq_core.config import get_settings
from tenderiq_core.logging import get_logger
from tenderiq_core.models import (
    Document,
    DocumentStatus,
    InvalidJobTransitionError,
    Job,
    JobStatus,
    Organization,
    Tender,
    TenderStatus,
)
from tenderiq_core.queueing import TASK_CLEANUP_STALE_UPLOADS, TASK_PROCESS_DOCUMENT
from tenderiq_core.storage import StorageNotConfiguredError
from tenderiq_worker.celery_app import celery_app
from tenderiq_worker.db import get_session_factory, tenant_session
from tenderiq_worker.indexing import run_indexing_phase
from tenderiq_worker.parsing import get_storage, run_parsing_phase

logger = get_logger("tenderiq.worker.documents")

_MAX_RETRIES = 5
_BACKOFF_BASE_SECONDS = 5
_BACKOFF_MAX_SECONDS = 300

# Faz sırası ve bir sonraki durum (§5.5).
_NEXT_STATUS: dict[JobStatus, JobStatus] = {
    JobStatus.PARSING: JobStatus.INDEXING,
    JobStatus.INDEXING: JobStatus.EXTRACTING,
    JobStatus.EXTRACTING: JobStatus.REVIEW_READY,
}


class JobNotVisibleError(Exception):
    """İş satırı henüz görünmüyor (API commit'i ile teslimat yarışı) — retry edilir."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _backoff_seconds(retries: int) -> int:
    return min(_BACKOFF_MAX_SECONDS, _BACKOFF_BASE_SECONDS * (1 << retries))


def _parse_document(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Parsing fazı — hibrit Docling/OCR hattı (ayrıntı: ``tenderiq_worker.parsing``)."""
    logger.info("parse_adimi", job_id=str(job_id), tenant_id=str(tenant_id))
    run_parsing_phase(job_id, tenant_id)


def _index_document(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Indexing fazı — chunk→embedding→pgvector (ayrıntı: ``tenderiq_worker.indexing``)."""
    logger.info("index_adimi", job_id=str(job_id), tenant_id=str(tenant_id))
    run_indexing_phase(job_id, tenant_id)


def _extract_findings(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Extracting fazı — Faz 2'de LangGraph çıkarım ajanlarına bağlanacak."""
    logger.info("extract_adimi", job_id=str(job_id), tenant_id=str(tenant_id))


_PHASE_HANDLERS = {
    JobStatus.PARSING: _parse_document,
    JobStatus.INDEXING: _index_document,
    JobStatus.EXTRACTING: _extract_findings,
}


def _begin_run(job_id: uuid.UUID, tenant_id: uuid.UUID) -> JobStatus | None:
    """Çalıştırmayı başlatır: deneme sayacı, queued→parsing, tender→analyzing.

    İş nihai durumdaysa ``None`` döner (idempotent no-op).
    """
    with tenant_session(tenant_id) as session:
        job = session.get(Job, job_id)
        if job is None:
            raise JobNotVisibleError(str(job_id))
        if job.is_terminal:
            return None
        job.attempts += 1
        if job.status is JobStatus.QUEUED:
            job.transition_to(JobStatus.PARSING)
            job.started_at = _utcnow()
            document = session.get(Document, job.document_id)
            if document is not None:
                tender = session.get(Tender, document.tender_id)
                if tender is not None and tender.status is TenderStatus.DRAFT:
                    tender.status = TenderStatus.ANALYZING
        return job.status


def _advance(job_id: uuid.UUID, tenant_id: uuid.UUID, current: JobStatus) -> JobStatus:
    """Fazı tamamlandı olarak işaretler; işi bir sonraki duruma geçirir."""
    target = _NEXT_STATUS[current]
    with tenant_session(tenant_id) as session:
        job = session.get(Job, job_id)
        if job is None:
            raise JobNotVisibleError(str(job_id))
        job.transition_to(target)
        if target is JobStatus.REVIEW_READY:
            job.finished_at = _utcnow()
            job.error_message = None
            document = session.get(Document, job.document_id)
            if document is not None:
                tender = session.get(Tender, document.tender_id)
                if tender is not None and tender.status is TenderStatus.ANALYZING:
                    tender.status = TenderStatus.REVIEW_READY
    return target


def _record_error(job_id: uuid.UUID, tenant_id: uuid.UUID, exc: Exception, *, final: bool) -> None:
    """Hata mesajını işler; deneme tükendiyse işi ``failed``'e çeker."""
    try:
        with tenant_session(tenant_id) as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            job.error_message = f"{type(exc).__name__}: {exc}"[:2000]
            if final and not job.is_terminal:
                job.transition_to(JobStatus.FAILED)
                job.finished_at = _utcnow()
    except Exception:  # hata kaydı, asıl hatayı gölgelememeli
        logger.error("hata_kaydi_basarisiz", job_id=str(job_id), exc_info=True)


def _run_pipeline(job_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    status = _begin_run(job_id, tenant_id)
    if status is None:
        return "already_terminal"
    while status is not JobStatus.REVIEW_READY:
        handler = _PHASE_HANDLERS[status]
        handler(job_id, tenant_id)
        status = _advance(job_id, tenant_id, status)
    return status.value


@celery_app.task(bind=True, name=TASK_PROCESS_DOCUMENT, max_retries=_MAX_RETRIES)
def process_document(self: Task, *, job_id: str, tenant_id: str) -> str:
    """Bir dokümanın işleme hattını yürütür (idempotent; hata → backoff'lu retry)."""
    job_uuid = uuid.UUID(job_id)
    tenant_uuid = uuid.UUID(tenant_id)
    try:
        return _run_pipeline(job_uuid, tenant_uuid)
    except InvalidJobTransitionError as exc:
        # Programlama hatası: retry anlamsız, işi doğrudan failed'e çek.
        _record_error(job_uuid, tenant_uuid, exc, final=True)
        raise
    except Exception as exc:
        logger.warning(
            "islem_hatasi",
            job_id=job_id,
            retries=self.request.retries,
            error=str(exc),
        )
        # Ara hata da kayda geçer: kullanıcı SSE'de işi sebepsiz takılı görmez.
        _record_error(job_uuid, tenant_uuid, exc, final=False)
        try:
            raise self.retry(exc=exc, countdown=_backoff_seconds(self.request.retries)) from exc
        except MaxRetriesExceededError:
            _record_error(job_uuid, tenant_uuid, exc, final=True)
            raise exc from None


@celery_app.task(name=TASK_CLEANUP_STALE_UPLOADS)
def cleanup_stale_uploads() -> int:
    """Yarım kalan yüklemeleri süpürür: eski ``pending_upload`` dokümanlar → ``failed``.

    RLS gereği kiracı kiracı dolaşılır (organization tablosu kiracı-kök tablodur,
    RLS'siz). Süre eşiği ``UPLOAD_PENDING_TTL_HOURS`` ayarından gelir.
    """
    settings = get_settings()
    cutoff = _utcnow() - timedelta(hours=settings.upload_pending_ttl_hours)
    factory = get_session_factory()
    with factory() as session:
        tenant_ids = list(session.scalars(select(Organization.id)))
    expired_total = 0
    for tenant_id in tenant_ids:
        stale_keys: list[str] = []
        with tenant_session(tenant_id) as session:
            stale_documents = session.scalars(
                select(Document).where(
                    Document.status == DocumentStatus.PENDING_UPLOAD,
                    Document.created_at < cutoff,
                )
            ).all()
            for document in stale_documents:
                document.status = DocumentStatus.FAILED
                stale_keys.append(document.storage_key)
        expired_total += len(stale_keys)
        # complete hiç çağrılmadıysa nesne depoda yetim kalmış olabilir;
        # commit sonrası best-effort silinir (hata süpürmeyi durdurmaz).
        _delete_objects_best_effort(stale_keys)
    if expired_total:
        logger.info("yarim_yukleme_temizligi", count=expired_total)
    return expired_total


def _delete_objects_best_effort(keys: list[str]) -> None:
    """Yarım yüklemelerin depodaki artıklarını siler; tek tek hatalar loglanır."""
    if not keys:
        return
    try:
        storage = get_storage()
    except StorageNotConfiguredError:
        logger.warning("supurge_depo_yapilandirilmamis", count=len(keys))
        return
    for key in keys:
        try:
            storage.delete_object(key)
        except Exception:
            logger.warning("supurge_nesne_silinemedi", key=key, exc_info=True)
