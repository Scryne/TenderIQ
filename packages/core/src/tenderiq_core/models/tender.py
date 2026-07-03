"""Tender (ihale/RFP projesi) modeli — kiracı-özel, RLS ile korunur."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin


class TenderStatus(StrEnum):
    """İhale analiz durumu."""

    DRAFT = "draft"
    ANALYZING = "analyzing"
    REVIEW_READY = "review_ready"
    ARCHIVED = "archived"


class Tender(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Analiz edilen tek bir ihale/RFP projesi (kiracı-özel)."""

    __tablename__ = "tender"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[TenderStatus] = mapped_column(
        SAEnum(TenderStatus, native_enum=False, length=20), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="SET NULL")
    )
