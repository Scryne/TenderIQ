"""Hibrit parser birim testleri — yönlendirme, kalite kapısı, fallback zinciri.

Docling GEREKTİRMEZ: parser'lar sahtedir, sayfa haritası monkeypatch'lenir.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import tenderiq_core.parsing.hybrid as hybrid_module
from tenderiq_core.parsing import (
    BoundingBox,
    DocumentParsingError,
    ElementKind,
    HybridDocumentParser,
    ParsedDocument,
    ParsedElement,
    ParseSource,
    RoutingDecision,
)

_BBOX = BoundingBox(x0=10.0, y0=20.0, x1=100.0, y1=40.0)


def _element(page: int, *, with_bbox: bool = True, text: str = "madde") -> ParsedElement:
    return ParsedElement(
        text=text,
        page=page,
        kind=ElementKind.PARAGRAPH,
        bbox=_BBOX if with_bbox else None,
    )


def _document(
    *elements: ParsedElement, source: ParseSource = ParseSource.DIGITAL
) -> ParsedDocument:
    return ParsedDocument(elements=list(elements), page_count=2, source=source)


class FakeParser:
    """Sabit sonuç döndüren ya da hata fırlatan sahte parser (çağrı sayacıyla)."""

    def __init__(
        self, result: ParsedDocument | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def parse(self, path: Path) -> ParsedDocument:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _patch_route(monkeypatch: pytest.MonkeyPatch, page_map: dict[int, bool]) -> None:
    monkeypatch.setattr(
        hybrid_module, "route_document", lambda path: RoutingDecision(page_map=page_map)
    )


def test_dijital_dokuman_dijital_yoldan_gecer(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_route(monkeypatch, {1: True, 2: True})
    digital = FakeParser(result=_document(_element(1), _element(2)))
    ocr = FakeParser()
    parser = HybridDocumentParser(digital_parser=digital, ocr_parser=ocr)

    parsed = parser.parse(Path("sartname.pdf"))

    assert digital.calls == 1
    assert ocr.calls == 0
    assert parsed.source is ParseSource.DIGITAL
    assert all(element.source is ParseSource.DIGITAL for element in parsed.elements)


def test_taranmis_sayfa_ocr_yolunu_tetikler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Karma dokümanda OCR yolu seçilir; öğe kaynağı sayfa bazında işaretlenir."""
    _patch_route(monkeypatch, {1: True, 2: False})
    digital = FakeParser()
    ocr = FakeParser(result=_document(_element(1), _element(2), source=ParseSource.SCANNED))
    parser = HybridDocumentParser(digital_parser=digital, ocr_parser=ocr)

    parsed = parser.parse(Path("karma.pdf"))

    assert digital.calls == 0
    assert ocr.calls == 1
    assert parsed.source is ParseSource.SCANNED
    assert parsed.elements[0].source is ParseSource.DIGITAL  # dijital sayfadaki öğe
    assert parsed.elements[1].source is ParseSource.SCANNED  # taranmış sayfadaki öğe


def test_kalite_kapisi_bbox_dusukse_ocr_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dijital yol bbox'sız çıktı üretirse (izlenebilirlik yok) OCR'a düşülür."""
    _patch_route(monkeypatch, {1: True})
    digital = FakeParser(result=_document(_element(1, with_bbox=False)))
    ocr = FakeParser(result=_document(_element(1)))
    parser = HybridDocumentParser(digital_parser=digital, ocr_parser=ocr)

    parsed = parser.parse(Path("bozuk-dijital.pdf"))

    assert digital.calls == 1
    assert ocr.calls == 1
    assert parsed.elements[0].bbox is not None


def test_bos_cikti_fallback_tetikler(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_route(monkeypatch, {1: True})
    digital = FakeParser(result=_document())  # hiç öğe yok
    ocr = FakeParser(result=_document(_element(1)))
    parser = HybridDocumentParser(digital_parser=digital, ocr_parser=ocr)

    parsed = parser.parse(Path("bos.pdf"))

    assert ocr.calls == 1
    assert len(parsed.elements) == 1


def test_dijital_hata_verirse_ocr_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_route(monkeypatch, {1: True})
    digital = FakeParser(error=RuntimeError("docling çöktü"))
    ocr = FakeParser(result=_document(_element(1)))
    parser = HybridDocumentParser(digital_parser=digital, ocr_parser=ocr)

    parsed = parser.parse(Path("hatali.pdf"))

    assert digital.calls == 1
    assert ocr.calls == 1
    assert len(parsed.elements) == 1


def test_zincir_tukenirse_parsing_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tüm yollar başarısızsa DocumentParsingError yükselir (worker retry'ı devralır)."""
    _patch_route(monkeypatch, {1: True})
    digital = FakeParser(error=RuntimeError("dijital çöktü"))
    ocr = FakeParser(error=RuntimeError("ocr çöktü"))
    parser = HybridDocumentParser(digital_parser=digital, ocr_parser=ocr)

    with pytest.raises(DocumentParsingError, match="tükendi"):
        parser.parse(Path("umutsuz.pdf"))


def test_vlm_fallback_zincirin_sonunda(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gürültülü taramada OCR yetersizse VLM fallback devreye girer (ADR-0004)."""
    _patch_route(monkeypatch, {1: False})
    digital = FakeParser()
    ocr = FakeParser(result=_document())  # OCR boş çıktı → kalite kapısını geçemez
    vlm = FakeParser(result=_document(_element(1), source=ParseSource.SCANNED))
    parser = HybridDocumentParser(digital_parser=digital, ocr_parser=ocr, vlm_parser=vlm)

    parsed = parser.parse(Path("gurultulu-tarama.pdf"))

    assert digital.calls == 0  # taranmış rota dijital yolu hiç denemez
    assert ocr.calls == 1
    assert vlm.calls == 1
    assert parsed.elements[0].source is ParseSource.SCANNED


def test_rota_tespiti_hatasi_zinciri_dusurmez(monkeypatch: pytest.MonkeyPatch) -> None:
    """pypdf sayfa haritası çıkaramazsa (bozuk/şifreli PDF) tam zincir yine denenir."""

    def _bozuk(path: Path) -> RoutingDecision:
        raise ValueError("bozuk xref tablosu")

    monkeypatch.setattr(hybrid_module, "route_document", _bozuk)
    digital = FakeParser(error=RuntimeError("dijital çöktü"))
    ocr = FakeParser(result=_document(_element(1), source=ParseSource.SCANNED))
    parser = HybridDocumentParser(digital_parser=digital, ocr_parser=ocr)

    parsed = parser.parse(Path("bozuk.pdf"))

    assert digital.calls == 1
    assert ocr.calls == 1
    assert parsed.source is ParseSource.SCANNED
    assert parsed.elements[0].source is ParseSource.SCANNED


def test_pdf_disi_format_dogrudan_dijital(monkeypatch: pytest.MonkeyPatch) -> None:
    """DOCX sayfa haritasına girmez; bbox kapısı uygulanmaz, kaynak dijitaldir."""

    def _patlamali(path: Path) -> RoutingDecision:
        raise AssertionError("PDF-dışı format için sayfa haritası çıkarılmamalı")

    monkeypatch.setattr(hybrid_module, "route_document", _patlamali)
    digital = FakeParser(result=_document(_element(0, with_bbox=False)))
    ocr = FakeParser()
    parser = HybridDocumentParser(digital_parser=digital, ocr_parser=ocr)

    parsed = parser.parse(Path("sartname.docx"))

    assert digital.calls == 1
    assert ocr.calls == 0
    assert parsed.source is ParseSource.DIGITAL
    assert parsed.elements[0].source is ParseSource.DIGITAL
