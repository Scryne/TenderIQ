"""Ajan çıktı şemaları (Sprint 2.2, §6.7/§8.1) — şema-önce (C.8).

Her ajan çıktısı bu pydantic şemalarına birebir uymak ZORUNDADIR; LLM çağrısı
structured outputs ile şemaya kısıtlanır, uymayan çıktı reddedilip yeniden
istenir (``tenderiq_core.llm``). Enum'lar ``tenderiq_core.findings``ten gelir
(tek kaynak; ORM modelleri de aynı modülü kullanır — ajan sözleşmesi ile DB
şeması ayrışamaz, döngüsel import olmadan).

Grounding sözleşmesi (§6.9, ADR-0006): her öğe, bağlamdaki kaynağını
``source_index`` (bağlam bloğu numarası) + ``source_quote`` (birebir alıntı)
ile bildirir; alıntı doğrulaması ve ``ParsedElement`` bağlama işlemi
``agents.grounding``'dedir. Not: structured outputs şema kısıtları gereği
min/max uzunluk gibi kısıtlar şemaya konmaz (desteklenmez); doğrulama
grounding katmanında yapılır.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field

from tenderiq_core.findings import DeliverableKind, RequirementKind

__all__ = [
    "DeliverableExtraction",
    "DeliverableKind",
    "ExtractedDeliverable",
    "ExtractedItem",
    "ExtractedRequirement",
    "ExtractionResult",
    "RequirementExtraction",
    "RequirementKind",
]


class ExtractedItem(BaseModel):
    """Tüm ajan öğelerinin ortak kaynak sözleşmesi (grounding girdisi)."""

    source_index: int = Field(
        description="Öğenin çıkarıldığı bağlam bloğunun numarası ([KAYNAK n] içindeki n)."
    )
    source_quote: str = Field(
        description=(
            "Öğeyi kanıtlayan, kaynak bloktan BİREBİR (kelimesi kelimesine) kopyalanmış "
            "kısa alıntı. Asla yeniden yazma, kısaltma işareti ekleme."
        )
    )


class ExtractionResult(BaseModel):
    """Ajan çıktılarının ortak zarfı — koşucu, öğelere bu tip üzerinden erişir.

    Alt sınıflar ``items``'ı kendi öğe tipleriyle daraltır (kovaryant
    ``Sequence``); LLM'e her zaman somut alt sınıfın şeması gönderilir.
    """

    items: Sequence[ExtractedItem]


class ExtractedRequirement(ExtractedItem):
    """Şartnameden çıkarılmış tek gereksinim."""

    text: str = Field(description="Gereksinimin tam ve kendi başına anlaşılır Türkçe ifadesi.")
    kind: RequirementKind = Field(
        description="Gereksinim tipi: technical/administrative/financial."
    )
    is_mandatory: bool = Field(
        description="Zorunlu mu? 'zorunludur/şarttır/gerekir' → true; tercih/opsiyon → false."
    )


class RequirementExtraction(ExtractionResult):
    """Requirement Extractor ajanının tam çıktısı."""

    items: list[ExtractedRequirement] = Field(
        description="Bağlamda kanıtı olan TÜM gereksinimler; bağlamda yoksa boş liste."
    )


class ExtractedDeliverable(ExtractedItem):
    """Teklifle birlikte sunulması istenen tek belge/sertifika/teminat."""

    name: str = Field(description="Belgenin resmî adı (ör. 'Geçici teminat mektubu').")
    kind: DeliverableKind = Field(description="Belge tipi: document/certificate/guarantee/other.")
    is_mandatory: bool = Field(
        description="Sunulması zorunlu mu? Zorunlu → true; ihtiyari/koşullu → false."
    )


class DeliverableExtraction(ExtractionResult):
    """Deliverables Extractor ajanının tam çıktısı."""

    items: list[ExtractedDeliverable] = Field(
        description="Bağlamda kanıtı olan TÜM istenen belgeler; bağlamda yoksa boş liste."
    )
