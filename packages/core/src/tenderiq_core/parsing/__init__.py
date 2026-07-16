"""Doküman ayrıştırma katmanı (§6.2). Sözleşmeler + hibrit yönlendirme (Sprint 1.2).

``DoclingParser`` ağır bağımlılık (docling→torch) taşıdığından buradan re-export
edilmez; ``HybridDocumentParser``'ın import'u hafiftir (docling lazy yüklenir).
"""

from tenderiq_core.parsing.base import DocumentParser, DocumentParsingError
from tenderiq_core.parsing.hybrid import HybridDocumentParser
from tenderiq_core.parsing.routing import RoutingDecision, digital_page_map, route_document
from tenderiq_core.parsing.types import (
    BoundingBox,
    ElementKind,
    ParsedDocument,
    ParsedElement,
    ParseSource,
)

__all__ = [
    "BoundingBox",
    "DocumentParser",
    "DocumentParsingError",
    "ElementKind",
    "HybridDocumentParser",
    "ParseSource",
    "ParsedDocument",
    "ParsedElement",
    "RoutingDecision",
    "digital_page_map",
    "route_document",
]
