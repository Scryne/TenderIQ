"""İnsan-döngüde inceleme mixin'i (Sprint 3.2, §4.3) — beş bulgu modelinde ortak.

``review_status`` çıkarım sonrası PENDING doğar; onay/red/düzeltme API'den
``reviewed_by``/``reviewed_at`` ile birlikte yazılır. Yeniden çıkarım
(delete+insert) bu kolonları bilinçli sıfırlar: yeni çıkarım yeni inceleme
gerektirir (bkz. ``models.requirement`` idempotency notu).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.findings import ReviewStatus


class ReviewMixin:
    """Bulgu tablolarına inceleme durumu + kim/ne zaman kolonları ekler."""

    review_status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, native_enum=False, length=20),
        nullable=False,
        default=ReviewStatus.PENDING,
        server_default="PENDING",
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
