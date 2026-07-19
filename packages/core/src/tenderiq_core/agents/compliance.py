"""Compliance Checker (Sprint 2.3, §6.7) — temel gap analizi.

Diğer ajanlardan (``agents.extractors``) FARKLIdır: bağlamdan çıkarım yapmaz,
çıkarılmış GEREKSİNİMLERİ firmanın ``CapabilityProfile``'ına karşı değerlendirir
(karşılanıyor/kısmi/karşılanmıyor + gerekçe). Bu yüzden LangGraph'ın paralel
fan-out'una GİRMEZ (gereksinim çıkarımına bağımlıdır ve dış girdi=profil ister);
worker, grafik koştuktan sonra sıralı bir adım olarak çağırır.

Grounding: değerlendirme kendi kaynağını üretmez — değerlendirilen gereksinimin
kendi grounding'ini DEVRALIR (ADR-0006 korunur: her ComplianceResult, gereksinimin
maddesine bağlıdır). Bu modül yalnız değerlendirmeyi (durum + gerekçe) üretir;
kaynak bağını worker (``_write_compliance``) gereksinim bulgusundan taşır.
"""

from __future__ import annotations

from collections.abc import Sequence

from tenderiq_core.agents.prompts import COMPLIANCE_SYSTEM_PROMPT, build_compliance_prompt
from tenderiq_core.agents.schemas import ComplianceAssessment, ComplianceCheck
from tenderiq_core.llm import StructuredLLM
from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.agents.compliance")


class ComplianceChecker:
    """Gereksinimleri yetkinlik profiline karşı değerlendiren koşucu (tek LLM çağrısı)."""

    def __init__(self, *, llm: StructuredLLM) -> None:
        self._llm = llm

    @property
    def model_name(self) -> str:
        return self._llm.model_name

    def check(
        self, *, requirement_texts: Sequence[str], profile_content: str
    ) -> list[ComplianceAssessment]:
        """Gereksinim başına değerlendirme döndürür (1-indeksli ``requirement_index``).

        Boş gereksinim listesi veya boş profil → değerlendirme yok. Model
        geçersiz/tekrarlı gereksinim numarası döndürürse yok sayılır (numara
        başına ilk değerlendirme kazanır) — worker'ın yaptığı eşleme güvenli kalır.
        Geçici LLM hataları istisna olarak yükselir (Celery faz retry'ı devralır).
        """
        if not requirement_texts or not profile_content.strip():
            return []
        result = self._llm.extract(
            system=COMPLIANCE_SYSTEM_PROMPT,
            prompt=build_compliance_prompt(profile_content, list(requirement_texts)),
            schema=ComplianceCheck,
        )
        seen: set[int] = set()
        assessments: list[ComplianceAssessment] = []
        for item in result.items:
            if 1 <= item.requirement_index <= len(requirement_texts) and (
                item.requirement_index not in seen
            ):
                seen.add(item.requirement_index)
                assessments.append(item)
        logger.info(
            "uygunluk_degerlendirmesi_tamam",
            model=self._llm.model_name,
            requirement_count=len(requirement_texts),
            assessed_count=len(assessments),
        )
        return assessments
