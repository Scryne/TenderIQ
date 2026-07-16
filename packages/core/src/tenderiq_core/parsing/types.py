"""Doküman ayrıştırma çıktısı için ortak tipler (Faz 1'de doldurulur).

En kritik alanlar ``page`` + ``bbox``: her öğenin dokümandaki tam konumu, ürünün
kaynak izlenebilirliği (citation-first) özelliğinin temelidir (§6.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ElementKind(StrEnum):
    """Ayrıştırılmış öğe türü (yapı-farkında chunking için)."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CAPTION = "caption"
    OTHER = "other"


class ParseSource(StrEnum):
    """Ayrıştırma yolu (§6.2 hibrit yönlendirme)."""

    DIGITAL = "digital"  # Docling — dijital PDF
    SCANNED = "scanned"  # VLM/OCR — taranmış/karmaşık


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Sayfa üzerinde konum (nokta cinsinden)."""

    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True, slots=True)
class ParsedElement:
    """Ayrıştırılmış tek bir öğe — izlenebilirlik için sayfa + konumlu."""

    text: str
    page: int  # 1-indeksli
    kind: ElementKind
    bbox: BoundingBox | None = None
    section: str | None = None  # ait olduğu bölüm başlığı (chunk metadata'sı)
    # Öğeyi üreten yol; hibrit rotada sayfa bazında değişir (taranmış sayfa → SCANNED).
    # Gürültülü-OCR öğelerini birebir citation'da işaretleyebilmek için saklanır.
    source: ParseSource | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Bir dokümanın ayrıştırma sonucu."""

    elements: list[ParsedElement]
    page_count: int
    source: ParseSource
