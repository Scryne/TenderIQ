"""Docling parser entegrasyon/regresyon testi (§6.2) — bbox çıkarımını kanıtlar.

Parsing spike'ının (Faz 0) kalıcı regresyon karşılığı: sentetik bir PDF üretip
Docling ile ayrıştırır ve **her öğenin sayfa + konum (bbox)** taşıdığını doğrular —
kaynak izlenebilirliğinin (citation-first) yapısal temeli.

`integration` işaretli (varsayılan pytest çalışmasından dışlanır) ve docling/reportlab
kurulu değilse atlanır (`uv sync --group parsing`). İçerik, CI taşınabilirliği için
ASCII + gömülü font; gerçek Türkçe doğrulaması ayrı spike dokümanlarıyla yapılır.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _make_sample_pdf(path: Path) -> None:
    """Başlık + paragraf + tablo içeren tek sayfalık sentetik PDF üretir."""
    pytest.importorskip("reportlab")
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    story = [
        Paragraph("TECHNICAL SPECIFICATION", styles["Title"]),
        Paragraph("1. SCOPE", styles["Heading1"]),
        Paragraph(
            "This document specifies the technical requirements for the procurement "
            "of server and network infrastructure. Bidders must satisfy all clauses below.",
            styles["BodyText"],
        ),
        Spacer(1, 8),
        Paragraph("2. PRICE SCHEDULE", styles["Heading1"]),
        Table(
            [["No", "Item", "Qty"], ["1", "Rack Server", "10"], ["2", "Network Switch", "4"]],
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ]
            ),
        ),
    ]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)


def test_docling_extracts_page_and_bbox(tmp_path: Path) -> None:
    """Dijital PDF → her öğe sayfa + bbox taşır; tablo ve başlık algılanır."""
    pytest.importorskip("docling")
    from tenderiq_core.parsing.docling_parser import DoclingParser
    from tenderiq_core.parsing.types import ElementKind, ParseSource

    pdf_path = tmp_path / "sample.pdf"
    _make_sample_pdf(pdf_path)

    parsed = DoclingParser(do_ocr=False).parse(pdf_path)

    assert parsed.source is ParseSource.DIGITAL
    assert parsed.page_count >= 1
    assert len(parsed.elements) >= 3

    # KRİTİK: kaynak izlenebilirliği — her öğe sayfa + konum taşımalı.
    assert all(element.page >= 1 for element in parsed.elements)
    assert all(element.bbox is not None for element in parsed.elements)

    kinds = {element.kind for element in parsed.elements}
    assert ElementKind.TABLE in kinds
    assert ElementKind.HEADING in kinds

    # bbox koordinatları tutarlı olmalı (x0<x1, y0<y1).
    for element in parsed.elements:
        box = element.bbox
        assert box is not None
        assert box.x1 > box.x0
        assert box.y1 > box.y0
