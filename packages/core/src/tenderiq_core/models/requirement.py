"""Requirement (çıkarılmış gereksinim) modeli — kiracı-özel, RLS (§8.1/§8.2).

Requirement Extractor ajanının kalıcı çıktısı. Zorunlu grounding (ADR-0006):
``source_element_id`` kaynak ``ParsedElement``e ``N—1`` bağdır; UNGROUNDED
bulgularda NULL kalır ve API bu satırları DÖNDÜRMEZ (gözlemlenebilirlik/eval
için yine de yazılır). Enum'lar tek kaynaktan gelir (``tenderiq_core.findings``)
— ajan sözleşmesi ile DB şeması ayrışamaz.

Yeniden koşum idempotenttir: extracting fazı dokümanın satırlarını delete+insert
eder; re-parse ``ParsedElement`` cascade'iyle türetilmiş bulguları da siler
(hat yeniden koştuğunda yeniden üretilir).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin
from tenderiq_core.findings import GroundingResolution, RequirementKind


class Requirement(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir dokümandan çıkarılmış tek gereksinim (kaynak öğe bağlı)."""

    __tablename__ = "requirement"
    __table_args__ = (
        # Idempotent yeniden-çıkarım güvencesi: doküman içi bulgu sırası tekildir.
        UniqueConstraint("document_id", "seq", name="uq_requirement_document_seq"),
    )

    tender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tender.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # doküman içi bulgu sırası (0-…)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[RequirementKind] = mapped_column(
        SAEnum(RequirementKind, native_enum=False, length=20), nullable=False
    )
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Zorunlu grounding: kaynak öğe bağı + bağlanma düzeyi + doğrulanmış alıntı.
    source_element_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("parsed_element.id", ondelete="CASCADE"), index=True
    )
    grounding_resolution: Mapped[GroundingResolution] = mapped_column(
        SAEnum(GroundingResolution, native_enum=False, length=20), nullable=False
    )
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
