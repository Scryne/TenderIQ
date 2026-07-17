"""LangGraph çıkarım iskeleti testleri — sahte getirim/koşucularla (§6.7)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import pytest
from langgraph.types import RetryPolicy

from tenderiq_core.agents import (
    AgentFinding,
    AgentName,
    ContextChunk,
    build_extraction_graph,
    run_extraction,
)
from tenderiq_core.agents.state import ExtractionState, merge_finding_maps
from tenderiq_core.retrieval import CorpusEntry, RetrievedChunk


def _chunk(seq: int, text: str, score: float = 1.0) -> ContextChunk:
    return ContextChunk.from_retrieved(
        RetrievedChunk(
            entry=CorpusEntry(
                chunk_id=uuid.UUID(int=seq + 1),
                document_id=uuid.UUID(int=500),
                seq=seq,
                text=text,
                section="Madde",
                page_start=seq + 1,
                page_end=seq + 1,
                element_seq_start=seq * 10,
                element_seq_end=seq * 10 + 3,
            ),
            score=score,
            fused_score=score,
            semantic_rank=1,
            keyword_rank=None,
        )
    )


class FakeRetriever:
    """Sorguları kaydeder; sabit bağlam döndürür."""

    def __init__(self, chunks: list[ContextChunk] | None = None) -> None:
        self.chunks = chunks if chunks is not None else [_chunk(0, "geçici teminat %3")]
        self.calls: list[tuple[str, ...]] = []

    def retrieve(self, queries: Sequence[str]) -> list[ContextChunk]:
        self.calls.append(tuple(queries))
        return list(self.chunks)


class EchoRunner:
    """Bağlamdaki her chunk için bir bulgu üretir."""

    def __init__(self, name: AgentName) -> None:
        self._name = name

    @property
    def name(self) -> AgentName:
        return self._name

    def run(self, context: Sequence[ContextChunk]) -> list[AgentFinding]:
        return [
            AgentFinding(agent=self._name.value, payload={"text": c.text}, chunk_id=c.chunk_id)
            for c in context
        ]


class FailingRunner(EchoRunner):
    def run(self, context: Sequence[ContextChunk]) -> list[AgentFinding]:
        raise RuntimeError("LLM zaman aşımı (sahte)")


def test_kosucusuz_iskelet_baglami_getirir() -> None:
    retriever = FakeRetriever()
    graph = build_extraction_graph(retriever=retriever)
    state = run_extraction(graph, tender_id="t-1", document_id="d-1")
    # Dört ajan şablonunun tümü için bağlam getirilmiş olmalı.
    assert set(state.contexts) == {agent.value for agent in AgentName}
    assert len(retriever.calls) == len(AgentName)
    assert state.findings == {}
    assert state.errors == []


def test_kayitli_kosucular_paralel_calisir_ve_bulgular_birlesir() -> None:
    retriever = FakeRetriever()
    graph = build_extraction_graph(
        retriever=retriever,
        runners=[EchoRunner(AgentName.REQUIREMENTS), EchoRunner(AgentName.RISKS)],
    )
    state = run_extraction(graph, tender_id="t-1", document_id="d-1")
    assert set(state.findings) == {"requirements", "risks"}
    assert state.findings["requirements"][0].chunk_id == str(uuid.UUID(int=1))
    assert state.errors == []


def test_bos_baglam_hata_kanalina_yazilir() -> None:
    graph = build_extraction_graph(retriever=FakeRetriever(chunks=[]))
    state = run_extraction(graph, tender_id="t-1", document_id="d-1")
    assert state.errors
    assert "bağlam getirilemedi" in state.errors[0]


def test_kosucu_hatasi_yukselir() -> None:
    # Kalıcı ajan hatası graph'tan yükselir → Celery faz retry'ı devralır (ADR-0005).
    graph = build_extraction_graph(
        retriever=FakeRetriever(),
        runners=[FailingRunner(AgentName.TIMELINE)],
        agent_retry=RetryPolicy(max_attempts=1),  # testte bekleme olmasın
    )
    with pytest.raises(RuntimeError, match="zaman aşımı"):
        run_extraction(graph, tender_id="t-1", document_id="d-1")


def test_ayni_ada_iki_kosucu_reddedilir() -> None:
    with pytest.raises(ValueError, match="birden çok"):
        build_extraction_graph(
            retriever=FakeRetriever(),
            runners=[EchoRunner(AgentName.RISKS), EchoRunner(AgentName.RISKS)],
        )


def test_bulgu_birlestirici() -> None:
    left = {"a": [AgentFinding(agent="a")]}
    right = {"a": [AgentFinding(agent="a", payload={"k": 1})], "b": [AgentFinding(agent="b")]}
    merged = merge_finding_maps(left, right)
    assert len(merged["a"]) == 2
    assert len(merged["b"]) == 1
    assert len(left["a"]) == 1  # girdiler mutasyona uğramaz


def test_durum_dogrulanabilir() -> None:
    state = ExtractionState(tender_id="t", document_id="d")
    assert state.contexts == {}
    assert state.findings == {}
