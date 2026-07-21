"""RiskFlag (çıkarılmış risk maddesi) modeli — kiracı-özel, RLS (§8.2).

Risk Detector ajanının kalıcı çıktısı; grounding ve idempotency sözleşmesi
``models.requirement`` ile birebir aynıdır (ADR-0006). Cezai şart, fesih,
sınırsız sorumluluk gibi olağandışı/riskli maddeleri önem derecesiyle işaretler.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin
from tenderiq_core.findings import GroundingResolution, RiskCategory, RiskSeverity
from tenderiq_core.models.review import ReviewMixin


class RiskFlag(UUIDPKMixin, TenantMixin, TimestampMixin, ReviewMixin, Base):
    """Bir dokümandan çıkarılmış tek risk maddesi (kaynak öğe bağlı)."""

    __tablename__ = "risk_flag"
    __table_args__ = (UniqueConstraint("document_id", "seq", name="uq_risk_flag_document_seq"),)

    tender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tender.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # doküman içi bulgu sırası (0-…)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[RiskSeverity] = mapped_column(
        SAEnum(RiskSeverity, native_enum=False, length=20), nullable=False
    )
    category: Mapped[RiskCategory] = mapped_column(
        SAEnum(RiskCategory, native_enum=False, length=20), nullable=False
    )
    source_element_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("parsed_element.id", ondelete="CASCADE"), index=True
    )
    grounding_resolution: Mapped[GroundingResolution] = mapped_column(
        SAEnum(GroundingResolution, native_enum=False, length=20), nullable=False
    )
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
