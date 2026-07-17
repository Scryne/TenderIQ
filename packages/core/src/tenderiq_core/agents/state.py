"""LangGraph çıkarım graph'ının durumu (§6.7) — şema-önce (C.8).

Durum pydantic'tir (serileştirilebilir; graph checkpointing'e hazır) ve
paralel ajan düğümleri için reducer'lıdır: her ajan YALNIZ kendi anahtarına
bulgu yazar (``findings`` sözlük-birleşimi), hatalar liste-birleşimiyle
toplanır. ``contexts`` tek yazarlıdır (retrieve düğümü) — reducer gerekmez.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any

from pydantic import BaseModel, Field

from tenderiq_core.retrieval.types import RetrievedChunk


class ContextChunk(BaseModel):
    """Graph durumunda taşınan getirim sonucu — ``RetrievedChunk``'ın izdüşümü.

    Citation zinciri eksiksiz taşınır (chunk → öğe ``seq`` aralığı → sayfa);
    Sprint 2.2 grounding'i bulguları bu alanlar üzerinden kaynağa bağlar.
    """

    chunk_id: str
    document_id: str
    seq: int
    text: str
    section: str | None = None
    page_start: int
    page_end: int
    element_seq_start: int
    element_seq_end: int
    score: float

    @classmethod
    def from_retrieved(cls, hit: RetrievedChunk) -> ContextChunk:
        """Getirim sonucunu durum tipine çevirir."""
        return cls(
            chunk_id=str(hit.entry.chunk_id),
            document_id=str(hit.entry.document_id),
            seq=hit.entry.seq,
            text=hit.entry.text,
            section=hit.entry.section,
            page_start=hit.entry.page_start,
            page_end=hit.entry.page_end,
            element_seq_start=hit.entry.element_seq_start,
            element_seq_end=hit.entry.element_seq_end,
            score=hit.score,
        )


class AgentFinding(BaseModel):
    """İskelet bulgu zarfı (Sprint 2.1).

    Sprint 2.2'de yerini tipli şemalar (Requirement/Deliverable...) + zorunlu
    ``ParsedElement`` grounding'i alır; zarf o güne dek ajan koşucularının
    sözleşmesini sabitler.
    """

    agent: str
    payload: dict[str, Any] = Field(default_factory=dict)
    chunk_id: str | None = None  # bulgunun dayandığı bağlam chunk'ı (varsa)


def merge_finding_maps(
    left: dict[str, list[AgentFinding]], right: dict[str, list[AgentFinding]]
) -> dict[str, list[AgentFinding]]:
    """Paralel ajan çıktılarını birleştirir; aynı anahtara yazımlar art arda eklenir."""
    merged = dict(left)
    for agent, findings in right.items():
        merged[agent] = [*merged.get(agent, []), *findings]
    return merged


class ExtractionState(BaseModel):
    """Çıkarım orkestrasyonunun graph durumu."""

    tender_id: str
    document_id: str
    # ajan adı → skor-sıralı bağlam parçaları (retrieve düğümü yazar).
    contexts: dict[str, list[ContextChunk]] = Field(default_factory=dict)
    # ajan adı → bulgular (paralel düğümler; reducer birleştirir).
    findings: Annotated[dict[str, list[AgentFinding]], merge_finding_maps] = Field(
        default_factory=dict
    )
    # Ölümcül olmayan sorunlar (ör. 2.2'de grounding reddi); orkestratör
    # boş-olmayan errors'ı faz hatası sayar — bkz. worker extraction.
    errors: Annotated[list[str], operator.add] = Field(default_factory=list)
