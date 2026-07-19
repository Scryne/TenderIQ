"""Extractor ajan koşucusu testleri — sahte LLM'le (Sprint 2.2, §6.7)."""

from __future__ import annotations

import uuid
from typing import Any

from tenderiq_core.agents import (
    AgentName,
    ContextChunk,
    ElementView,
    GroundingResolution,
    create_extractor_runners,
)
from tenderiq_core.agents.schemas import (
    DeliverableExtraction,
    RequirementExtraction,
    RiskExtraction,
    TimelineExtraction,
)
from tenderiq_core.retrieval import CorpusEntry, RetrievedChunk

_ELEMENTS = {
    5: ElementView(seq=5, page=2, text="İstekliler ISO 9001 kalite belgesi sunmak zorundadır."),
}


def _chunk() -> ContextChunk:
    return ContextChunk.from_retrieved(
        RetrievedChunk(
            entry=CorpusEntry(
                chunk_id=uuid.UUID(int=3),
                document_id=uuid.UUID(int=42),
                seq=0,
                text=_ELEMENTS[5].text,
                section="Madde 7",
                page_start=2,
                page_end=2,
                element_seq_start=5,
                element_seq_end=5,
            ),
            score=0.9,
            fused_score=0.9,
            semantic_rank=1,
            keyword_rank=1,
        )
    )


class FakeLLM:
    """extract çağrılarını kaydeder; şemaya göre önceden kurulmuş sonucu döndürür."""

    model_name = "fake-llm"

    def __init__(self, results: dict[type, Any]) -> None:
        self._results = results
        self.calls: list[dict[str, Any]] = []

    def extract(self, *, system: str, prompt: str, schema: type) -> Any:
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        return self._results[schema]


def _runners(llm: FakeLLM) -> dict[AgentName, Any]:
    return {r.name: r for r in create_extractor_runners(llm=llm, elements_by_seq=_ELEMENTS)}


def test_dort_ajan_kurulur() -> None:
    llm = FakeLLM({})
    names = set(_runners(llm))
    assert names == {
        AgentName.REQUIREMENTS,
        AgentName.DELIVERABLES,
        AgentName.RISKS,
        AgentName.TIMELINE,
    }


def test_gecerli_alinti_grounded_bulgu_uretir() -> None:
    llm = FakeLLM(
        {
            RequirementExtraction: RequirementExtraction.model_validate(
                {
                    "items": [
                        {
                            "text": "ISO 9001 kalite belgesi sunulmalıdır.",
                            "kind": "administrative",
                            "is_mandatory": True,
                            "source_index": 1,
                            "source_quote": "ISO 9001 kalite belgesi sunmak zorundadır",
                        }
                    ]
                }
            )
        }
    )
    runner = _runners(llm)[AgentName.REQUIREMENTS]
    findings = runner.run([_chunk()])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.agent == "requirements"
    assert finding.payload["kind"] == "administrative"
    assert finding.source is not None
    assert finding.source.resolution is GroundingResolution.ELEMENT
    assert finding.source.element_seq == 5
    assert finding.chunk_id == str(uuid.UUID(int=3))


def test_uydurma_alinti_dusuk_guven_isaretlenir() -> None:
    llm = FakeLLM(
        {
            RequirementExtraction: RequirementExtraction.model_validate(
                {
                    "items": [
                        {
                            "text": "Sunucular %99,9 erişilebilirlik sağlamalıdır.",
                            "kind": "technical",
                            "is_mandatory": True,
                            "source_index": 1,
                            "source_quote": "yüzde 99,9 erişilebilirlik SLA'sı",  # kaynakta yok
                        }
                    ]
                }
            )
        }
    )
    runner = _runners(llm)[AgentName.REQUIREMENTS]
    findings = runner.run([_chunk()])
    assert len(findings) == 1
    assert findings[0].source is not None
    assert findings[0].source.resolution is GroundingResolution.UNGROUNDED
    assert findings[0].chunk_id is None


def test_deliverables_kosucusu_kendi_semasini_kullanir() -> None:
    llm = FakeLLM(
        {
            DeliverableExtraction: DeliverableExtraction.model_validate(
                {
                    "items": [
                        {
                            "name": "ISO 9001 Kalite Yönetim Sistemi Belgesi",
                            "kind": "certificate",
                            "is_mandatory": True,
                            "source_index": 1,
                            "source_quote": "ISO 9001 kalite belgesi sunmak zorundadır",
                        }
                    ]
                }
            )
        }
    )
    runner = _runners(llm)[AgentName.DELIVERABLES]
    findings = runner.run([_chunk()])
    assert llm.calls[0]["schema"] is DeliverableExtraction
    assert findings[0].payload["name"].startswith("ISO 9001")
    assert findings[0].source is not None
    assert findings[0].source.is_grounded


def test_risks_kosucusu_kendi_semasini_kullanir() -> None:
    llm = FakeLLM(
        {
            RiskExtraction: RiskExtraction.model_validate(
                {
                    "items": [
                        {
                            "text": "ISO 9001 belgesi sunmayan istekli değerlendirme dışı kalır.",
                            "severity": "high",
                            "category": "termination",
                            "source_index": 1,
                            "source_quote": "ISO 9001 kalite belgesi sunmak zorundadır",
                        }
                    ]
                }
            )
        }
    )
    runner = _runners(llm)[AgentName.RISKS]
    findings = runner.run([_chunk()])
    assert llm.calls[0]["schema"] is RiskExtraction
    assert findings[0].payload["severity"] == "high"
    assert findings[0].payload["category"] == "termination"
    assert findings[0].source is not None
    assert findings[0].source.is_grounded


def test_timeline_kosucusu_kendi_semasini_kullanir() -> None:
    llm = FakeLLM(
        {
            TimelineExtraction: TimelineExtraction.model_validate(
                {
                    "items": [
                        {
                            "label": "Belge sunum şartı",
                            "kind": "other",
                            "value_text": "ihale aşamasında",
                            "source_index": 1,
                            "source_quote": "ISO 9001 kalite belgesi sunmak zorundadır",
                        }
                    ]
                }
            )
        }
    )
    runner = _runners(llm)[AgentName.TIMELINE]
    findings = runner.run([_chunk()])
    assert llm.calls[0]["schema"] is TimelineExtraction
    assert findings[0].payload["kind"] == "other"
    assert findings[0].payload["value_text"] == "ihale aşamasında"
    assert findings[0].source is not None
    assert findings[0].source.is_grounded


def test_istem_kaynak_numaralari_ve_konum_icerir() -> None:
    llm = FakeLLM({RequirementExtraction: RequirementExtraction.model_validate({"items": []})})
    runner = _runners(llm)[AgentName.REQUIREMENTS]
    runner.run([_chunk()])
    prompt = llm.calls[0]["prompt"]
    assert "[KAYNAK 1]" in prompt
    assert "sayfa 2" in prompt
    assert "Madde 7" in prompt
    assert _ELEMENTS[5].text in prompt
    # Sistem istemi grounding kurallarını taşır.
    assert "source_quote" in llm.calls[0]["system"]


def test_bos_baglamda_llm_cagrilmaz() -> None:
    llm = FakeLLM({})
    runner = _runners(llm)[AgentName.REQUIREMENTS]
    assert runner.run([]) == []
    assert llm.calls == []
