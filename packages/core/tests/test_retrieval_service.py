"""HybridRetriever birim testleri — pgvector/model olmadan (sahte enjeksiyonlarla).

Semantik yol enjekte edilen closure ile, embedding sahte modelle taklit edilir;
BM25 ve RRF gerçektir. Gerçek pgvector yolu entegrasyon testindedir
(apps/api/tests/integration/test_upload_pipeline_flow.py).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from tenderiq_core.config import Settings
from tenderiq_core.retrieval import (
    CorpusEntry,
    HybridRetriever,
    RerankerProvider,
    RetrievalCorpus,
    create_reranker,
)

TEXTS = [
    "Madde 26 - Geçici teminat: teklif bedelinin %3'ü oranında geçici teminat verilir.",
    "Madde 33 - Cezai şart: gecikme cezası sözleşme bedelinin %0,05'i oranındadır.",
    "İstekliler iş deneyim belgesi ve iş bitirme belgesi sunacaktır.",
    "Sistem 7x24 çalışacak; SLA kapsamında müdahale süresi iki saati aşamaz.",
]


def _corpus() -> RetrievalCorpus:
    return RetrievalCorpus(
        [
            CorpusEntry(
                chunk_id=uuid.UUID(int=index + 1),
                document_id=uuid.UUID(int=1000),
                seq=index,
                text=text,
                section=None,
                page_start=index + 1,
                page_end=index + 1,
                element_seq_start=index * 10,
                element_seq_end=index * 10 + 5,
            )
            for index, text in enumerate(TEXTS)
        ]
    )


class FakeEmbedder:
    """Sabit boyutlu deterministik vektörler (içerik önemsiz — semantik yol enjekte)."""

    model_name = "fake-embedder"
    dim = 4

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class FakeReranker:
    """Metin uzunluğuna göre skorlar — sırayı bilinçli tersine çevirebilir."""

    model_name = "fake-reranker"

    def __init__(self, scores_by_text: dict[str, float]) -> None:
        self._scores = scores_by_text

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        return [self._scores.get(text, 0.0) for text in texts]


def _retriever(
    corpus: RetrievalCorpus,
    semantic_ids: list[uuid.UUID],
    reranker: FakeReranker | None = None,
) -> HybridRetriever:
    def fake_semantic(query_vector: Sequence[float], top_k: int) -> list[tuple[uuid.UUID, float]]:
        return [(chunk_id, 0.9 - 0.1 * rank) for rank, chunk_id in enumerate(semantic_ids)][:top_k]

    return HybridRetriever(
        corpus=corpus,
        embedder=FakeEmbedder(),
        semantic_search=fake_semantic,
        reranker=reranker,
        top_n=3,
    )


def test_iki_yoldan_gelen_chunk_one_cikar() -> None:
    corpus = _corpus()
    # Semantik yol 1 (cezai şart) ve 0'ı (geçici teminat) döndürür; sorgu
    # "geçici teminat" BM25'te 0'ı bulur → 0 iki listede birden geçer, öne çıkar.
    retriever = _retriever(corpus, [uuid.UUID(int=2), uuid.UUID(int=1)])
    hits = retriever.retrieve("geçici teminat oranı")
    assert hits[0].entry.seq == 0
    assert hits[0].semantic_rank == 2
    assert hits[0].keyword_rank == 1
    assert hits[0].score == hits[0].fused_score  # reranker yok → RRF skoru nihaidir


def test_yalniz_semantik_yol_calisir() -> None:
    corpus = _corpus()
    retriever = _retriever(corpus, [uuid.UUID(int=4)])
    hits = retriever.retrieve("tamamen alakasız bir sorgu metni")
    assert [hit.entry.seq for hit in hits] == [3]
    assert hits[0].keyword_rank is None


def test_korpusta_olmayan_semantik_aday_atlanir() -> None:
    corpus = _corpus()
    hayalet = uuid.UUID(int=999)  # eşzamanlı yeniden indeksleme yarışı senaryosu
    retriever = _retriever(corpus, [hayalet, uuid.UUID(int=3)])
    hits = retriever.retrieve("iş deneyim belgesi")
    assert hayalet not in {hit.entry.chunk_id for hit in hits}
    assert hits[0].entry.seq == 2


def test_reranker_nihai_sirayi_belirler() -> None:
    corpus = _corpus()
    # Reranker SLA chunk'ına en yüksek skoru verir — RRF sırasını ezer.
    reranker = FakeReranker({corpus.entries[3].match_text(): 5.0})
    retriever = _retriever(corpus, [uuid.UUID(int=1), uuid.UUID(int=4)], reranker=reranker)
    hits = retriever.retrieve("geçici teminat")
    assert hits[0].entry.seq == 3
    assert hits[0].score == 5.0
    assert hits[0].fused_score < 5.0  # RRF skoru ayrıca korunur (izlenebilirlik)


def test_bos_korpus_bos_doner() -> None:
    retriever = _retriever(RetrievalCorpus([]), [])
    assert retriever.retrieve("geçici teminat") == []


def test_coklu_sorgu_birlesimi_tekillestirir_ve_kirpar() -> None:
    corpus = _corpus()
    retriever = _retriever(corpus, [uuid.UUID(int=1), uuid.UUID(int=2)])
    hits = retriever.retrieve_for_queries(
        ["geçici teminat oranı", "cezai şart gecikme cezası", "geçici teminat süresi"],
        limit=2,
    )
    assert len(hits) == 2
    chunk_ids = [hit.entry.chunk_id for hit in hits]
    assert len(chunk_ids) == len(set(chunk_ids))  # tekil
    # Her iki sorguda da geçen chunk'lar (0 ve 1) bağlamda olmalı.
    assert {hit.entry.seq for hit in hits} == {0, 1}


def test_create_reranker_none_saglayici() -> None:
    settings = Settings(retrieval_reranker_provider=RerankerProvider.NONE.value)
    assert create_reranker(settings) is None
