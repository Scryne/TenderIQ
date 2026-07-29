"""Kuyruk sözleşmesi: task adları ve kuyruk adı sabitleri.

API (üretici) ve worker (tüketici) task'lara yalnızca bu adlarla başvurur;
API, worker kodunu import etmez (``send_task`` ada göre yayınlar).
"""

from __future__ import annotations

QUEUE_DEFAULT = "tenderiq"

TASK_PROCESS_DOCUMENT = "documents.process"
TASK_CLEANUP_STALE_UPLOADS = "documents.cleanup_stale_uploads"
# KVKK kalıcı silme (Faz 4): saklama penceresi dolan yumuşak silmeleri kesinleştirir.
TASK_PURGE_DELETED = "data.purge_deleted"
# Abonelik mutabakatı (Tur 6): webhook'un hiç gelmediği hâlin TEK yedeği.
TASK_RECONCILE_SUBSCRIPTIONS = "billing.reconcile_subscriptions"
# Dönem sonu gelmiş iptal ve düşürmeleri uygular (Tur 7): `/sartlar` §3'ün
# "dönem sonunda" kısmının gerçekten olmasını sağlayan yedek.
TASK_APPLY_DUE_SUBSCRIPTION_CHANGES = "billing.apply_due_subscription_changes"
