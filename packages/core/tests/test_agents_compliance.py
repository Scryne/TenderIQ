"""Compliance Checker testleri — sahte LLM'le (Sprint 2.3, §6.7)."""

from __future__ import annotations

from typing import Any

from tenderiq_core.agents import ComplianceChecker, ComplianceStatus
from tenderiq_core.agents.schemas import ComplianceCheck


class FakeLLM:
    """extract çağrılarını kaydeder; önceden kurulmuş ComplianceCheck döndürür."""

    model_name = "fake-llm"

    def __init__(self, result: ComplianceCheck) -> None:
        self._result = result
        self.calls: list[dict[str, Any]] = []

    def extract(self, *, system: str, prompt: str, schema: type) -> Any:
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        return self._result


def _check(result: ComplianceCheck) -> tuple[ComplianceChecker, FakeLLM]:
    llm = FakeLLM(result)
    return ComplianceChecker(llm=llm), llm


def test_degerlendirme_durumlari_donuyor() -> None:
    checker, llm = _check(
        ComplianceCheck.model_validate(
            {
                "items": [
                    {
                        "requirement_index": 1,
                        "status": "met",
                        "rationale": "ISO 9001 profilde var.",
                    },
                    {"requirement_index": 2, "status": "unmet", "rationale": "TSE belgesi yok."},
                ]
            }
        )
    )
    assessments = checker.check(
        requirement_texts=["ISO 9001 belgesi gerekir.", "TSE belgesi gerekir."],
        profile_content="Firmamız ISO 9001 belgesine sahiptir.",
    )
    assert [a.status for a in assessments] == [ComplianceStatus.MET, ComplianceStatus.UNMET]
    # İstem hem profili hem numaralı gereksinimleri taşır.
    assert "ISO 9001" in llm.calls[0]["prompt"]
    assert "1. ISO 9001 belgesi gerekir." in llm.calls[0]["prompt"]
    assert llm.calls[0]["schema"] is ComplianceCheck


def test_gecersiz_ve_tekrarli_numaralar_yok_sayilir() -> None:
    checker, _ = _check(
        ComplianceCheck.model_validate(
            {
                "items": [
                    {"requirement_index": 1, "status": "met", "rationale": "a"},
                    {
                        "requirement_index": 1,
                        "status": "unmet",
                        "rationale": "tekrar",
                    },  # yok sayılır
                    {
                        "requirement_index": 5,
                        "status": "met",
                        "rationale": "aralık dışı",
                    },  # yok sayılır
                ]
            }
        )
    )
    assessments = checker.check(requirement_texts=["tek gereksinim"], profile_content="profil")
    assert len(assessments) == 1
    assert assessments[0].requirement_index == 1
    assert assessments[0].status is ComplianceStatus.MET


def test_bos_profil_veya_gereksinim_llm_cagirmaz() -> None:
    checker, llm = _check(ComplianceCheck.model_validate({"items": []}))
    assert checker.check(requirement_texts=[], profile_content="profil") == []
    assert checker.check(requirement_texts=["x"], profile_content="   ") == []
    assert llm.calls == []
