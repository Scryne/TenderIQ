"""Doküman işleme hattı task'ları — idempotent, retry/backoff'lu (§5.5).

Tasarım:
- Her faz (parsing/indexing/extracting) kendi transaction'ında ilerler; SSE
  akışı ara durumları canlı görür.
- Task yeniden çalıştığında (retry / duplicate teslim) kaldığı fazdan devam
  eder: tamamlanmış iş için no-op, ara durumda kalan iş için o fazdan devam.
- Deneme tükenince iş ``failed``'e çekilir ve hata mesajı kaydedilir.

Faz gövdeleri: parsing (Sprint 1.2), indexing (Sprint 1.3), extracting
(Sprint 2.1 — RAG bağlamı + LangGraph iskeleti; LLM ajanları Sprint 2.2'de).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from celery import Task
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from tenderiq_core.config import Settings, get_settings
from tenderiq_core.db.soft_delete import INCLUDE_DELETED
from tenderiq_core.logging import get_logger, job_id_var, tenant_id_var
from tenderiq_core.models import (
    AuditAction,
    Document,
    DocumentStatus,
    InvalidJobTransitionError,
    Job,
    JobStatus,
    Organization,
    Tender,
    TenderStatus,
)
from tenderiq_core.observability import bind_sentry_tags
from tenderiq_core.ops import JOB_PHASE_TOTAL, record_job_phase
from tenderiq_core.queueing import (
    TASK_APPLY_DUE_SUBSCRIPTION_CHANGES,
    TASK_CLEANUP_STALE_UPLOADS,
    TASK_PROCESS_DOCUMENT,
    TASK_PURGE_DELETED,
    TASK_RECONCILE_SUBSCRIPTIONS,
)
from tenderiq_core.services.audit import record_audit
from tenderiq_core.services.deletion import (
    collect_purgeable_organizations,
    purge_cutoff,
    purge_organization_sync,
    purge_tenant_sync,
)
from tenderiq_core.services.quota import QuotaExceededError
from tenderiq_core.storage import StorageNotConfiguredError
from tenderiq_worker.celery_app import celery_app
from tenderiq_worker.db import get_session_factory, tenant_session
from tenderiq_worker.extraction import run_extraction_phase
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
    """Extracting fazı — RAG bağlamı + LangGraph orkestrasyon (``tenderiq_worker.extraction``)."""
    logger.info("extract_adimi", job_id=str(job_id), tenant_id=str(tenant_id))
    run_extraction_phase(job_id, tenant_id)


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
            # Toplam süre DB'deki started_at'ten ölçülür, bu denemenin başından
            # değil: retry'lı bir iş kullanıcıya bir kez bekletir ve SLO'nun
            # ("işleme < 10 dk") ölçtüğü şey o bekleyiştir.
            _record_total_duration(job, ok=True)
            document = session.get(Document, job.document_id)
            if document is not None:
                tender = session.get(Tender, document.tender_id)
                if tender is not None and tender.status is TenderStatus.ANALYZING:
                    tender.status = TenderStatus.REVIEW_READY
    return target


def _record_total_duration(job: Job, *, ok: bool) -> None:
    """İşin uçtan uca süresini/sonucunu operasyon penceresine yazar (J.4)."""
    if job.started_at is None or job.finished_at is None:
        return
    elapsed = (job.finished_at - job.started_at).total_seconds()
    record_job_phase(JOB_PHASE_TOTAL, duration_seconds=elapsed, ok=ok)


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
                _record_total_duration(job, ok=False)
    except Exception:  # hata kaydı, asıl hatayı gölgelememeli
        logger.error("hata_kaydi_basarisiz", job_id=str(job_id), exc_info=True)


def _run_pipeline(job_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    status = _begin_run(job_id, tenant_id)
    if status is None:
        return "already_terminal"
    while status is not JobStatus.REVIEW_READY:
        handler = _PHASE_HANDLERS[status]
        started = time.perf_counter()
        try:
            handler(job_id, tenant_id)
        except Exception:
            # Faz sayacı deneme başınadır: "hangi faz patlıyor" sorusunun cevabı
            # denemelerin dağılımıdır, işin nihai sonucu değil (o `total`de).
            record_job_phase(status.value, duration_seconds=0.0, ok=False)
            raise
        record_job_phase(status.value, duration_seconds=time.perf_counter() - started, ok=True)
        status = _advance(job_id, tenant_id, status)
    return status.value


@celery_app.task(bind=True, name=TASK_PROCESS_DOCUMENT, max_retries=_MAX_RETRIES)
def process_document(self: Task, *, job_id: str, tenant_id: str) -> str:
    """Bir dokümanın işleme hattını yürütür (idempotent; hata → backoff'lu retry)."""
    job_uuid = uuid.UUID(job_id)
    tenant_uuid = uuid.UUID(tenant_id)
    # Sentry hata raporları iş/kiracı korelasyonu taşır (DSN yoksa no-op).
    bind_sentry_tags(tenant_id=tenant_uuid, job_id=job_uuid)
    # Aynı korelasyon hattın TÜM log kayıtlarına geçer (parse/index/extract dâhil).
    # Prefork worker süreci task'lar arası yaşadığından çıkışta sıfırlanır.
    tenant_token = tenant_id_var.set(tenant_id)
    job_token = job_id_var.set(job_id)
    try:
        return _run_pipeline(job_uuid, tenant_uuid)
    except (InvalidJobTransitionError, QuotaExceededError) as exc:
        # Kalıcı hatalar — retry anlamsız, iş doğrudan failed'e çekilir:
        # durum makinesi ihlali (programlama hatası) veya dönem kotası aşımı
        # (yeniden denemek aynı sonucu verir; dönem dönene kadar geçmez).
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
    finally:
        tenant_id_var.reset(tenant_token)
        job_id_var.reset(job_token)


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


@celery_app.task(name=TASK_PURGE_DELETED)
def purge_deleted() -> int:
    """Saklama penceresi dolan yumuşak silmeleri KALICI olarak siler (KVKK §8.3).

    Kullanıcının "sil" demesi veriyi anında yok etmez (bkz.
    ``tenderiq_core.services.deletion``); bu iş pencereyi dolduranları
    kesinleştirir: önce nesne depolamadaki dosyalar, sonra DB satırları
    (CASCADE alt tabloları götürür).

    Depolama yapılandırılmamışsa iş HİÇBİR ŞEY silmez ve uyarı basar: dosyayı
    silemeyeceksek DB satırını silmek, depoda erişilemez ve artık kime ait
    olduğu bilinmeyen dosya bırakırdı.

    RLS gereği kiracı kiracı dolaşılır (``organization`` kiracı-kök tablodur).
    """
    settings = get_settings()
    cutoff = purge_cutoff(settings.data_retention_days, now=_utcnow())

    try:
        storage = get_storage()
    except StorageNotConfiguredError:
        logger.warning("kalici_silme_atlandi_depo_yok")
        return 0

    def _delete_object(key: str) -> bool:
        try:
            storage.delete_object(key)
        except Exception:
            logger.warning("kalici_silme_nesne_silinemedi", key=key, exc_info=True)
            return False
        return True

    factory = get_session_factory()
    with factory() as session:
        # Bu liste ETKİN organizasyonlardır: yumuşak silme filtresi kapatılmış
        # olanları eler. Kapatılanlar aşağıda AYRI bir geçişte, tümüyle farklı
        # bir kuralla (içerik silinir, satır mezar taşı olarak kalır) işlenir.
        tenant_ids = list(session.scalars(select(Organization.id)))

    purged_total = 0
    for tenant_id in tenant_ids:
        with tenant_session(tenant_id) as session:
            result = purge_tenant_sync(session, cutoff=cutoff, delete_object=_delete_object)
            if not result.anything:
                continue
            # Denetim kaydı silinen satırdan SONRA da kalmalı: kalıcı silmenin
            # gerçekleştiğinin tek kanıtı budur (satırın kendisi artık yok).
            record_audit(
                session,
                tenant_id=tenant_id,
                action=AuditAction.DATA_PURGED,
                resource_type="tenant",
                resource_id=tenant_id,
                meta={
                    "tenders": result.tenders,
                    "documents": result.documents,
                    "objects_deleted": result.objects_deleted,
                    "objects_failed": result.objects_failed,
                    "retention_days": settings.data_retention_days,
                },
            )
        purged_total += result.tenders + result.documents
        logger.info(
            "kalici_silme_yapildi",
            tenant_id=str(tenant_id),
            tenders=result.tenders,
            documents=result.documents,
            objects_deleted=result.objects_deleted,
            objects_failed=result.objects_failed,
        )

    purged_total += _purge_closed_organizations(cutoff, _delete_object, settings)
    return purged_total


def _purge_closed_organizations(
    cutoff: datetime,
    delete_object: Callable[[str], bool],
    settings: Settings,
) -> int:
    """Kapatılmış organizasyonların içeriğini kalıcı siler (KVKK md. 7).

    Etkin kiracı süpürmesinden AYRI tutulur çünkü kuralı farklıdır: burada
    yalnız süresi dolmuş silmeler değil, kiracının TÜM içeriği gider ve ardından
    organizasyon satırı anonimleştirilip bırakılır (fatura/denetim kayıtları ona
    bağlıdır — bkz. ``services.deletion``).
    """
    factory = get_session_factory()
    with factory() as session:
        closed = collect_purgeable_organizations(session, cutoff)
        closed_ids = [organization.id for organization in closed]

    purged = 0
    for organization_id in closed_ids:
        with tenant_session(organization_id) as session:
            organization = session.execute(
                select(Organization)
                .where(Organization.id == organization_id)
                .execution_options(**{INCLUDE_DELETED: True})
            ).scalar_one_or_none()
            if organization is None:  # eşzamanlı başka bir koşu almış olabilir
                continue
            result = purge_organization_sync(session, organization, delete_object=delete_object)
            if result.objects_failed:
                logger.warning(
                    "hesap_kapatma_ertelendi_nesne_silinemedi",
                    tenant_id=str(organization_id),
                    objects_failed=result.objects_failed,
                )
                continue
            record_audit(
                session,
                tenant_id=organization_id,
                action=AuditAction.DATA_PURGED,
                resource_type="organization",
                resource_id=organization_id,
                meta={
                    "reason": "account_closed",
                    "tenders": result.tenders,
                    "objects_deleted": result.objects_deleted,
                    "memberships": result.memberships,
                    "users_deleted": result.users_deleted,
                    "retention_days": settings.data_retention_days,
                },
            )
        purged += 1
        logger.info(
            "hesap_kapatma_tamamlandi",
            tenant_id=str(organization_id),
            tenders=result.tenders,
            objects_deleted=result.objects_deleted,
            users_deleted=result.users_deleted,
        )
    return purged


@celery_app.task(name=TASK_RECONCILE_SUBSCRIPTIONS)
def reconcile_subscriptions() -> int:
    """Sağlayıcıdaki abonelik durumuyla bizdeki yetkilendirmeyi mutabık kılar.

    Checkout erişimi AÇMAZ; yetkilendirmeyi açan tek mekanizma webhook'tur.
    Webhook hiç gelmezse "ödeme alındı ama erişim açılmadı" hâli sessizce
    kalıcı olur — bu iş onun tek yedeğidir.

    Dönen değer: toplam sapma sayısı (sıfırdan farklıysa görünür olmalı).
    """
    import asyncio

    from tenderiq_core.billing.provider import BillingError, create_billing_provider
    from tenderiq_core.db import create_engine, create_session_factory
    from tenderiq_core.services import billing as billing_service

    settings = get_settings()
    try:
        provider = create_billing_provider(
            settings.billing_provider,
            webhook_secret=settings.billing_webhook_secret,
            settings=settings,
        )
    except BillingError as exc:
        logger.warning("mutabakat_saglayici_yok", error=str(exc))
        return 0

    factory = get_session_factory()
    with factory() as session:
        tenant_ids = list(session.scalars(select(Organization.id)))

    async def _run() -> int:
        engine = create_engine(settings)
        async_factory = create_session_factory(engine)
        try:
            async with async_factory() as async_session, async_session.begin():
                report = await billing_service.reconcile_subscriptions(
                    async_session, provider, tenant_ids=tenant_ids
                )
            return report.drift
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@celery_app.task(name=TASK_APPLY_DUE_SUBSCRIPTION_CHANGES)
def apply_due_subscription_changes() -> int:
    """Dönem sonu gelmiş iptalleri ve düşürmeleri uygular.

    `/sartlar` §3 "iptal, içinde bulunulan dönemin sonunda geçerli olur" ve
    "düşürmeler dönem sonunda uygulanır" der. Normalde bunu sağlayıcının dönem
    sonu olayı tetikler (ADR-0014: yetkilendirmenin kaynağı webhook'tur); bu
    görev onun **yedeğidir**. Olay hiç gelmezse iptal etmiş müşteri ücretsiz
    plana hiç düşmez ve ödemediği kotayı kullanmaya devam eder.

    Mutabakattan farkı: sağlayıcıya HİÇ ÇIKMAZ. Yalnızca kullanıcının kendi
    talep ettiği ve vakti gelmiş değişiklikleri uygular; sağlayıcı kesintisinde
    yanlış kapatma üretemez. Bu yüzden sağlayıcı yapılandırılmamış olsa bile
    koşar.

    Dönen değer: uygulanan değişiklik sayısı.
    """
    import asyncio

    from tenderiq_core.db import create_engine, create_session_factory
    from tenderiq_core.services import billing as billing_service

    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        tenant_ids = list(session.scalars(select(Organization.id)))

    async def _run() -> int:
        engine = create_engine(settings)
        async_factory = create_session_factory(engine)
        try:
            async with async_factory() as async_session, async_session.begin():
                report = await billing_service.apply_due_subscription_changes(
                    async_session, tenant_ids=tenant_ids
                )
            return report.applied
        finally:
            await engine.dispose()

    return asyncio.run(_run())
