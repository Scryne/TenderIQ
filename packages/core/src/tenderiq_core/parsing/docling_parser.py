"""Docling tabanlı ayrıştırıcı — dijital PDF'ler için page + bbox çıkarımı (§6.2).

Docling AĞIR bir bağımlılıktır (torch, transformers). Bu modül yalnızca `parsing`
bağımlılık grubu kuruluyken (`uv sync --group parsing`) kullanılabilir. Docling
importları bilinçli olarak **lazy** tutulur: böylece docling'siz ortamlar
(ör. `apps/api`) `tenderiq_core.parsing` paketini içe aktardığında kırılmaz.
Bu nedenle sınıf `parsing/__init__.py`'den re-export EDİLMEZ; tüketiciler onu
`tenderiq_core.parsing.docling_parser` yolundan doğrudan içe aktarır.

Faz 1'de docling `packages/core`'un opsiyonel bir bağımlılığına (extra) taşınıp
`apps/worker` tarafından tüketilecek; sözleşme (`DocumentParser` Protocol) aynı kalır.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tenderiq_core.parsing.types import (
    BoundingBox,
    ElementKind,
    ParsedDocument,
    ParsedElement,
    ParseSource,
)

# Docling `DocItemLabel` → dahili `ElementKind` eşlemesi (yapı-farkında chunking için).
_LABEL_TO_KIND: dict[str, ElementKind] = {
    "title": ElementKind.HEADING,
    "section_header": ElementKind.HEADING,
    "list_item": ElementKind.LIST_ITEM,
    "table": ElementKind.TABLE,
    "caption": ElementKind.CAPTION,
    "footnote": ElementKind.CAPTION,
    "text": ElementKind.PARAGRAPH,
    "paragraph": ElementKind.PARAGRAPH,
    "reference": ElementKind.PARAGRAPH,
}
# Bu etiketler bir bölüm başlığı başlatır; sonraki öğeler bu bölüme atfedilir.
_HEADING_LABELS: frozenset[str] = frozenset({"title", "section_header"})


class DoclingParser:
    """Bir PDF'i Docling ile ``ParsedDocument``'e dönüştürür (her öğe page + bbox'lı).

    ``do_ocr=False`` (varsayılan) dijital yol içindir; taranmış/karmaşık dokümanlar
    için ``do_ocr=True`` ile ayrı bir örnek kullanın (§6.2 hibrit yönlendirme).
    OCR motoru EasyOCR'dır (ADR-0011); dil listesi ``ocr_lang`` ile verilir —
    Türkçe şartnameler için varsayılan ``("tr", "en")``.
    """

    def __init__(
        self,
        *,
        do_ocr: bool = False,
        do_table_structure: bool = True,
        ocr_lang: Sequence[str] = ("tr", "en"),
    ) -> None:
        self._do_ocr = do_ocr
        self._do_table_structure = do_table_structure
        self._ocr_lang = tuple(ocr_lang)
        self._converter: Any = None  # lazy — ilk parse'ta kurulur

    def _converter_instance(self) -> Any:
        """Docling ``DocumentConverter``'ı (lazy) kurar ve önbelleğe alır."""
        if self._converter is None:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            options = PdfPipelineOptions()
            options.do_ocr = self._do_ocr
            options.do_table_structure = self._do_table_structure
            if self._do_ocr:
                from docling.datamodel.pipeline_options import EasyOcrOptions

                options.ocr_options = EasyOcrOptions(lang=list(self._ocr_lang))
            self._converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
            )
        return self._converter

    def parse(self, path: Path) -> ParsedDocument:
        """Dosyayı ayrıştırır; okuma sırasında page + bbox'lı öğeler döndürür."""
        result = self._converter_instance().convert(str(path))
        return self._to_parsed_document(result.document)

    def _to_parsed_document(self, doc: Any) -> ParsedDocument:
        elements: list[ParsedElement] = []
        section: str | None = None
        for item, _level in doc.iterate_items(with_groups=False):
            label = self._label_of(item)
            text = self._text_of(item, doc)
            if not text:
                continue
            if label in _HEADING_LABELS:
                section = text
            page, bbox = self._locate(item, doc)
            elements.append(
                ParsedElement(
                    text=text,
                    page=page,
                    kind=_LABEL_TO_KIND.get(label, ElementKind.OTHER),
                    bbox=bbox,
                    section=section,
                )
            )
        page_count = len(doc.pages) if doc.pages else max((e.page for e in elements), default=0)
        source = ParseSource.SCANNED if self._do_ocr else ParseSource.DIGITAL
        return ParsedDocument(elements=elements, page_count=page_count, source=source)

    @staticmethod
    def _label_of(item: Any) -> str:
        label = getattr(item, "label", None)
        if label is None:
            return ""
        return str(getattr(label, "value", label))

    def _text_of(self, item: Any, doc: Any) -> str:
        # Tablolar markdown olarak dışa aktarılır (satır/sütun yapısı korunur);
        # diğer öğeler için ham metin kullanılır.
        if self._label_of(item) == "table" and hasattr(item, "export_to_markdown"):
            markdown: str = item.export_to_markdown(doc)
            return markdown.strip()
        return str(getattr(item, "text", "")).strip()

    @staticmethod
    def _locate(item: Any, doc: Any) -> tuple[int, BoundingBox | None]:
        """İlk provenance'tan (page, bbox) çıkarır; bbox TOPLEFT origin'e normalize edilir.

        TOPLEFT origin, Faz 3'teki PDF.js/react-pdf vurgu katmanına doğrudan eşlenir.
        """
        prov = getattr(item, "prov", None) or []
        if not prov:
            return 0, None
        first = prov[0]
        page_no = int(first.page_no)
        raw = getattr(first, "bbox", None)
        if raw is None:
            return page_no, None
        page = doc.pages.get(page_no) if doc.pages else None
        height = getattr(getattr(page, "size", None), "height", None)
        top_left = raw.to_top_left_origin(float(height)) if height is not None else raw
        bbox = BoundingBox(
            x0=float(top_left.l),
            y0=float(top_left.t),
            x1=float(top_left.r),
            y1=float(top_left.b),
        )
        return page_no, bbox
