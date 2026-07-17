"""Indexing fazı (Sprint 1.3): öğeleri oku → chunk → embed → pgvector'a yaz.

Tasarım (parsing fazıyla simetrik):
- Uzun süren embedding hesabı **transaction dışında** yapılır; DB'ye yalnızca
  sonuç yazılırken bağlanılır (SSE poll'u ve bağlantı havuzu bloklanmaz).
- Idempotent: yeniden koşumda dokümanın mevcut chunk'ları tek transaction'da
  silinip yeniden yazılır; embedding'ler FK cascade ile birlikte gider
  (``uq_chunk_document_seq`` çift kaydı ayrıca DB düzeyinde engeller).
- Embedding modeli süreç başına tekildir (BGE-M3 bir kez yüklenir, task'lar
  arası yeniden kullanılır); testler ``_embedder``'ı monkeypatch'ler.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select

from tenderiq_core.config import get_settings
from tenderiq_core.indexing import (
    ChunkDraft,
    EmbeddingModel,
    chunk_elements,
    create_embedding_model,
)
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Chunk, Document, Embedding, Job
from tenderiq_core.models import ParsedElement as ParsedElementRow
from tenderiq_core.parsing import ParsedElement
from tenderiq_worker.db import tenant_session

logger = get_logger("tenderiq.worker.indexing")

_embedder: EmbeddingModel | None = None


def get_embedder() -> EmbeddingModel:
    """Süreç başına tek embedding modeli döndürür (lazy; BGE-M3 bir kez yüklenir)."""
    global _embedder
    if _embedder is None:
        _embedder = create_embedding_model()
    return _embedder


def run_indexing_phase(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Bir işin dokümanını chunk'layıp gömer ve pgvector'a yazar."""
    settings = get_settings()
    with tenant_session(tenant_id) as session:
        job = session.get(Job, job_id)
        document = session.get(Document, job.document_id) if job is not None else None
        if document is None:
            raise RuntimeError(f"Indexing fazı: işin dokümanı bulunamadı (job={job_id})")
        document_id = document.id
        rows = session.scalars(
            select(ParsedElementRow)
            .where(ParsedElementRow.document_id == document_id)
            .order_by(ParsedElementRow.seq)
        ).all()
        # Sözleşme tipine dönüşüm session içinde yapılır (commit sonrası ORM
        # satırları expire olur); element_seqs chunk→öğe çevirisi içindir.
        elements = [
            ParsedElement(text=row.text, page=row.page, kind=row.kind, section=row.section)
            for row in rows
        ]
        element_seqs = [row.seq for row in rows]

    if not elements:
        # Parse fazı kalite kapısı boş çıktıyı reddeder; buraya düşmek parse
        # verisinin yazılmadığını gösterir — retry parse'ı değil bu fazı tekrarlar,
        # o yüzden kalıcı hata mesajıyla yükselt.
        raise RuntimeError(f"Indexing fazı: dokümanın parse öğesi yok (document={document_id})")

    drafts = chunk_elements(
        elements,
        max_chars=settings.indexing_chunk_max_chars,
        overlap_chars=settings.indexing_chunk_overlap_chars,
    )
    embedder = get_embedder()
    vectors = embedder.embed([draft.embedding_input() for draft in drafts])

    with tenant_session(tenant_id) as session:
        session.execute(delete(Chunk).where(Chunk.document_id == document_id))
        for draft, vector in zip(drafts, vectors, strict=True):
            chunk_id = uuid.uuid4()  # embedding FK'sı için istemci tarafında üretilir
            session.add(_to_chunk_row(draft, chunk_id, document_id, tenant_id, element_seqs))
            session.add(
                Embedding(
                    tenant_id=tenant_id,
                    chunk_id=chunk_id,
                    model=embedder.model_name,
                    vector=vector,
                )
            )

    logger.info(
        "indeksleme_tamam",
        job_id=str(job_id),
        document_id=str(document_id),
        chunk_count=len(drafts),
        model=embedder.model_name,
        dim=embedder.dim,
    )


def _to_chunk_row(
    draft: ChunkDraft,
    chunk_id: uuid.UUID,
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
    element_seqs: list[int],
) -> Chunk:
    """Chunk taslağını ORM satırına çevirir (öğe indeksleri gerçek seq'lere çevrilir)."""
    return Chunk(
        id=chunk_id,
        tenant_id=tenant_id,
        document_id=document_id,
        seq=draft.seq,
        text=draft.text,
        section=draft.section,
        page_start=draft.page_start,
        page_end=draft.page_end,
        element_seq_start=element_seqs[draft.element_start],
        element_seq_end=element_seqs[draft.element_end],
    )
