"""Job (asenkron işleme işi) modeli — durum makinesi (§5.5), kiracı-özel, RLS.

Durum akışı: ``queued → parsing → indexing → extracting → review_ready``;
her adımdan ``failed``'e düşülebilir, ``failed → queued`` yeniden kuyruklamadır.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin


class JobStatus(StrEnum):
    """İşleme işinin durumu (§5.5)."""

    QUEUED = "queued"
    PARSING = "parsing"
    INDEXING = "indexing"
    EXTRACTING = "extracting"
    REVIEW_READY = "review_ready"
    FAILED = "failed"


# İzinli geçişler (§5.5). FAILED → QUEUED yeniden kuyruklama içindir.
JOB_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.PARSING, JobStatus.FAILED}),
    JobStatus.PARSING: frozenset({JobStatus.INDEXING, JobStatus.FAILED}),
    JobStatus.INDEXING: frozenset({JobStatus.EXTRACTING, JobStatus.FAILED}),
    JobStatus.EXTRACTING: frozenset({JobStatus.REVIEW_READY, JobStatus.FAILED}),
    JobStatus.REVIEW_READY: frozenset(),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),
}

TERMINAL_JOB_STATUSES: frozenset[JobStatus] = frozenset({JobStatus.REVIEW_READY, JobStatus.FAILED})


class InvalidJobTransitionError(ValueError):
    """Durum makinesinde tanımsız bir geçiş denendi."""

    def __init__(self, current: JobStatus, target: JobStatus) -> None:
        super().__init__(f"Geçersiz iş durumu geçişi: {current} → {target}")
        self.current = current
        self.target = target


class Job(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir dokümanın asenkron işleme hattındaki işi (kiracı-özel)."""

    __tablename__ = "job"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, native_enum=False, length=20),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_terminal(self) -> bool:
        """İş nihai bir durumda mı (``review_ready`` veya ``failed``)."""
        return self.status in TERMINAL_JOB_STATUSES

    def transition_to(self, target: JobStatus) -> None:
        """Durumu geçiş kurallarını uygulayarak günceller; tanımsız geçiş → hata."""
        if target not in JOB_TRANSITIONS[self.status]:
            raise InvalidJobTransitionError(self.status, target)
        self.status = target
