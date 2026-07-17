"""Celery uygulaması — broker/backend Redis (ayarlardan).

İş durum makinesi task'ları (queued→parsing→indexing→extracting→review_ready→failed,
§5.5) ``tasks.documents`` modülündedir; task'lar idempotent tasarlanır.
"""

from __future__ import annotations

from celery import Celery

from tenderiq_core.config import get_settings
from tenderiq_core.observability import init_sentry
from tenderiq_core.queueing import QUEUE_DEFAULT, TASK_CLEANUP_STALE_UPLOADS


def create_celery_app() -> Celery:
    """Yapılandırılmış bir Celery uygulaması üretir."""
    settings = get_settings()
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
        },
    )
    return app


celery_app = create_celery_app()
