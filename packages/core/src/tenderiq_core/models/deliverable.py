"""Deliverable (istenen belge/sertifika/teminat) modeli — kiracı-özel, RLS (§8.1/§8.2).

Deliverables Extractor ajanının kalıcı çıktısı; grounding ve idempotency
sözleşmesi ``models.requirement`` ile birebir aynıdır (ADR-0006).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin
from tenderiq_core.findings import DeliverableKind, GroundingResolution


class Deliverable(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir dokümandan çıkarılmış tek istenen belge (kaynak öğe bağlı)."""

    __tablename__ = "deliverable"
    __table_args__ = (UniqueConstraint("document_id", "seq", name="uq_deliverable_document_seq"),)

    tender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tender.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # doküman içi bulgu sırası (0-…)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[DeliverableKind] = mapped_column(
        SAEnum(DeliverableKind, native_enum=False, length=20), nullable=False
    )
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_element_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("parsed_element.id", ondelete="CASCADE"), index=True
    )
    grounding_resolution: Mapped[GroundingResolution] = mapped_column(
        SAEnum(GroundingResolution, native_enum=False, length=20), nullable=False
    )
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
