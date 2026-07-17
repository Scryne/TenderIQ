"""Extracting fazı (Sprint 2.1): RAG bağlamı + LangGraph orkestrasyon iskeleti.

Tasarım (parsing/indexing fazlarıyla simetrik):
- Korpus tek kısa transaction'da yüklenir; uzun süren işler (sorgu embedding'i,
  BM25, rerank, graph) transaction DIŞINDA koşar. Semantik pgvector sorgusu
  sorgu başına kısa bir kiracı-oturumu açar (closure — çekirdek, oturum
  yönetimini bilmez).
- Embedding modeli indexing fazıyla PAYLAŞILIR (``worker_indexing.get_embedder``,
  süreç başına tek BGE-M3); reranker da süreç başına tek yüklenir.
- Idempotent: Sprint 2.1 iskeleti DB'ye yazmaz (bulgular Sprint 2.2'de
  delete+insert deseniyle yazılacak); yeniden koşum güvenlidir.
- Durumdaki ``errors`` boş değilse faz hatayla biter → Celery backoff'la
  yeniden dener (ajanlar bu kanala yalnız ölümcül sorun yazar, ADR-0005).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from tenderiq_core.agents import ContextChunk, build_extraction_graph, run_extraction
from tenderiq_core.config import get_settings
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Document, Job
from tenderiq_core.retrieval import (
    HybridRetriever,
    Reranker,
    create_reranker,
    load_corpus,
    semantic_search,
)
from tenderiq_worker.db import tenant_session
from tenderiq_worker.indexing import get_embedder

logger = get_logger("tenderiq.worker.extraction")

# Süreç başına tek reranker (None = kapalı). Tuple sarmalayıcı "hiç yüklenmedi"
# (None) ile "yüklendi, kapalı" ((None,)) durumlarını ayırt eder.
_reranker_cache: tuple[Reranker | None] | None = None


def get_reranker() -> Reranker | None:
    """Süreç başına tek reranker döndürür (ayarlara göre; ``none`` → None)."""
    global _reranker_cache
    if _reranker_cache is None:
        _reranker_cache = (create_reranker(),)
    return _reranker_cache[0]


class _GraphContextRetriever:
    """``ContextRetriever`` protokolü: HybridRetriever → graph durum tipi köprüsü."""

    def __init__(self, retriever: HybridRetriever, *, limit: int) -> None:
        self._retriever = retriever
        self._limit = limit

    def retrieve(self, queries: Sequence[str]) -> list[ContextChunk]:
        hits = self._retriever.retrieve_for_queries(queries, limit=self._limit)
        return [ContextChunk.from_retrieved(hit) for hit in hits]


def run_extraction_phase(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Bir işin dokümanı için çıkarım orkestrasyonunu koşar (2.1: bağlam iskeleti)."""
    settings = get_settings()
    with tenant_session(tenant_id) as session:
        job = session.get(Job, job_id)
        document = session.get(Document, job.document_id) if job is not None else None
        if document is None:
            raise RuntimeError(f"Extracting fazı: işin dokümanı bulunamadı (job={job_id})")
        document_id = document.id
        tender_id = document.tender_id
        corpus = load_corpus(session, [document_id])

    if not len(corpus):
        # Indexing fazı en az bir chunk yazmadan buraya gelinemez; boş korpus
        # üst-akış tutarsızlığıdır — retry indexing'i değil bu fazı tekrarlar.
        raise RuntimeError(f"Extracting fazı: dokümanın chunk'ı yok (document={document_id})")

    embedder = get_embedder()
    reranker = get_reranker()

    def _semantic(query_vector: Sequence[float], top_k: int) -> list[tuple[uuid.UUID, float]]:
        # Sorgu başına kısa oturum: pgvector HNSW sorgusu hızlıdır, uzun süren
        # embedding/rerank hesabı bu oturumun dışında kalır.
        with tenant_session(tenant_id) as session:
            return semantic_search(
                session,
                query_vector=query_vector,
                document_ids=[document_id],
                model=embedder.model_name,
                top_k=top_k,
            )

    retriever = HybridRetriever.from_settings(
        corpus=corpus,
        embedder=embedder,
        semantic_search=_semantic,
        reranker=reranker,
        settings=settings,
    )
    graph = build_extraction_graph(
        retriever=_GraphContextRetriever(retriever, limit=settings.retrieval_agent_context_limit),
        runners=(),  # Sprint 2.2: Requirement/Deliverables Extractor buraya kaydolur
    )
    state = run_extraction(graph, tender_id=str(tender_id), document_id=str(document_id))

    if state.errors:
        raise RuntimeError("Extracting fazı hataları: " + "; ".join(state.errors))

    logger.info(
        "cikarim_iskeleti_tamam",
        job_id=str(job_id),
        document_id=str(document_id),
        context_counts={agent: len(chunks) for agent, chunks in state.contexts.items()},
        reranker=reranker.model_name if reranker is not None else None,
    )
