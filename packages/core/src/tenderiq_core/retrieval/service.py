"""Hibrit getirim servisi (§6.6, ADR-0012): semantik + BM25 → RRF → rerank.

Akış (``HybridRetriever.retrieve``):

1. sorgu embedding'i hesaplanır (uzun süren kısım — DB oturumu DIŞINDA);
2. semantik adaylar pgvector'dan (kısa SQL), anahtar-kelime adayları
   bellekteki BM25 indeksinden gelir;
3. iki sıralı liste RRF ile birleştirilir;
4. reranker devredeyse en iyi adaylar cross-encoder ile yeniden sıralanır.

DB oturumu servise enjekte edilen ``semantic_search`` closure'ının içinde
yaşar — çağıran (worker) transaction ömrünü yönetir; birim testleri sahte
closure enjekte eder (pgvector gerekmez).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from tenderiq_core.config import Settings, get_settings
from tenderiq_core.indexing import EmbeddingModel
from tenderiq_core.models import Chunk
from tenderiq_core.retrieval.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from tenderiq_core.retrieval.keyword import Bm25Index, tokenize_tr
from tenderiq_core.retrieval.rerank import Reranker
from tenderiq_core.retrieval.types import CorpusEntry, RetrievedChunk

# (sorgu vektörü, top_k) → mesafe-sıralı (chunk_id, benzerlik) listesi.
# Varsayılan uygulama pgvector'dur (semantic.semantic_search); oturum/kapsam
# bağlama işi çağırana aittir.
SemanticSearchFn = Callable[[Sequence[float], int], list[tuple[uuid.UUID, float]]]


class RetrievalCorpus:
    """Tek ihalenin chunk korpusu: BM25 indeksi + chunk_id → metadata haritası."""

    def __init__(self, entries: Sequence[CorpusEntry]) -> None:
        self.entries: list[CorpusEntry] = list(entries)
        self._by_id: dict[uuid.UUID, CorpusEntry] = {
            entry.chunk_id: entry for entry in self.entries
        }
        # BM25, embedding ile aynı metni indeksler (bölüm başlığı dahil) —
        # iki yol aynı bağlamı görür (types.CorpusEntry.match_text).
        self.bm25 = Bm25Index([tokenize_tr(entry.match_text()) for entry in self.entries])

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, chunk_id: uuid.UUID) -> CorpusEntry | None:
        """chunk_id ile korpus girdisini döndürür (yoksa None)."""
        return self._by_id.get(chunk_id)


def load_corpus(session: Session, document_ids: Sequence[uuid.UUID]) -> RetrievalCorpus:
    """Dokümanların chunk'larını tek sorguyla korpusa yükler (RLS'ye tabi)."""
    if not document_ids:
        return RetrievalCorpus([])
    rows = session.scalars(
        select(Chunk)
        .where(Chunk.document_id.in_(list(document_ids)))
        .order_by(Chunk.document_id, Chunk.seq)
    ).all()
    return RetrievalCorpus(
        [
            CorpusEntry(
                chunk_id=row.id,
                document_id=row.document_id,
                seq=row.seq,
                text=row.text,
                section=row.section,
                page_start=row.page_start,
                page_end=row.page_end,
                element_seq_start=row.element_seq_start,
                element_seq_end=row.element_seq_end,
            )
            for row in rows
        ]
    )


class HybridRetriever:
    """Semantik + anahtar-kelime adaylarını RRF ile birleştirip (ops.) rerank'ler."""

    def __init__(
        self,
        *,
        corpus: RetrievalCorpus,
        embedder: EmbeddingModel,
        semantic_search: SemanticSearchFn,
        reranker: Reranker | None = None,
        semantic_top_k: int = 24,
        keyword_top_k: int = 24,
        rrf_k: int = DEFAULT_RRF_K,
        rerank_candidates: int = 32,
        top_n: int = 8,
    ) -> None:
        self._corpus = corpus
        self._embedder = embedder
        self._semantic_search = semantic_search
        self._reranker = reranker
        self._semantic_top_k = semantic_top_k
        self._keyword_top_k = keyword_top_k
        self._rrf_k = rrf_k
        self._rerank_candidates = rerank_candidates
        self._top_n = top_n

    @classmethod
    def from_settings(
        cls,
        *,
        corpus: RetrievalCorpus,
        embedder: EmbeddingModel,
        semantic_search: SemanticSearchFn,
        reranker: Reranker | None = None,
        settings: Settings | None = None,
    ) -> HybridRetriever:
        """Ayarlardaki RETRIEVAL_* değerleriyle retriever kurar."""
        settings = settings or get_settings()
        return cls(
            corpus=corpus,
            embedder=embedder,
            semantic_search=semantic_search,
            reranker=reranker,
            semantic_top_k=settings.retrieval_semantic_top_k,
            keyword_top_k=settings.retrieval_keyword_top_k,
            rrf_k=settings.retrieval_rrf_k,
            rerank_candidates=settings.retrieval_rerank_candidates,
            top_n=settings.retrieval_top_n,
        )

    def retrieve(self, query: str, *, top_n: int | None = None) -> list[RetrievedChunk]:
        """Tek sorgu için hibrit getirim koşar; skor-azalan sıralı sonuç döndürür."""
        limit = top_n if top_n is not None else self._top_n
        if not len(self._corpus) or limit <= 0:
            return []

        (query_vector,) = self._embedder.embed([query])
        # Korpusta olmayan id (eşzamanlı yeniden indeksleme yarışı) sessizce
        # atlanır — sıradaki adaylar yukarı kayar.
        semantic_ids = [
            chunk_id
            for chunk_id, _similarity in self._semantic_search(query_vector, self._semantic_top_k)
            if self._corpus.get(chunk_id) is not None
        ]
        keyword_ids = [
            self._corpus.entries[index].chunk_id for index, _score in self.bm25_top(query)
        ]

        fused = reciprocal_rank_fusion([semantic_ids, keyword_ids], k=self._rrf_k)
        if not fused:
            return []
        semantic_rank = {chunk_id: rank for rank, chunk_id in enumerate(semantic_ids, start=1)}
        keyword_rank = {chunk_id: rank for rank, chunk_id in enumerate(keyword_ids, start=1)}
        ordered = sorted(fused, key=lambda chunk_id: (-fused[chunk_id], self._seq_of(chunk_id)))

        if self._reranker is not None:
            candidates = ordered[: max(limit, self._rerank_candidates)]
            scores = self._reranker.rerank(
                query, [self._entry_of(chunk_id).match_text() for chunk_id in candidates]
            )
            reranked = sorted(
                zip(candidates, scores, strict=True),
                key=lambda pair: (-pair[1], self._seq_of(pair[0])),
            )
            final: list[tuple[uuid.UUID, float]] = list(reranked[:limit])
        else:
            final = [(chunk_id, fused[chunk_id]) for chunk_id in ordered[:limit]]

        return [
            RetrievedChunk(
                entry=self._entry_of(chunk_id),
                score=score,
                fused_score=fused[chunk_id],
                semantic_rank=semantic_rank.get(chunk_id),
                keyword_rank=keyword_rank.get(chunk_id),
            )
            for chunk_id, score in final
        ]

    def retrieve_for_queries(
        self, queries: Sequence[str], *, limit: int | None = None
    ) -> list[RetrievedChunk]:
        """Sorgu kümesi için birleşik bağlam üretir (chunk başına en iyi skor).

        Skorlar sorgular arasında karşılaştırılabilir (tek reranker modeli;
        reranker yoksa aynı RRF ölçeği). Sonuç skor-azalan sıralıdır ve
        ``limit`` ile kırpılır (ajan başına bağlam tavanı).
        """
        best: dict[uuid.UUID, RetrievedChunk] = {}
        for query in queries:
            for hit in self.retrieve(query):
                current = best.get(hit.entry.chunk_id)
                if current is None or hit.score > current.score:
                    best[hit.entry.chunk_id] = hit
        ranked = sorted(best.values(), key=lambda hit: (-hit.score, hit.entry.seq))
        return ranked[:limit] if limit is not None else ranked

    def bm25_top(self, query: str) -> list[tuple[int, float]]:
        """Sorgunun BM25 adaylarını (korpus indeksi, skor) döndürür."""
        return self._corpus.bm25.top(tokenize_tr(query), self._keyword_top_k)

    def _entry_of(self, chunk_id: uuid.UUID) -> CorpusEntry:
        entry = self._corpus.get(chunk_id)
        if entry is None:  # aday listeleri korpustan süzülür; buraya düşmek bug'dır
            raise KeyError(f"Chunk korpusta yok: {chunk_id}")
        return entry

    def _seq_of(self, chunk_id: uuid.UUID) -> int:
        return self._entry_of(chunk_id).seq
