"""Ayrıştırıcı sözleşmesi (Protocol) — Faz 1'de Docling/VLM ile uygulanır."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from tenderiq_core.parsing.types import ParsedDocument


class DocumentParser(Protocol):
    """Bir dosyayı ``ParsedDocument``'e dönüştüren ayrıştırıcı sözleşmesi."""

    def parse(self, path: Path) -> ParsedDocument:
        """Dosyayı ayrıştırır; her öğe için sayfa + konum (bbox) döndürmelidir."""
        ...
