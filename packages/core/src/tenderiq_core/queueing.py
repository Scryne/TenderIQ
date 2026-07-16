"""Kuyruk sözleşmesi: task adları ve kuyruk adı sabitleri.

API (üretici) ve worker (tüketici) task'lara yalnızca bu adlarla başvurur;
API, worker kodunu import etmez (``send_task`` ada göre yayınlar).
"""

from __future__ import annotations

QUEUE_DEFAULT = "tenderiq"

TASK_PROCESS_DOCUMENT = "documents.process"
TASK_CLEANUP_STALE_UPLOADS = "documents.cleanup_stale_uploads"
