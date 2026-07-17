"""Chunk (getirim parçası) modeli — kiracı-özel, RLS.

Yapı-farkında chunking (§6.3) çıktısının kalıcı hâli. Her chunk kaynağını bilir:
sayfa aralığı + kaynak ``ParsedElement.seq`` aralığı (citation-first — bulgu →
chunk → öğe → sayfa/bbox zinciri buradan yürür). İlişki: ``Document 1—N Chunk``;
idempotent yeniden-indeksleme delete+insert ile yapılır (embedding'ler FK
cascade ile birlikte silinir).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin


class Chunk(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir dokümanın getirime hazır tek parçası (bölüm + sayfa/öğe aralıklı)."""

    __tablename__ = "chunk"
    __table_args__ = (
        # Idempotent yeniden-indeksleme güvencesi: doküman içi chunk sırası tekildir.
        UniqueConstraint("document_id", "seq", name="uq_chunk_document_seq"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # doküman içi chunk sırası (0-…)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(Text)  # ait olduğu bölüm başlığı
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-indeksli; konumsuzda 0
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)  # dahil
    # Kaynak öğe aralığı (ParsedElement.seq, her iki uç dahil) — citation zinciri.
    element_seq_start: Mapped[int] = mapped_column(Integer, nullable=False)
    element_seq_end: Mapped[int] = mapped_column(Integer, nullable=False)
