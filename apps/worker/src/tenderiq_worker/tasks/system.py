"""Sistem/sağlık task'ları."""

from __future__ import annotations

from tenderiq_worker.celery_app import celery_app


@celery_app.task(name="system.ping")
def ping() -> str:
    """Basit sağlık task'ı — ``"pong"`` döner (worker canlılığı doğrulaması)."""
    return "pong"
