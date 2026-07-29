"""Celery uygulaması — broker/backend Redis (ayarlardan).

İş durum makinesi task'ları (queued→parsing→indexing→extracting→review_ready→failed,
§5.5) ``tasks.documents`` modülündedir; task'lar idempotent tasarlanır.
"""

from __future__ import annotations

from celery import Celery

from tenderiq_core.config import Environment, get_settings
from tenderiq_core.logging import configure_logging
from tenderiq_core.observability import init_sentry
from tenderiq_core.queueing import (
    QUEUE_DEFAULT,
    TASK_CLEANUP_STALE_UPLOADS,
    TASK_PURGE_DELETED,
    TASK_RECONCILE_SUBSCRIPTIONS,
)


def create_celery_app() -> Celery:
    """Yapılandırılmış bir Celery uygulaması üretir."""
    settings = get_settings()
    # İşleme hattının TAMAMI worker'da koşar; API ile aynı yapılandırılmış (JSON)
    # log biçimi olmadan production'da parse/index/extract kayıtları aranamaz.
    configure_logging(json_logs=settings.environment is not Environment.DEVELOPMENT)
    init_sentry(settings)  # DSN yoksa no-op; CeleryIntegration task hatalarını yakalar
    app = Celery(
        "tenderiq",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["tenderiq_worker.tasks.system", "tenderiq_worker.tasks.documents"],
    )
    app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        # Zaman tavanı: parsing/OCR kullanıcı kontrolündeki bir PDF üzerinde koşar.
        # Tavan olmadan patolojik bir doküman (dev tarama, decompression bomb) bir
        # worker sürecini süresiz bloke edebilir — prefetch=1 olduğundan o slot
        # başka kiracılara da kapanır. Soft limit SoftTimeLimitExceeded fırlatır;
        # task'ın mevcut hata yolu işi backoff'la yeniden dener, denemeler
        # tükenince `failed`e çeker. Hard limit yalnız takılan süreç için ağ.
        task_soft_time_limit=25 * 60,
        task_time_limit=30 * 60,
        task_default_queue=QUEUE_DEFAULT,
        result_expires=3600,
        timezone="UTC",
        enable_utc=True,
        # Zamanlanmış bakım (worker `-B` bayrağıyla veya ayrı beat servisiyle koşar).
        beat_schedule={
            "cleanup-stale-uploads": {
                "task": TASK_CLEANUP_STALE_UPLOADS,
                "schedule": 3600.0,  # saatte bir
            },
            # KVKK kalıcı silme (Faz 4). Günde bir yeterlidir: eşik gün
            # cinsindendir (DATA_RETENTION_DAYS), daha sık koşmak yalnız boş
            # tarama üretir. Gecikme toleransı da gün ölçeğindedir.
            "purge-deleted": {
                "task": TASK_PURGE_DELETED,
                "schedule": 24 * 3600.0,
            },
            # Mutabakat SIK koşar: "ödeme alındı ama erişim açılmadı" hâlinin
            # süresi doğrudan müşterinin bekleme süresidir. Saatlik, kayıp bir
            # webhook'un etkisini en fazla bir saatle sınırlar.
            "reconcile-subscriptions": {
                "task": TASK_RECONCILE_SUBSCRIPTIONS,
                "schedule": 3600.0,
            },
        },
    )
    return app


celery_app = create_celery_app()
