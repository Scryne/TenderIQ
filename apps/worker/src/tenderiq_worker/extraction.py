"""Extracting fazı (Sprint 2.1 iskelet + Sprint 2.2 ajanlar): RAG → LLM → bulgu yazımı.

Tasarım (parsing/indexing fazlarıyla simetrik):
- Korpus + öğe indeksi tek kısa transaction'da yüklenir; uzun süren işler
  (sorgu embedding'i, BM25, rerank, LLM çağrıları) transaction DIŞINDA koşar.
  Semantik pgvector sorgusu sorgu başına kısa bir kiracı-oturumu açar.
- Embedding modeli indexing fazıyla PAYLAŞILIR (süreç başına tek BGE-M3);
  reranker ve LLM istemcisi de süreç başına tek kurulur.
- Idempotent: bulgular tek transaction'da delete+insert yazılır
  (``uq_requirement_document_seq`` / ``uq_deliverable_document_seq`` çift
  kaydı DB düzeyinde de engeller); yeniden koşum güvenlidir.
- Zorunlu grounding (ADR-0006): UNGROUNDED bulgular ``source_element_id=NULL``
  ile yazılır (gözlemlenebilirlik/eval) ama API'den dönmez.
- ``LLM_PROVIDER=none`` ise ajanlar devre dışıdır — faz 2.1 iskelet modunda
  koşar (bağlam getirimi çalışır, bulgu yazılmaz); testler/CI bu modu kullanır.
- Durumdaki ``errors`` boş değilse faz hatayla biter → Celery backoff'la
  yeniden dener (ajanlar bu kanala yalnız ölümcül sorun yazar, ADR-0005).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select

from tenderiq_core.agents import (
    AgentFinding,
    AgentName,
    AgentRunner,
    ComplianceAssessment,
    ComplianceChecker,
    ContextChunk,
    ElementView,
    GroundedSource,
    GroundingResolution,
    build_extraction_graph,
    create_extractor_runners,
    run_extraction,
)
from tenderiq_core.agents.schemas import (
    ExtractedDeliverable,
    ExtractedRequirement,
    ExtractedRisk,
    ExtractedTimelineEvent,
)
from tenderiq_core.config import get_settings
from tenderiq_core.llm import StructuredLLM, create_structured_llm
from tenderiq_core.logging import get_logger
from tenderiq_core.models import (
    CapabilityProfile,
    ComplianceResult,
    Deliverable,
    Document,
    Job,
    Requirement,
    RiskFlag,
    TimelineEvent,
)
from tenderiq_core.models import ParsedElement as ParsedElementRow
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


@dataclass(frozen=True)
class _ExtractionFindingSpec:
    """Bağlam-çıkarım bulgusunu ORM satırına çeviren sözleşme (ajan başına).

    Requirements/Deliverables/Risks/Timeline aynı grounding + idempotency
    kalıbını paylaşır; yalnız tipe özgü kolonlar (``to_columns``) değişir.
    """

    agent: AgentName
    model: type[Any]  # ORM modeli (delete+insert hedefi)
    schema: type[BaseModel]  # payload doğrulama şeması
    to_columns: Callable[[Any], dict[str, object]]  # doğrulanmış öğe → tipe özgü kolonlar


# Grafiğin ürettiği dört çıkarım bulgusu; sıra deterministik yazımı sabitler.
_EXTRACTION_SPECS: tuple[_ExtractionFindingSpec, ...] = (
    _ExtractionFindingSpec(
        agent=AgentName.REQUIREMENTS,
        model=Requirement,
        schema=ExtractedRequirement,
        to_columns=lambda i: {"text": i.text, "kind": i.kind, "is_mandatory": i.is_mandatory},
    ),
    _ExtractionFindingSpec(
        agent=AgentName.DELIVERABLES,
        model=Deliverable,
        schema=ExtractedDeliverable,
        to_columns=lambda i: {"name": i.name, "kind": i.kind, "is_mandatory": i.is_mandatory},
    ),
    _ExtractionFindingSpec(
        agent=AgentName.RISKS,
        model=RiskFlag,
        schema=ExtractedRisk,
        to_columns=lambda i: {"text": i.text, "severity": i.severity, "category": i.category},
    ),
    _ExtractionFindingSpec(
        agent=AgentName.TIMELINE,
        model=TimelineEvent,
        schema=ExtractedTimelineEvent,
        to_columns=lambda i: {"label": i.label, "kind": i.kind, "value_text": i.value_text},
    ),
)

# Süreç başına tek reranker/LLM (None = kapalı). Tuple sarmalayıcı "hiç
# yüklenmedi" (None) ile "yüklendi, kapalı" ((None,)) durumlarını ayırt eder.
_reranker_cache: tuple[Reranker | None] | None = None
_llm_cache: tuple[StructuredLLM | None] | None = None


def get_reranker() -> Reranker | None:
    """Süreç başına tek reranker döndürür (ayarlara göre; ``none`` → None)."""
    global _reranker_cache
    if _reranker_cache is None:
        _reranker_cache = (create_reranker(),)
    return _reranker_cache[0]


def get_structured_llm() -> StructuredLLM | None:
    """Süreç başına tek LLM istemcisi döndürür (``LLM_PROVIDER=none`` → None)."""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = (create_structured_llm(),)
    return _llm_cache[0]


class _GraphContextRetriever:
    """``ContextRetriever`` protokolü: HybridRetriever → graph durum tipi köprüsü."""

    def __init__(self, retriever: HybridRetriever, *, limit: int) -> None:
        self._retriever = retriever
        self._limit = limit

    def retrieve(self, queries: Sequence[str]) -> list[ContextChunk]:
        hits = self._retriever.retrieve_for_queries(queries, limit=self._limit)
        return [ContextChunk.from_retrieved(hit) for hit in hits]


def run_extraction_phase(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Bir işin dokümanı için çıkarım ajanlarını koşar ve bulguları yazar."""
    settings = get_settings()
    with tenant_session(tenant_id) as session:
        job = session.get(Job, job_id)
        document = session.get(Document, job.document_id) if job is not None else None
        if document is None:
            raise RuntimeError(f"Extracting fazı: işin dokümanı bulunamadı (job={job_id})")
        document_id = document.id
        tender_id = document.tender_id
        corpus = load_corpus(session, [document_id])
        # Grounding için öğe indeksi: seq → görünüm + seq → satır id'si
        # (bulgu FK'sı). Dönüşüm session içinde yapılır (commit sonrası expire).
        element_rows = session.execute(
            select(
                ParsedElementRow.seq,
                ParsedElementRow.id,
                ParsedElementRow.page,
                ParsedElementRow.text,
            )
            .where(ParsedElementRow.document_id == document_id)
            .order_by(ParsedElementRow.seq)
        ).all()
        elements_by_seq = {
            row.seq: ElementView(seq=row.seq, page=row.page, text=row.text) for row in element_rows
        }
        element_id_by_seq = {row.seq: row.id for row in element_rows}
        # Compliance gap analizinin girdisi: kiracının yetkinlik profili (varsa,
        # RLS gereği tekildir). Yoksa compliance atlanır (aşağıda temizlik yine yapılır).
        profile = session.scalar(select(CapabilityProfile))
        profile_content = profile.content if profile is not None else None

    if not len(corpus):
        # Indexing fazı en az bir chunk yazmadan buraya gelinemez; boş korpus
        # üst-akış tutarsızlığıdır — retry indexing'i değil bu fazı tekrarlar.
        raise RuntimeError(f"Extracting fazı: dokümanın chunk'ı yok (document={document_id})")

    embedder = get_embedder()
    reranker = get_reranker()
    llm = get_structured_llm()

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
    runners: Sequence[AgentRunner] = ()
    if llm is None:
        logger.warning("cikarim_ajanlari_devre_disi", job_id=str(job_id), provider="none")
    else:
        runners = create_extractor_runners(llm=llm, elements_by_seq=elements_by_seq)
    # Bağlam tavanı sağlayıcıya göre kısılır: Ollama'da num_ctx'i aşan bağlam
    # sessizce kırpılıp grounding'i bozardı (§6.9); geniş-pencereli Claude'da
    # yapılandırılan değer aynen kullanılır.
    context_limit = settings.effective_agent_context_limit()
    if context_limit != settings.retrieval_agent_context_limit:
        logger.info(
            "ajan_baglam_tavani_kisildi",
            configured=settings.retrieval_agent_context_limit,
            effective=context_limit,
            provider=settings.llm_provider,
            num_ctx=settings.ollama_num_ctx,
        )
    graph = build_extraction_graph(
        retriever=_GraphContextRetriever(retriever, limit=context_limit),
        runners=runners,
    )
    state = run_extraction(graph, tender_id=str(tender_id), document_id=str(document_id))

    if state.errors:
        raise RuntimeError("Extracting fazı hataları: " + "; ".join(state.errors))

    if llm is not None:
        written = _write_findings(
            tenant_id=tenant_id,
            tender_id=tender_id,
            document_id=document_id,
            findings=state.findings,
            element_id_by_seq=element_id_by_seq,
        )
        # Compliance grafiğin DIŞINDA (gereksinim çıkarımına bağımlı sıralı adım):
        # yetkinlik profili girdisi + ayrı LLM çağrısı ister. Profil yoksa yalnız
        # bayat sonuçlar temizlenir. Değerlendirme grounding'i gereksinimden devralır.
        written["compliance"] = _run_compliance(
            tenant_id=tenant_id,
            tender_id=tender_id,
            document_id=document_id,
            requirement_findings=state.findings.get(AgentName.REQUIREMENTS.value, ()),
            element_id_by_seq=element_id_by_seq,
            profile_content=profile_content,
            llm=llm,
        )
    else:
        written = {}

    # Bekleyen LLM izlerini (Langfuse) gönder: worker task'ı kısa ömürlüdür, aniden
    # sonlanırsa arka plan flush'ı yetişmeyebilir. Anahtarsız/no-op tracer'da bedelsiz.
    # Duck-typed: sahte LLM istemcilerinde (testler) ``flush`` bulunmaz → atlanır.
    flush = getattr(llm, "flush", None)
    if callable(flush):
        flush()

    logger.info(
        "cikarim_tamam",
        job_id=str(job_id),
        document_id=str(document_id),
        context_counts={agent: len(chunks) for agent, chunks in state.contexts.items()},
        finding_counts={agent: len(items) for agent, items in state.findings.items()},
        written_counts=written,
        reranker=reranker.model_name if reranker is not None else None,
        llm=llm.model_name if llm is not None else None,
        compliance_profile=profile_content is not None,
    )


def _write_findings(
    *,
    tenant_id: uuid.UUID,
    tender_id: uuid.UUID,
    document_id: uuid.UUID,
    findings: Mapping[str, Sequence[AgentFinding]],
    element_id_by_seq: Mapping[int, uuid.UUID],
) -> dict[str, int]:
    """Dört çıkarım bulgusunu tek transaction'da idempotent yazar (delete+insert)."""
    counts: dict[str, int] = {}
    with tenant_session(tenant_id) as session:
        for spec in _EXTRACTION_SPECS:
            agent_findings = list(findings.get(spec.agent.value, ()))
            session.execute(delete(spec.model).where(spec.model.document_id == document_id))
            for seq, finding in enumerate(agent_findings):
                item = spec.schema.model_validate(finding.payload)
                session.add(
                    spec.model(
                        tenant_id=tenant_id,
                        tender_id=tender_id,
                        document_id=document_id,
                        seq=seq,
                        **spec.to_columns(item),
                        **_source_columns(
                            finding.source,
                            element_id_by_seq,
                            # source_quote her ExtractedItem alt sınıfında bulunur.
                            fallback_quote=str(finding.payload.get("source_quote", "")),
                        ),
                    )
                )
            counts[spec.agent.value] = len(agent_findings)
    return counts


def _run_compliance(
    *,
    tenant_id: uuid.UUID,
    tender_id: uuid.UUID,
    document_id: uuid.UUID,
    requirement_findings: Sequence[AgentFinding],
    element_id_by_seq: Mapping[int, uuid.UUID],
    profile_content: str | None,
    llm: StructuredLLM,
) -> int:
    """Gap analizini koşar ve ComplianceResult'ları idempotent yazar (delete+insert).

    Yalnız GROUNDED gereksinimler değerlendirilir (kaynaksız/uydurma gereksinimin
    uygunluğu anlamsız); değerlendirme grounding'i gereksinimden devralır. Profil
    yoksa değerlendirme yapılmaz ama bayat sonuçlar yine temizlenir (idempotency).
    LLM çağrısı transaction DIŞINDA yapılır (parsing/indexing deseniyle simetrik).
    """
    grounded = [f for f in requirement_findings if f.source is not None and f.source.is_grounded]
    assessments: list[ComplianceAssessment] = []
    if profile_content is not None and grounded:
        checker = ComplianceChecker(llm=llm)
        assessments = checker.check(
            requirement_texts=[str(f.payload.get("text", "")) for f in grounded],
            profile_content=profile_content,
        )

    with tenant_session(tenant_id) as session:
        session.execute(delete(ComplianceResult).where(ComplianceResult.document_id == document_id))
        for seq, assessment in enumerate(assessments):
            finding = grounded[assessment.requirement_index - 1]
            session.add(
                ComplianceResult(
                    tenant_id=tenant_id,
                    tender_id=tender_id,
                    document_id=document_id,
                    seq=seq,
                    requirement_text=str(finding.payload.get("text", "")),
                    status=assessment.status,
                    rationale=assessment.rationale,
                    **_source_columns(
                        finding.source,
                        element_id_by_seq,
                        fallback_quote=str(finding.payload.get("source_quote", "")),
                    ),
                )
            )
    return len(assessments)


def _source_columns(
    source: GroundedSource | None,
    element_id_by_seq: Mapping[int, uuid.UUID],
    *,
    fallback_quote: str,
) -> dict[str, object]:
    """Grounding sonucunu ortak bulgu kolonlarına çevirir (kaynaksız → NULL)."""
    if source is None or not source.is_grounded:
        return {
            "source_element_id": None,
            "grounding_resolution": GroundingResolution.UNGROUNDED,
            "source_quote": source.quote if source is not None else fallback_quote,
        }
    element_id = (
        element_id_by_seq.get(source.element_seq) if source.element_seq is not None else None
    )
    if element_id is None:
        # Öğe indeksi ile grounding arasında tutarsızlık (beklenmez) — kaynaksız say.
        return {
            "source_element_id": None,
            "grounding_resolution": GroundingResolution.UNGROUNDED,
            "source_quote": source.quote,
        }
    return {
        "source_element_id": element_id,
        "grounding_resolution": source.resolution,
        "source_quote": source.quote,
    }
