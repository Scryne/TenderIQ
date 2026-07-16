"""Sayfa-bazlı yönlendirme birim testleri (§6.2) — karar mantığı + pypdf tespiti."""

from __future__ import annotations

from pathlib import Path

import pytest

from tenderiq_core.parsing.routing import RoutingDecision, digital_page_map
from tenderiq_core.parsing.types import ParseSource


def test_tum_sayfalar_dijitalse_ocr_gerekmez() -> None:
    decision = RoutingDecision(page_map={1: True, 2: True})
    assert decision.digital_pages == 2
    assert decision.scanned_pages == 0
    assert not decision.needs_ocr
    assert decision.source is ParseSource.DIGITAL


def test_tek_taranmis_sayfa_ocr_yolunu_gerektirir() -> None:
    """Çoğunluk dijital olsa bile tek taranmış sayfa OCR gerektirir (sayfa-bazlı rota)."""
    decision = RoutingDecision(page_map={1: True, 2: True, 3: False})
    assert decision.digital_pages == 2
    assert decision.scanned_pages == 1
    assert decision.needs_ocr
    assert decision.source is ParseSource.SCANNED


def test_page_source_sayfa_bazinda_kaynak_verir() -> None:
    decision = RoutingDecision(page_map={1: True, 2: False})
    assert decision.page_source(1) is ParseSource.DIGITAL
    assert decision.page_source(2) is ParseSource.SCANNED
    # Harita dışı sayfa (ör. konumsuz öğede page=0) → rota kaynağı.
    assert decision.page_source(0) is ParseSource.SCANNED


def test_digital_page_map_gercek_pdf_ile(tmp_path: Path) -> None:
    """Metinli sayfa dijital, boş (metin katmansız) sayfa taranmış sayılır."""
    pytest.importorskip("pypdf")
    reportlab_pagesizes = pytest.importorskip("reportlab.lib.pagesizes")
    reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")

    pdf_path = tmp_path / "karma.pdf"
    canvas = reportlab_canvas.Canvas(str(pdf_path), pagesize=reportlab_pagesizes.A4)
    canvas.drawString(72, 720, "IDARI SARTNAME - madde 1")  # sayfa 1: dijital metin
    canvas.showPage()
    canvas.rect(72, 72, 200, 200, fill=1)  # sayfa 2: yalnızca çizim (metin katmanı yok)
    canvas.showPage()
    canvas.save()

    assert digital_page_map(pdf_path) == {1: True, 2: False}
