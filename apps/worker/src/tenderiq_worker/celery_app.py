"""Celery uygulaması — broker/backend Redis (ayarlardan).

İş durum makinesi (queued→parsing→indexing→extracting→review_ready→failed, §5.5)
task'ları Faz 1'de bu uygulama üzerine eklenecektir. Task'lar idempotent tasarlanır.
"""

from __future__ import annotations

from celery import Celery

from tenderiq_core.config import get_settings


def create_celery_app() -> Celery:
    """Yapılandırılmış bir Celery uygulaması üretir."""
    settings = get_settings()
    app = Celery(
        "tenderiq",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["tenderiq_worker.tasks.system"],
    )
    app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_default_queue="tenderiq",
        result_expires=3600,
        timezone="UTC",
        enable_utc=True,
    )
    return app


celery_app = create_celery_app()
