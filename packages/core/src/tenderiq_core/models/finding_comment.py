"""FindingComment — bulguya ekip notu (Sprint 3.2, temel işbirliği) — RLS.

Beş bulgu tablosuna tek tablodan bağlanır (``finding_kind`` + ``finding_id``);
polimorfik hedefe gerçek FK konulamaz. Yeniden çıkarım bulguları delete+insert
ettiğinde yorumlar yetim kalmasın diye worker, bulgu silmeden önce ilgili
yorumları da siler (``tenderiq_worker.extraction``) — yeni çıkarım yeni
tartışma gerektirir (inceleme durumu sıfırlamasıyla aynı gerekçe).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin
from tenderiq_core.findings import FindingKind


class FindingComment(UUIDPKMixin, TenantMixin, Base):
    """Tek bir bulgu yorumu (yazar + zaman damgalı, değiştirilmez)."""

    __tablename__ = "finding_comment"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tender.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_kind: Mapped[FindingKind] = mapped_column(
        SAEnum(FindingKind, native_enum=False, length=20), nullable=False
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
