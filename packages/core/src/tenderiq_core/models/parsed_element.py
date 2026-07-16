"""ParsedElement (ayrıştırılmış öğe) modeli — izlenebilirlik verisi, kiracı-özel, RLS.

Her satır bir dokümandaki tek bir yapısal öğedir (başlık/paragraf/madde/tablo) ve
citation-first gereği **sayfa + bounding box** taşır (§8.1, ADR-0004).
İlişki: ``Document 1—N ParsedElement``. Enum tanımları tek kaynaktan gelir
(``tenderiq_core.parsing.types``) — parse sözleşmesi ile DB şeması ayrışamaz.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin
from tenderiq_core.parsing.types import ElementKind, ParseSource


class ParsedElement(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir dokümanın ayrıştırılmış tek öğesi (kiracı-özel, sayfa + konumlu)."""

    __tablename__ = "parsed_element"
    __table_args__ = (
        # Idempotent yeniden-parse güvencesi: aynı doküman içinde okuma sırası tekildir
        # (delete+insert dışında bir yol çift kayıt üretemez).
        UniqueConstraint("document_id", "seq", name="uq_parsed_element_document_seq"),
        # Citation sorguları sayfa üzerinden gelir (Faz 3 PDF vurgu katmanı).
        Index("ix_parsed_element_document_page", "document_id", "page"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # doküman içi okuma sırası (0-…)
    page: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-indeksli; konumsuz öğede 0
    kind: Mapped[ElementKind] = mapped_column(
        SAEnum(ElementKind, native_enum=False, length=20), nullable=False
    )
    source: Mapped[ParseSource] = mapped_column(
        SAEnum(ParseSource, native_enum=False, length=20), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(Text)  # ait olduğu bölüm başlığı
    # Bounding box (TOPLEFT origin, nokta cinsinden); taranmışta OCR'dan gelir.
    bbox_x0: Mapped[float | None] = mapped_column(Float)
    bbox_y0: Mapped[float | None] = mapped_column(Float)
    bbox_x1: Mapped[float | None] = mapped_column(Float)
    bbox_y1: Mapped[float | None] = mapped_column(Float)
