"""Parsing fizibilite spike'ı (Faz 0) — gerçek şartname PDF'leriyle çalıştırın.

Amaç (§6.2, A.4/5 "en riskli varsayımı erken doğrula"): dijital/taranmış
yönlendirmesini ve özellikle **her öğenin SAYFA + KONUM (bounding box)** bilgisinin
gerçek TR şartnamelerinde çıkarılabildiğini kanıtlamak. Bu, kaynak izlenebilirliğinin
(citation-first) yapısal temelidir. Bulgular `docs/adr/0004-hybrid-parsing.md`'ye işlenir.

Kurulum ve kullanım:
    uv sync --group parsing
    uv run --group parsing python scripts/parsing_spike.py spike-docs/*.pdf
    # Yönlendirme otomatiktir; zorlamak için:  --ocr  /  --no-ocr

Her PDF için `spike-out/<ad>.json` makine-okunur rapor üretir (gitignore'lu).
Gerçek şartnameler gizlidir (KVKK) → `spike-docs/` ve `spike-out/` commit EDİLMEZ.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tenderiq_core.parsing.types import ParsedDocument

_SAMPLE_LIMIT = 6
_TEXT_PREVIEW = 140
# Docling'in kullanabileceği OCR motorları (taranmış yol için gerekir).
_OCR_MODULES = ("easyocr", "rapidocr_onnxruntime", "pytesseract")


def _configure_utf8_stdout() -> None:
    """Windows konsolunun (cp1254) Türkçe/simge çıktısında çökmesini önle."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")


def _ocr_engine_available() -> bool:
    """Taranmış yol için bir OCR motoru (kütüphane veya tesseract) kurulu mu?"""
    if any(importlib.util.find_spec(module) is not None for module in _OCR_MODULES):
        return True
    return shutil.which("tesseract") is not None


def _digital_page_map(path: Path) -> dict[int, bool] | None:
    """Her sayfa için 'dijital metin var mı' haritası (pypdf ile)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf kurulu değil — `uv sync --group parsing` çalıştırın.")
        return None
    reader = PdfReader(str(path))
    return {
        index + 1: bool((page.extract_text() or "").strip())
        for index, page in enumerate(reader.pages)
    }


@dataclass(frozen=True, slots=True)
class SpikeReport:
    """Bir PDF'in parsing fizibilite özeti (ADR-0004 kanıtı)."""

    file: str
    page_count: int
    digital_pages: int
    scanned_pages: int
    parse_source: str  # digital | scanned (Docling do_ocr)
    element_count: int
    kind_counts: dict[str, int]
    bbox_coverage: float  # bbox'lı öğe oranı — KRİTİK metrik (0.0–1.0)
    pages_with_elements: int
    table_count: int
    samples: list[dict[str, object]]


def _resolve_ocr(digital: int, scanned: int, forced: bool | None) -> bool:
    """Yönlendirme: taranmış sayfalar çoğunluktaysa OCR (aksi hâlde dijital)."""
    if forced is not None:
        return forced
    total = digital + scanned
    return total > 0 and scanned > digital


def _build_report(path: Path, page_map: dict[int, bool], parsed: ParsedDocument) -> SpikeReport:
    digital = sum(1 for has_text in page_map.values() if has_text)
    elements = parsed.elements
    with_bbox = sum(1 for element in elements if element.bbox is not None)
    kind_counts = Counter(element.kind.value for element in elements)
    pages_seen = {element.page for element in elements}
    samples: list[dict[str, object]] = [
        {
            "page": element.page,
            "kind": element.kind.value,
            "section": element.section,
            "bbox": None if element.bbox is None else asdict(element.bbox),
            "text": element.text[:_TEXT_PREVIEW],
        }
        for element in elements[:_SAMPLE_LIMIT]
    ]
    return SpikeReport(
        file=path.name,
        page_count=parsed.page_count or len(page_map),
        digital_pages=digital,
        scanned_pages=len(page_map) - digital,
        parse_source=parsed.source.value,
        element_count=len(elements),
        kind_counts=dict(kind_counts),
        bbox_coverage=round(with_bbox / len(elements), 4) if elements else 0.0,
        pages_with_elements=len(pages_seen),
        table_count=kind_counts.get("table", 0),
        samples=samples,
    )


def _print_summary(report: SpikeReport) -> None:
    print(f"\n=== {report.file} ===")
    print(
        f"Sayfa: {report.page_count} | dijital: {report.digital_pages} | "
        f"taranmış: {report.scanned_pages} | yol: {report.parse_source}"
    )
    print(f"Öğe: {report.element_count} | türler: {report.kind_counts}")
    print(
        f"BBOX KAPSAMI: {report.bbox_coverage:.1%} "
        f"({report.pages_with_elements}/{report.page_count} sayfada öğe) "
        f"| tablo: {report.table_count}"
    )
    verdict = "✓ izlenebilirlik verisi çıkıyor" if report.bbox_coverage >= 0.9 else "⚠ bbox eksik"
    print(f"Karar: {verdict}")


def analyze(path: Path, *, forced_ocr: bool | None, out_dir: Path) -> SpikeReport | None:
    """Tek bir PDF'i yönlendirir, Docling ile ayrıştırır ve rapor üretir."""
    page_map = _digital_page_map(path)
    if page_map is None:
        return None
    digital = sum(1 for has_text in page_map.values() if has_text)
    do_ocr = _resolve_ocr(digital, len(page_map) - digital, forced_ocr)

    if do_ocr and not _ocr_engine_available():
        print(
            f"[{path.name}] Taranmış yol (OCR) gerekiyor ama OCR motoru kurulu değil. "
            "Kurun (biri yeterli):\n"
            "  uv pip install rapidocr-onnxruntime   # hafif, önerilen\n"
            "  uv pip install easyocr                 # torch tabanlı\n"
            "  veya sistemde `tesseract` + pytesseract.\n"
            "Dijital yolu denemek için: --no-ocr"
        )
        return None

    try:
        from tenderiq_core.parsing.docling_parser import DoclingParser
    except ImportError:
        print("docling kurulu değil — `uv sync --group parsing` çalıştırın.")
        return None

    print(f"[{path.name}] Docling çalışıyor (do_ocr={do_ocr})… ilk çağrı model indirebilir.")
    parsed = DoclingParser(do_ocr=do_ocr).parse(path)
    report = _build_report(path, page_map, parsed)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{path.stem}.json"
    out_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    _print_summary(report)
    print(f"Rapor: {out_path}")
    return report


def main() -> int:
    _configure_utf8_stdout()
    parser = argparse.ArgumentParser(description="TenderIQ parsing fizibilite spike'ı (§6.2).")
    parser.add_argument("pdfs", nargs="+", type=Path, help="Ayrıştırılacak PDF yolları")
    parser.add_argument("--out", type=Path, default=Path("spike-out"), help="Rapor klasörü")
    routing = parser.add_mutually_exclusive_group()
    routing.add_argument(
        "--ocr", dest="ocr", action="store_true", default=None, help="OCR yolunu zorla (taranmış)"
    )
    routing.add_argument("--no-ocr", dest="ocr", action="store_false", help="Dijital yolu zorla")
    args = parser.parse_args()

    exit_code = 0
    for path in args.pdfs:
        if not path.exists():
            print(f"Bulunamadı: {path}")
            exit_code = 1
            continue
        if analyze(path, forced_ocr=args.ocr, out_dir=args.out) is None:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
