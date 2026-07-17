"""Extracting fazı birim testleri (DB'siz — köprü ve süreç-tekil reranker)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import pytest

import tenderiq_worker.extraction as worker_extraction
from tenderiq_core.retrieval import CorpusEntry, RetrievedChunk
from tenderiq_worker.extraction import _GraphContextRetriever, get_reranker


class StubHybridRetriever:
    """retrieve_for_queries sözleşmesinin kaydedici eşleniği."""

    def __init__(self, hits: list[RetrievedChunk]) -> None:
        self._hits = hits
        self.calls: list[tuple[tuple[str, ...], int | None]] = []

    def retrieve_for_queries(
        self, queries: Sequence[str], *, limit: int | None = None
    ) -> list[RetrievedChunk]:
        self.calls.append((tuple(queries), limit))
        return self._hits


def _hit(seq: int) -> RetrievedChunk:
    return RetrievedChunk(
        entry=CorpusEntry(
            chunk_id=uuid.UUID(int=seq + 1),
            document_id=uuid.UUID(int=99),
            seq=seq,
            text="Geçici teminat %3'tür.",
            section="Madde 26",
            page_start=4,
            page_end=4,
            element_seq_start=40,
            element_seq_end=42,
        ),
        score=0.5,
        fused_score=0.5,
        semantic_rank=1,
        keyword_rank=None,
    )


def test_graph_context_retriever_kopru_ve_tavan() -> None:
    stub = StubHybridRetriever([_hit(0)])
    bridge = _GraphContextRetriever(stub, limit=12)  # type: ignore[arg-type]
    chunks = bridge.retrieve(["geçici teminat oranı", "kesin teminat"])
    assert stub.calls == [(("geçici teminat oranı", "kesin teminat"), 12)]
    # Citation zinciri graph durum tipine eksiksiz taşınır.
    assert chunks[0].chunk_id == str(uuid.UUID(int=1))
    assert chunks[0].section == "Madde 26"
    assert (chunks[0].element_seq_start, chunks[0].element_seq_end) == (40, 42)
    assert chunks[0].score == 0.5


def test_get_reranker_surec_basina_bir_kez_kurulur(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(worker_extraction, "_reranker_cache", None)
    monkeypatch.setattr(worker_extraction, "create_reranker", lambda: calls.append(1) or None)
    assert get_reranker() is None
    assert get_reranker() is None
    # "yüklendi, kapalı" (None) durumu önbelleğe alınır — fabrika tek kez çağrılır.
    assert calls == [1]
