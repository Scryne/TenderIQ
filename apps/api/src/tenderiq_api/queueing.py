"""Celery üretici — task'ları ada göre kuyruğa yayınlar (worker kodu import edilmez).

Task adları/kuyruk adı ``tenderiq_core.queueing`` sözleşmesinden gelir; worker
(``apps/worker``) aynı adlarla tüketir.
"""

from __future__ import annotations

import uuid

from celery import Celery

from tenderiq_core.config import get_settings
from tenderiq_core.queueing import QUEUE_DEFAULT, TASK_PROCESS_DOCUMENT

_producer: Celery | None = None


def _get_producer() -> Celery:
    global _producer
    if _producer is None:
        settings = get_settings()
        app = Celery("tenderiq-api-producer", broker=settings.redis_url)
        app.conf.task_default_queue = QUEUE_DEFAULT
        _producer = app
    return _producer


def enqueue_process_document(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Doküman işleme job'ını kuyruğa yayınlar (commit SONRASI çağrılmalıdır)."""
    _get_producer().send_task(
        TASK_PROCESS_DOCUMENT,
        kwargs={"job_id": str(job_id), "tenant_id": str(tenant_id)},
        queue=QUEUE_DEFAULT,
    )
