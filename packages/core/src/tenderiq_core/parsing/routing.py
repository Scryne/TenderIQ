"""Sayfa-bazlı yönlendirme (§6.2, ADR-0004): "dijital metin var mı?" tespiti.

Her sayfanın metin katmanı ``pypdf`` ile yoklanır. Tek bir taranmış sayfa bile
OCR yolunu gerektirir: Docling ``do_ocr=True`` modunda yalnızca bitmap alanları
OCR'lar, dijital sayfalar programatik metnini korur — yani yönlendirme kararı
doküman düzeyinde verilse de davranış fiilen sayfa bazındadır.

``pypdf`` importu lazy tutulur: ``parsing`` extra'sı kurulu olmayan ortamlar
(ör. ``apps/api``) bu modülü sorunsuz içe aktarabilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tenderiq_core.parsing.types import ParseSource


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Bir PDF'in parse yolu kararı (sayfa haritasından türetilir)."""

    page_map: dict[int, bool]  # sayfa no (1-indeksli) → dijital metin var mı

    @property
    def digital_pages(self) -> int:
        """Dijital metin katmanı taşıyan sayfa sayısı."""
        return sum(1 for has_text in self.page_map.values() if has_text)

    @property
    def scanned_pages(self) -> int:
        """Metin katmanı olmayan (taranmış) sayfa sayısı."""
        return len(self.page_map) - self.digital_pages

    @property
    def needs_ocr(self) -> bool:
        """En az bir taranmış sayfa varsa OCR yolu gerekir."""
        return self.scanned_pages > 0

    @property
    def source(self) -> ParseSource:
        """Doküman düzeyi rota kaynağı (OCR kullanıldıysa ``scanned``)."""
        return ParseSource.SCANNED if self.needs_ocr else ParseSource.DIGITAL

    def page_source(self, page: int) -> ParseSource:
        """Bir sayfanın öğelerine atanacak kaynak; harita dışı sayfa → rota kaynağı."""
        has_text = self.page_map.get(page)
        if has_text is None:
            return self.source
        return ParseSource.DIGITAL if has_text else ParseSource.SCANNED


def digital_page_map(path: Path) -> dict[int, bool]:
    """Her sayfa için "çıkarılabilir dijital metin var mı" haritası üretir (pypdf)."""
    from pypdf import PdfReader  # lazy: parsing extra'sız ortamlar modülü import edebilsin

    reader = PdfReader(str(path))
    return {
        index + 1: bool((page.extract_text() or "").strip())
        for index, page in enumerate(reader.pages)
    }


def route_document(path: Path) -> RoutingDecision:
    """Bir PDF için yönlendirme kararı üretir."""
    return RoutingDecision(page_map=digital_page_map(path))
