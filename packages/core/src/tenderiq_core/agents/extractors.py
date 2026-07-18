"""Çıkarım ajanı koşucuları (Sprint 2.2): şema-zorlamalı LLM + zorunlu grounding.

``ExtractionRunner`` graph'ın ``AgentRunner`` protokolünü uygular ve üç adımı
birleştirir: (1) numaralı bağlam bloklarından istem kur, (2) LLM'den şemaya
birebir uyan çıktı al (reddet-ve-yeniden-iste ``tenderiq_core.llm``'de),
(3) her öğeyi ``agents.grounding`` ile kaynağına bağla. UNGROUNDED öğeler
bulgu olarak DÖNER (worker düşük güvenle yazar; API göstermez) — hata kanalına
yazılmaz çünkü tek öğenin bağlanamaması faz hatası değildir (ADR-0006).

Geçici LLM hataları (rate limit, 5xx) istisna olarak yükselir → graph'ın
``RetryPolicy``si düğümü yeniden dener (ADR-0005 çifte katman).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tenderiq_core.agents.context import AgentName
from tenderiq_core.agents.grounding import ElementView, ground_item
from tenderiq_core.agents.prompts import AGENT_INSTRUCTIONS, SYSTEM_PROMPT, build_context_block
from tenderiq_core.agents.schemas import (
    DeliverableExtraction,
    ExtractionResult,
    RequirementExtraction,
)
from tenderiq_core.agents.state import AgentFinding, ContextChunk
from tenderiq_core.llm import StructuredLLM
from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.agents.extractors")


class ExtractionRunner:
    """Tek ajanın koşucusu: bağlam → şemalı LLM çıktısı → grounding'li bulgular."""

    def __init__(
        self,
        *,
        name: AgentName,
        schema: type[ExtractionResult],
        llm: StructuredLLM,
        elements_by_seq: Mapping[int, ElementView],
    ) -> None:
        self._name = name
        self._schema = schema
        self._llm = llm
        self._elements_by_seq = elements_by_seq

    @property
    def name(self) -> AgentName:
        return self._name

    def run(self, context: Sequence[ContextChunk]) -> list[AgentFinding]:
        if not context:
            # Bağlam yoksa çıkaracak şey de yok; boş sonuç geçerlidir (retrieve
            # düğümü topyekûn boşluğu zaten hata kanalına yazar).
            return []
        result = self._llm.extract(
            system=SYSTEM_PROMPT,
            prompt=self._build_prompt(context),
            schema=self._schema,
        )
        findings: list[AgentFinding] = []
        for item in result.items:
            source = ground_item(
                source_index=item.source_index,
                quote=item.source_quote,
                contexts=context,
                elements_by_seq=self._elements_by_seq,
            )
            findings.append(
                AgentFinding(
                    agent=self._name.value,
                    payload=item.model_dump(mode="json"),
                    chunk_id=source.chunk_id,
                    source=source,
                )
            )
        grounded = sum(1 for f in findings if f.source is not None and f.source.is_grounded)
        logger.info(
            "ajan_cikarimi_tamam",
            agent=self._name.value,
            model=self._llm.model_name,
            item_count=len(findings),
            grounded_count=grounded,
            ungrounded_count=len(findings) - grounded,
        )
        return findings

    def _build_prompt(self, context: Sequence[ContextChunk]) -> str:
        parts = [AGENT_INSTRUCTIONS[self._name], "", "Bağlam blokları:"]
        for index, chunk in enumerate(context, start=1):
            parts.append("")
            parts.append(
                build_context_block(
                    index,
                    section=chunk.section,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
            )
            parts.append(chunk.text)
        return "\n".join(parts)


def create_extractor_runners(
    *, llm: StructuredLLM, elements_by_seq: Mapping[int, ElementView]
) -> tuple[ExtractionRunner, ...]:
    """Sprint 2.2 ajan kümesini kurar (requirements + deliverables).

    Risk/Timeline/Compliance koşucuları Sprint 2.3'te bu kümeye eklenir.
    """
    return (
        ExtractionRunner(
            name=AgentName.REQUIREMENTS,
            schema=RequirementExtraction,
            llm=llm,
            elements_by_seq=elements_by_seq,
        ),
        ExtractionRunner(
            name=AgentName.DELIVERABLES,
            schema=DeliverableExtraction,
            llm=llm,
            elements_by_seq=elements_by_seq,
        ),
    )
