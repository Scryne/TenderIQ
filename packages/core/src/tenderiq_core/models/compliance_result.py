"""ComplianceResult (gereksinim ↔ yetkinlik profili gap analizi) — RLS (§8.2).

Compliance Checker'ın kalıcı çıktısı (temel gap analizi, §6.7): çıkarılmış her
gereksinimi firmanın ``CapabilityProfile``'ına karşı değerlendirir
(karşılanıyor/kısmi/karşılanmıyor + gerekçe). Bağlamdan çıkarım DEĞİL, çıkarılmış
gereksinim üzerinde değerlendirmedir; bu yüzden grounding, değerlendirilen
gereksinimin kendi kaynağından DEVRALINIR (``source_element_id`` = gereksinimin
maddesi). ``requirement_text`` denormalize edilmiş anlık görüntüdür (profil ve
gereksinimler yeniden koşumda değişebilir; sonuç kendi başına anlaşılır kalır).
Idempotency/grounding sözleşmesi ``models.requirement`` ile aynıdır (ADR-0006).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin
from tenderiq_core.findings import ComplianceStatus, GroundingResolution


class ComplianceResult(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir gereksinimin yetkinlik profiline göre karşılanma değerlendirmesi."""

    __tablename__ = "compliance_result"
    __table_args__ = (
        UniqueConstraint("document_id", "seq", name="uq_compliance_result_document_seq"),
    )

    tender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tender.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # doküman içi bulgu sırası (0-…)
    requirement_text: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # değerlendirilen gereksinim
    status: Mapped[ComplianceStatus] = mapped_column(
        SAEnum(ComplianceStatus, native_enum=False, length=20), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)  # karar gerekçesi (profil ↔ şart)
    # Grounding gereksinimin kaynağından devralınır (değerlendirilen madde).
    source_element_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("parsed_element.id", ondelete="CASCADE"), index=True
    )
    grounding_resolution: Mapped[GroundingResolution] = mapped_column(
        SAEnum(GroundingResolution, native_enum=False, length=20), nullable=False
    )
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
