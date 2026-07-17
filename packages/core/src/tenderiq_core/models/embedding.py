"""Embedding (vektör) modeli — pgvector kolonu, kiracı-özel, RLS (§6.5, ADR-0008).

Chunk'tan ayrı tablo: aynı chunk farklı bir modelle yeniden gömülebilir
(``uq_embedding_chunk_model``) ve getirim sorgusu model adıyla filtreler —
model geçişinde eski vektörler yeni indeksleme bitene dek hizmet vermeye
devam eder. Vektör boyutu kolon tipinde sabittir (``EMBEDDING_DIM``); farklı
boyutlu bir modele geçiş migration gerektirir (ADR-0008).
"""

from __future__ import annotations

import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin

# BGE-M3 yoğun vektör boyutu. Migration 0006'daki kolon tipi ve EMBEDDING_DIM
# ayarının varsayılanı ile SÖZLEŞMELİDİR — üçü birlikte değişir.
EMBEDDING_DIM = 1024


class Embedding(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir chunk'ın tek modelle üretilmiş yoğun vektörü."""

    __tablename__ = "embedding"
    __table_args__ = (UniqueConstraint("chunk_id", "model", name="uq_embedding_chunk_model"),)

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chunk.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(255), nullable=False)  # üreten model kimliği
    # L2-normalize yoğun vektör; benzerlik cosine (ivme: HNSW vector_cosine_ops).
    vector: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
