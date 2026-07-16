"""Parsing fazı (Sprint 1.2): indir → hibrit ayrıştır → ``ParsedElement`` kalıcılaştır.

Tasarım:
- Uzun süren indirme + ayrıştırma **transaction dışında** yapılır; DB'ye yalnızca
  sonuç yazılırken bağlanılır (SSE poll'u ve bağlantı havuzu bloklanmaz).
- Idempotent: yeniden koşumda dokümanın mevcut öğeleri tek transaction'da
  silinip yeniden yazılır (``uq_parsed_element_document_seq`` çift kaydı ayrıca
  DB düzeyinde engeller).
- Parser ve depolama süreç başına tekildir (Docling modelleri task'lar arası
  yeniden kullanılır); testler ``_parser``/``_storage``'ı monkeypatch'ler.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from sqlalchemy import delete

from tenderiq_core.config import get_settings
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Document, Job
from tenderiq_core.models import ParsedElement as ParsedElementRow
from tenderiq_core.parsing import DocumentParser, ParsedDocument
from tenderiq_core.storage import StorageService
from tenderiq_core.uploads import normalize_content_type
from tenderiq_worker.db import tenant_session

logger = get_logger("tenderiq.worker.parsing")

_parser: DocumentParser | None = None
_storage: StorageService | None = None

# Geçici dosya uzantısı doğrulanmış içerik türünden türetilir: magic-bytes kontrolü
# content_type'ı doğrular, dosya adı uzantısı ise kullanıcı girdisidir ve içerikle
# çelişebilir (ör. "rapor.pdf" adlı DOCX) — yanlış uzantı hibrit rotayı şaşırtır.
_CONTENT_TYPE_SUFFIXES: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


def _suffix_for(content_type: str, filename: str) -> str:
    """İçerik türüne göre uzantı; bilinmeyen türde dosya adına düşer."""
    return (
        _CONTENT_TYPE_SUFFIXES.get(normalize_content_type(content_type))
        or Path(filename).suffix.lower()
        or ".pdf"
    )


def get_parser() -> DocumentParser:
    """Süreç başına tek hibrit parser döndürür (lazy; ağır modeller bir kez kurulur)."""
    global _parser
    if _parser is None:
        from tenderiq_core.parsing.hybrid import HybridDocumentParser

        _parser = HybridDocumentParser(ocr_lang=tuple(get_settings().parsing_ocr_languages))
    return _parser


def get_storage() -> StorageService:
    """Süreç başına tek depolama servisi döndürür (lazy)."""
    global _storage
    if _storage is None:
        _storage = StorageService.from_settings(get_settings())
    return _storage


def run_parsing_phase(job_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    """Bir işin dokümanını ayrıştırır ve öğeleri (sayfa + bbox) DB'ye yazar."""
    with tenant_session(tenant_id) as session:
        job = session.get(Job, job_id)
        document = session.get(Document, job.document_id) if job is not None else None
        if document is None:
            raise RuntimeError(f"Parse fazı: işin dokümanı bulunamadı (job={job_id})")
        document_id = document.id
        storage_key = document.storage_key
        suffix = _suffix_for(document.content_type, document.filename)

    parsed = _download_and_parse(storage_key, suffix)

    with tenant_session(tenant_id) as session:
        session.execute(delete(ParsedElementRow).where(ParsedElementRow.document_id == document_id))
        session.add_all(_to_rows(parsed, document_id=document_id, tenant_id=tenant_id))
        refreshed = session.get(Document, document_id)
        if refreshed is not None:
            refreshed.page_count = parsed.page_count

    logger.info(
        "parse_tamam",
        job_id=str(job_id),
        document_id=str(document_id),
        element_count=len(parsed.elements),
        page_count=parsed.page_count,
        source=parsed.source.value,
    )


def _download_and_parse(storage_key: str, suffix: str) -> ParsedDocument:
    """Nesneyi geçici dosyaya indirir ve hibrit parser'dan geçirir."""
    with tempfile.TemporaryDirectory(prefix="tenderiq-parse-") as tmp:
        local_path = Path(tmp) / f"document{suffix}"
        get_storage().download_file(storage_key, local_path)
        return get_parser().parse(local_path)


def _to_rows(
    parsed: ParsedDocument, *, document_id: uuid.UUID, tenant_id: uuid.UUID
) -> list[ParsedElementRow]:
    """Parse çıktısını ORM satırlarına çevirir (okuma sırası ``seq`` olarak korunur)."""
    rows: list[ParsedElementRow] = []
    for seq, element in enumerate(parsed.elements):
        bbox = element.bbox
        rows.append(
            ParsedElementRow(
                tenant_id=tenant_id,
                document_id=document_id,
                seq=seq,
                page=element.page,
                kind=element.kind,
                source=element.source or parsed.source,
                text=element.text,
                section=element.section,
                bbox_x0=bbox.x0 if bbox is not None else None,
                bbox_y0=bbox.y0 if bbox is not None else None,
                bbox_x1=bbox.x1 if bbox is not None else None,
                bbox_y1=bbox.y1 if bbox is not None else None,
            )
        )
    return rows
