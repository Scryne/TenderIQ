"""LangGraph çıkarım orkestrasyon iskeleti (§6.7, ADR-0005).

Graph şekli::

    START → retrieve_context → agent_<ad> (paralel, kayıtlı koşucu başına)
                             ↘ (koşucu yoksa doğrudan) ↘
                               finalize → END

Tasarım kararları:
- **Bağımlılık enjeksiyonu:** getirim ve ajan koşucuları protokol olarak
  enjekte edilir — graph LLM'e, DB'ye, embedding'e doğrudan bağlanmaz;
  birim testleri sahtelerle koşar.
- **Yeniden denenebilirlik:** ajan düğümleri ``RetryPolicy`` taşır (2.2'de
  LLM'in geçici hataları için); kalıcı hata düğümden yükselir → orkestratör
  (Celery task) kendi backoff'uyla TÜM FAZI idempotent yeniden dener.
- **Hata kanalı:** ölümcül olmayan sorunlar durumdaki ``errors`` listesinde
  birikir (reducer'lı); istisna fırlatmak yalnızca yeniden denemeye değer
  durumlar içindir.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from langgraph.graph import END, START, StateGraph
from langgraph.graph._node import StateNode  # tip-düzeyi alias; public re-export yok
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from tenderiq_core.agents.context import AGENT_QUERY_TEMPLATES, AgentName
from tenderiq_core.agents.state import AgentFinding, ContextChunk, ExtractionState
from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.agents.graph")

# LLM geçici hataları (rate limit, ağ) için düğüm-içi yeniden deneme; kalıcı
# hata Celery'nin faz-düzeyi retry'ına yükselir (çifte katman — ADR-0005).
DEFAULT_AGENT_RETRY = RetryPolicy(max_attempts=3, initial_interval=1.0, backoff_factor=2.0)

_RETRIEVE_NODE = "retrieve_context"
_FINALIZE_NODE = "finalize"


class ContextRetriever(Protocol):
    """Getirim sözleşmesi: sorgu kümesi → skor-sıralı, tekilleştirilmiş bağlam."""

    def retrieve(self, queries: Sequence[str]) -> list[ContextChunk]:
        """Sorguların birleşik bağlamını döndürür (ajan başına tavan uygulanmış)."""
        ...


class AgentRunner(Protocol):
    """Ajan koşucusu sözleşmesi — Sprint 2.2'de LLM'li uygulamalar kaydolur."""

    @property
    def name(self) -> AgentName:
        """Ajanın adı (bağlam ve bulgu anahtarı)."""
        ...

    def run(self, context: Sequence[ContextChunk]) -> list[AgentFinding]:
        """Bağlamdan bulgu üretir; geçici hatada istisna yükseltebilir (retry)."""
        ...


def build_extraction_graph(
    *,
    retriever: ContextRetriever,
    runners: Sequence[AgentRunner] = (),
    agent_queries: Mapping[AgentName, tuple[str, ...]] = AGENT_QUERY_TEMPLATES,
    agent_retry: RetryPolicy = DEFAULT_AGENT_RETRY,
) -> CompiledStateGraph[ExtractionState]:
    """Çıkarım graph'ını kurar ve derler.

    Koşucu kümesi derleme anında sabitlenir (deterministik topoloji); bağlam
    TÜM ajan şablonları için getirilir — henüz koşucusu olmayan ajanın bağlam
    kalitesi de gözlemlenebilir (2.1 iskelet amacı).
    """
    duplicate_names = [runner.name for runner in runners]
    if len(duplicate_names) != len(set(duplicate_names)):
        raise ValueError(f"Aynı ada birden çok ajan koşucusu kayıtlı: {duplicate_names}")

    def retrieve_context(state: ExtractionState) -> dict[str, object]:
        contexts = {
            agent.value: [] if not queries else list(retriever.retrieve(queries))
            for agent, queries in agent_queries.items()
        }
        update: dict[str, object] = {"contexts": contexts}
        if not any(contexts.values()):
            # İndekslenmiş dokümandan hiç bağlam gelmemesi üst-akış tutarsızlığıdır;
            # ölümcül kararı orkestratör verir (errors → faz hatası).
            update["errors"] = ["retrieve_context: hiçbir ajan için bağlam getirilemedi"]
        return update

    def finalize(state: ExtractionState) -> dict[str, object]:
        logger.info(
            "cikarim_graph_tamam",
            tender_id=state.tender_id,
            document_id=state.document_id,
            context_counts={agent: len(chunks) for agent, chunks in state.contexts.items()},
            finding_counts={agent: len(items) for agent, items in state.findings.items()},
            error_count=len(state.errors),
        )
        return {}

    builder: StateGraph[ExtractionState] = StateGraph(ExtractionState)
    builder.add_node(_RETRIEVE_NODE, retrieve_context)
    builder.add_node(_FINALIZE_NODE, finalize)
    builder.add_edge(START, _RETRIEVE_NODE)
    if runners:
        for runner in runners:
            node_name = f"agent_{runner.name.value}"
            builder.add_node(node_name, _make_agent_node(runner), retry_policy=agent_retry)
            builder.add_edge(_RETRIEVE_NODE, node_name)  # paralel fan-out
            builder.add_edge(node_name, _FINALIZE_NODE)
    else:
        builder.add_edge(_RETRIEVE_NODE, _FINALIZE_NODE)
    builder.add_edge(_FINALIZE_NODE, END)
    return builder.compile()


def run_extraction(
    graph: CompiledStateGraph[ExtractionState], *, tender_id: str, document_id: str
) -> ExtractionState:
    """Graph'ı baştan sona koşar ve doğrulanmış nihai durumu döndürür."""
    raw = graph.invoke(ExtractionState(tender_id=tender_id, document_id=document_id))
    return ExtractionState.model_validate(raw)


def _make_agent_node(runner: AgentRunner) -> StateNode[ExtractionState, None]:
    def run_agent(state: ExtractionState) -> dict[str, object]:
        context = state.contexts.get(runner.name.value, [])
        findings = runner.run(context)
        return {"findings": {runner.name.value: findings}}

    run_agent.__name__ = f"agent_{runner.name.value}"
    return run_agent
