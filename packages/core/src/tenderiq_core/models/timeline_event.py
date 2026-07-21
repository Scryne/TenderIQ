"""TimelineEvent (çıkarılmış tarih/süre) modeli — kiracı-özel, RLS (§8.2).

Timeline Extractor ajanının kalıcı çıktısı; grounding ve idempotency
sözleşmesi ``models.requirement`` ile birebir aynıdır (ADR-0006). İhale tarihi,
son teklif verme tarihi, işin süresi, garanti süresi gibi öğeleri işaretler.

``value_text`` ham metindir (tarih/süre olduğu gibi tutulur, ``date``e
ayrıştırılmaz): TR şartnamelerde tarih/süre ifadeleri çok çeşitlidir ("30 gün",
"15/08/2026", "24 ay") ve birebir alıntı grounding'i ayrıştırmadan önce gelir.
Yapısal ayrıştırma (Faz 3 UI'ında gerekiyorsa) ayrı bir katmanda yapılır.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin
from tenderiq_core.findings import GroundingResolution, TimelineKind
from tenderiq_core.models.review import ReviewMixin


class TimelineEvent(UUIDPKMixin, TenantMixin, TimestampMixin, ReviewMixin, Base):
    """Bir dokümandan çıkarılmış tek tarih/süre öğesi (kaynak öğe bağlı)."""

    __tablename__ = "timeline_event"
    __table_args__ = (
        UniqueConstraint("document_id", "seq", name="uq_timeline_event_document_seq"),
    )

    tender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tender.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # doküman içi bulgu sırası (0-…)
    label: Mapped[str] = mapped_column(Text, nullable=False)  # öğenin adı (ör. "Son teklif tarihi")
    kind: Mapped[TimelineKind] = mapped_column(
        SAEnum(TimelineKind, native_enum=False, length=20), nullable=False
    )
    value_text: Mapped[str] = mapped_column(Text, nullable=False)  # ham tarih/süre metni
    source_element_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("parsed_element.id", ondelete="CASCADE"), index=True
    )
    grounding_resolution: Mapped[GroundingResolution] = mapped_column(
        SAEnum(GroundingResolution, native_enum=False, length=20), nullable=False
    )
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
