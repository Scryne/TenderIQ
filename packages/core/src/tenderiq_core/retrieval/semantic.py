"""Semantik getirim: pgvector cosine (HNSW) sorgusu (§6.5–6.6).

Sorgu RLS'ye tabi oturumla çalışır — kiracı filtresi SQL'e yazılmaz,
politikadan gelir (ADR-0003). Model filtresi zorunludur: model geçişi
sırasında aynı chunk'ın iki vektörü bulunabilir (``uq_embedding_chunk_model``),
sorgu yalnızca aktif modelin vektörleriyle eşleşmelidir (ADR-0008).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from tenderiq_core.models import Chunk, Embedding


def semantic_search(
    session: Session,
    *,
    query_vector: Sequence[float],
    document_ids: Sequence[uuid.UUID],
    model: str,
    top_k: int,
) -> list[tuple[uuid.UUID, float]]:
    """Cosine benzerliğe göre en yakın chunk'ları döndürür: (chunk_id, benzerlik).

    Benzerlik = 1 − cosine mesafesi; vektörler L2-normalize olduğundan
    [-1, 1] aralığındadır. Sonuç mesafeye göre artan (benzerliğe göre azalan)
    sıralıdır — sıra RRF girdisi olarak doğrudan kullanılır.
    """
    if not document_ids or top_k <= 0:
        return []
    distance = Embedding.vector.cosine_distance(list(query_vector)).label("distance")
    statement = (
        select(Embedding.chunk_id, distance)
        .join(Chunk, Embedding.chunk_id == Chunk.id)
        .where(Embedding.model == model, Chunk.document_id.in_(list(document_ids)))
        .order_by(distance, Embedding.chunk_id)
        .limit(top_k)
    )
    return [(chunk_id, 1.0 - float(dist)) for chunk_id, dist in session.execute(statement).all()]
