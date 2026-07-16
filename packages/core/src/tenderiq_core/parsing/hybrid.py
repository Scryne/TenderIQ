"""Hibrit ayrıştırıcı (§6.2, ADR-0004): sayfa-bazlı yönlendirme + fallback zinciri.

Rota kararı ``routing`` modülünden gelir: tüm sayfalar dijitalse Docling
(``do_ocr=False``); en az bir taranmış sayfa varsa OCR'lı Docling (``do_ocr=True`` —
yalnızca bitmap alanlar OCR'lanır, dijital sayfalar programatik metnini korur).

Hata dayanıklılığı: bir yol hata verirse ya da kalite kapısını (öğe var mı +
PDF'te bbox kapsamı) geçemezse zincirdeki sonraki yola düşülür
(dijital → OCR → opsiyonel VLM). Zincir tükenirse ``DocumentParsingError``
yükselir; worker'ın retry/backoff mekanizması devralır. VLM fallback'i
(gürültülü taramada birebir citation için — ADR-0004) Faz 2'deki LLM
entegrasyonuyla ``vlm_parser`` parametresinden takılır.

Bu modülün import'u hafiftir (docling importları ``DoclingParser`` içinde lazy).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

from tenderiq_core.logging import get_logger
from tenderiq_core.parsing.base import DocumentParser, DocumentParsingError
from tenderiq_core.parsing.docling_parser import DoclingParser
from tenderiq_core.parsing.routing import RoutingDecision, route_document
from tenderiq_core.parsing.types import ParsedDocument

logger = get_logger("tenderiq.parsing.hybrid")

# İzlenebilirlik (citation-first) için PDF'te asgari bbox kapsamı; altı → fallback.
_MIN_BBOX_COVERAGE = 0.9


class HybridDocumentParser:
    """``DocumentParser`` sözleşmesini hibrit yönlendirme + fallback ile uygular."""

    def __init__(
        self,
        *,
        ocr_lang: Sequence[str] = ("tr", "en"),
        digital_parser: DocumentParser | None = None,
        ocr_parser: DocumentParser | None = None,
        vlm_parser: DocumentParser | None = None,
    ) -> None:
        self._digital = digital_parser or DoclingParser(do_ocr=False)
        self._ocr = ocr_parser or DoclingParser(do_ocr=True, ocr_lang=ocr_lang)
        self._vlm = vlm_parser  # Faz 2: gürültülü taramada VLM fallback (ADR-0004)

    def parse(self, path: Path) -> ParsedDocument:
        """Dosyayı yönlendirir, zincirdeki ilk kabul edilebilir sonucu döndürür."""
        is_pdf = path.suffix.lower() == ".pdf"
        routing: RoutingDecision | None = None
        if is_pdf:
            try:
                routing = route_document(path)
            except Exception as exc:
                # Bozuk/şifreli PDF'te rota tespiti (pypdf) zinciri düşürmemeli:
                # rota bilinmiyorsa en geniş zincir (dijital → OCR → VLM) denenir.
                logger.warning("rota_tespiti_hatasi", file=path.name, error=str(exc))
        last_error: Exception | None = None
        for name, parser in self._chain(routing, unknown_pdf=is_pdf and routing is None):
            try:
                parsed = parser.parse(path)
            except Exception as exc:
                logger.warning("parse_yolu_hatasi", file=path.name, yol=name, error=str(exc))
                last_error = exc
                continue
            if self._acceptable(parsed, path):
                return self._annotate(parsed, routing)
            logger.warning(
                "parse_kalite_kapisi",
                file=path.name,
                yol=name,
                element_count=len(parsed.elements),
            )
        raise DocumentParsingError(f"Parse zinciri tükendi: {path.name}") from last_error

    def _chain(
        self, routing: RoutingDecision | None, *, unknown_pdf: bool
    ) -> list[tuple[str, DocumentParser]]:
        """Rotaya göre denenecek parser zinciri (sıralı)."""
        if routing is None and not unknown_pdf:
            # DOCX/XLSX: OCR/VLM anlamsız — Docling'in format-yerel dönüştürücüsü tek yol.
            return [("digital", self._digital)]
        chain: list[tuple[str, DocumentParser]] = []
        if routing is None or not routing.needs_ocr:
            chain.append(("digital", self._digital))
        chain.append(("ocr", self._ocr))
        if self._vlm is not None:
            chain.append(("vlm", self._vlm))
        return chain

    @staticmethod
    def _acceptable(parsed: ParsedDocument, path: Path) -> bool:
        """Kalite kapısı: çıktı boş olmamalı; PDF'te bbox kapsamı eşiği aşmalı."""
        if not parsed.elements:
            return False
        if path.suffix.lower() != ".pdf":
            return True  # sayfa/bbox kavramı akış-tabanlı formatlarda (DOCX) zorunlu değil
        with_bbox = sum(1 for element in parsed.elements if element.bbox is not None)
        return with_bbox / len(parsed.elements) >= _MIN_BBOX_COVERAGE

    @staticmethod
    def _annotate(parsed: ParsedDocument, routing: RoutingDecision | None) -> ParsedDocument:
        """Öğelere sayfa-bazlı kaynak (digital/scanned) işler; doküman kaynağını rotalar."""
        if routing is None:
            # PDF-dışı format ya da rota tespiti başarısız PDF: kaynağı, sonucu
            # üreten parser belirler (dijital yol DIGITAL, OCR yolu SCANNED üretir).
            elements = [
                dataclasses.replace(element, source=element.source or parsed.source)
                for element in parsed.elements
            ]
            return dataclasses.replace(parsed, elements=elements)
        elements = [
            dataclasses.replace(element, source=routing.page_source(element.page))
            for element in parsed.elements
        ]
        return dataclasses.replace(parsed, elements=elements, source=routing.source)
