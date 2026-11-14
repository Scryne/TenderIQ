"""Kayıtlı yanıt kipi (LLM_PROVIDER=recorded) — deterministik, bağlama bağlı, yalnız development."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from tenderiq_core.agents import (
    AgentName,
    ContextChunk,
    ElementView,
    GroundingResolution,
    create_extractor_runners,
)
from tenderiq_core.agents.prompts import build_compliance_prompt
from tenderiq_core.agents.schemas import (
    ComplianceCheck,
    DeliverableExtraction,
    RequirementExtraction,
    RiskExtraction,
    TimelineExtraction,
)
from tenderiq_core.config import Settings
from tenderiq_core.llm.client import create_structured_llm
from tenderiq_core.llm.recorded import (
    RecordedLLMError,
    RecordedStructuredLLM,
    parse_context_blocks,
)
from tenderiq_core.retrieval import CorpusEntry, RetrievedChunk

ISO = "İsteklinin TS EN ISO/IEC 27001 belgesine sahip olması zorunludur"
CEZA = "gecikilen her takvim günü için sözleşme bedelinin binde 3'ü"

RECORDINGS = {
    "RequirementExtraction": [
        {
            "source_quote": ISO,
            "text": "ISO 27001 zorunlu.",
            "kind": "technical",
            "is_mandatory": True,
        },
        {
            "source_quote": "Bu cümle belgede hiç geçmiyor ve üretilmemeli",
            "text": "Uydurma gereksinim.",
            "kind": "technical",
            "is_mandatory": True,
        },
    ],
    "RiskExtraction": [
        {"source_quote": CEZA, "text": "Gecikme cezası.", "severity": "high", "category": "penalty"}
    ],
    "ComplianceCheck": [
        {
            "requirement_contains": "27001",
            "profile_contains": ["27001"],
            "met_rationale": "Profilde var.",
            "unmet_rationale": "Profilde yok.",
        },
        {
            "requirement_contains": "personel",
            "profile_contains": ["sertifikalı personel"],
            "met_rationale": "Var.",
            "unmet_rationale": "Bilinmiyor.",
            "unmet_status": "partial",
        },
    ],
}

_ELEMENTS = {
    1: ElementView(seq=1, page=2, text="7.2.3. " + ISO + "; belge geçerli olmalıdır."),
    2: ElementView(seq=2, page=4, text="46.1. Gecikmede " + CEZA + " oranında ceza uygulanır."),
}


def _chunk(seq: int, n: int) -> ContextChunk:
    element = _ELEMENTS[seq]
    return ContextChunk.from_retrieved(
        RetrievedChunk(
            entry=CorpusEntry(
                chunk_id=uuid.UUID(int=n),
                document_id=uuid.UUID(int=42),
                seq=n,
                text=element.text,
                section=f"Madde {seq}",
                page_start=element.page,
                page_end=element.page,
                element_seq_start=seq,
                element_seq_end=seq,
            ),
            score=0.9,
            fused_score=0.9,
            semantic_rank=n,
            keyword_rank=n,
        )
    )


def _llm() -> RecordedStructuredLLM:
    return RecordedStructuredLLM(recordings=RECORDINGS, source="test.json")


def test_baglamda_gecen_ogeler_dogru_blok_numarasiyla_doner_uydurma_uretilmez() -> None:
    runners = {r.name: r for r in create_extractor_runners(llm=_llm(), elements_by_seq=_ELEMENTS)}
    # Sıra bilerek ters: ceza 1. blokta, ISO 2. blokta — getirim sırasından bağımsız olmalı.
    context = [_chunk(2, 1), _chunk(1, 2)]
    reqs = runners[AgentName.REQUIREMENTS].run(context)
    assert len(reqs) == 1  # belgede olmayan alıntılı kayıt ÜRETİLMEZ
    assert reqs[0].payload["source_index"] == 2
    assert reqs[0].source is not None
    assert reqs[0].source.resolution is GroundingResolution.ELEMENT
    assert reqs[0].source.page == 2
    risks = runners[AgentName.RISKS].run(context)
    assert [r.payload["source_index"] for r in risks] == [1]
    assert risks[0].source is not None
    assert risks[0].source.page == 4


def test_kanit_baglamda_yoksa_bos_liste() -> None:
    runners = {r.name: r for r in create_extractor_runners(llm=_llm(), elements_by_seq=_ELEMENTS)}
    assert runners[AgentName.REQUIREMENTS].run([_chunk(2, 1)]) == []
    # Kaydı olmayan şema da boş ve şemaya uygun döner.
    assert runners[AgentName.TIMELINE].run([_chunk(1, 1)]) == []


def test_ayni_girdi_ayni_cikti() -> None:
    prompt = "Bağlam blokları:\n\n[KAYNAK 1] (sayfa 2)\n" + _ELEMENTS[1].text
    a = _llm().extract(system="s", prompt=prompt, schema=RequirementExtraction)
    b = _llm().extract(system="s", prompt=prompt, schema=RequirementExtraction)
    assert a == b
    assert a.items[0].source_quote == ISO


def test_uygunluk_profile_gore_durum_secer() -> None:
    requirements = ["ISO/IEC 27001 belgesi zorunlu.", "2 sertifikalı personel.", "Kayıtsız madde."]
    with_iso = build_compliance_prompt("Firmamız ISO 27001 belgelidir.", requirements)
    result = _llm().extract(system="s", prompt=with_iso, schema=ComplianceCheck)
    by_index = {i.requirement_index: i for i in result.items}
    assert by_index[1].status == "met"
    assert by_index[2].status == "partial"  # profil söylemiyor → kayıt "partial" diyor
    assert 3 not in by_index  # kaydı olmayan gereksinim değerlendirilmez
    without = build_compliance_prompt("Yalnız ISO 9001 belgemiz var.", requirements)
    status = {
        i.requirement_index: i.status
        for i in _llm().extract(system="s", prompt=without, schema=ComplianceCheck).items
    }
    assert status[1] == "unmet"


def test_semaya_uymayan_kayit_reddedilir() -> None:
    bad = RecordedStructuredLLM(
        recordings={"RequirementExtraction": [{"source_quote": ISO, "text": "x", "kind": "yok"}]},
        source="bozuk.json",
    )
    prompt = "[KAYNAK 1] (sayfa 2)\n" + _ELEMENTS[1].text
    with pytest.raises(ValidationError):
        bad.extract(system="s", prompt=prompt, schema=RequirementExtraction)


def test_blok_ayristirma() -> None:
    prompt = (
        "Talimat\n\nBağlam blokları:\n\n[KAYNAK 1] (sayfa 1)\nbir\n\n"
        "[KAYNAK 2] (sayfa 3, bölüm: X)\niki"
    )
    blocks = parse_context_blocks(prompt)
    assert set(blocks) == {1, 2}
    assert "bir" in blocks[1]
    assert "iki" not in blocks[1]
    assert "iki" in blocks[2]


def test_yalniz_developmentta_acilir() -> None:
    assert Settings(_env_file=None, llm_provider="recorded").llm_provider == "recorded"
    with pytest.raises(ValidationError, match="yalnız ENVIRONMENT=development"):
        Settings(_env_file=None, llm_provider="recorded", environment="staging")


def test_fabrika_depodaki_kaydi_yukler_ve_kayit_semaya_uyar() -> None:
    llm = create_structured_llm(Settings(_env_file=None, llm_provider="recorded"))
    assert isinstance(llm, RecordedStructuredLLM)
    assert llm.model_name.startswith("recorded:")
    # Depodaki kayıt dosyasının her öğesi kendi şemasına uymalı (bozuk kayıt CI'da düşer).
    path = Path(__file__).resolve().parents[3] / "config/llm-kayitli/yesilvadi-idari-sartname.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    schemas = {
        "RequirementExtraction": RequirementExtraction,
        "DeliverableExtraction": DeliverableExtraction,
        "RiskExtraction": RiskExtraction,
        "TimelineExtraction": TimelineExtraction,
    }
    for name, schema in schemas.items():
        assert data[name], name
        schema.model_validate({"items": [{**i, "source_index": 1} for i in data[name]]})
    assert data["ComplianceCheck"]


def test_bozuk_kayit_dosyasi_anlasilir_hata(tmp_path: Path) -> None:
    path = tmp_path / "bozuk.json"
    path.write_text("{bozuk", encoding="utf-8")
    with pytest.raises(RecordedLLMError, match="okunamadı"):
        RecordedStructuredLLM.from_path(path)
