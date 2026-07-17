"""Faz 1 çıkış kapısı doğrulaması: gerçek şartname → parse → chunk → embed → pgvector.

Kullanım (compose postgres ayakta + migration'lar uygulanmış olmalı):
    uv run python scripts/faz1_gate_check.py spike-docs/ornek.pdf [--query "..."] [--keep]

Ne yapar:
- Atılabilir bir Organization/Tender/Document/Job kaydı açar,
- Worker'ın GERÇEK pipeline'ını (``_run_pipeline``: parsing → indexing →
  extracting → review_ready) senkron çalıştırır — Celery broker'ı gerekmez.
  Tek ikame: nesne depolama yerine verilen yerel dosyayı sunan LocalFileStorage
  (R2 yükleme yolu Sprint 1.1 entegrasyon testlerinde ayrıca doğrulanmıştır).
- Parser hibrittir (Docling; taranmışta EasyOCR), embedding GERÇEK BGE-M3'tür
  (ilk çalıştırmada ~2 GB model iner).
- Sonunda izlenebilirlik ve getirim kanıtı basar: öğe/bbox kapsamı, chunk
  sayısı, vektör boyutu ve örnek sorgu için cosine benzerlikli ilk 3 chunk.
- Kayıtları temizler (``--keep`` verilmedikçe).

KVKK: gerçek şartname içeriği yalnız yerel DB'ye yazılır ve varsayılan olarak
koşum sonunda silinir; hiçbir içerik repoya/dosyaya kaydedilmez.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
import uuid
from pathlib import Path

# Bu script worker fazlarını süreç içinde koşturur; import'lar ağırdır (docling).
from sqlalchemy import func, select, text

import tenderiq_worker.parsing as worker_parsing
from tenderiq_core.models import (
    Chunk,
    Document,
    DocumentKind,
    DocumentStatus,
    Embedding,
    Job,
    JobStatus,
    Organization,
    ParsedElement,
    Tender,
    TenderStatus,
)
from tenderiq_worker.db import get_session_factory, tenant_session
from tenderiq_worker.indexing import get_embedder
from tenderiq_worker.tasks.documents import _run_pipeline


class LocalFileStorage:
    """Depolama ikamesi: hangi anahtar istenirse istensin verilen dosyayı sunar."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def download_file(self, key: str, destination: Path) -> None:
        shutil.copyfile(self.path, destination)


def _setup_rows(pdf: Path) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Atılabilir kiracı + tender + doküman + iş kaydı açar."""
    suffix = uuid.uuid4().hex[:8]
    factory = get_session_factory()
    with factory() as session, session.begin():
        org = Organization(name=f"Gate Check {suffix}", slug=f"gate-check-{suffix}")
        session.add(org)
        session.flush()
        tenant_id = org.id
    with tenant_session(tenant_id) as session:
        tender = Tender(
            tenant_id=tenant_id, title=f"Faz1 Gate — {pdf.name}", status=TenderStatus.DRAFT
        )
        session.add(tender)
        session.flush()
        document = Document(
            tenant_id=tenant_id,
            tender_id=tender.id,
            filename=pdf.name,
            content_type="application/pdf",
            storage_key=f"gate-check/{suffix}/{pdf.name}",
            kind=DocumentKind.TECHNICAL,
            status=DocumentStatus.UPLOADED,
        )
        session.add(document)
        session.flush()
        job = Job(tenant_id=tenant_id, document_id=document.id, status=JobStatus.QUEUED)
        session.add(job)
        session.flush()
        return tenant_id, document.id, job.id


def _report(tenant_id: uuid.UUID, document_id: uuid.UUID, query: str) -> None:
    """İzlenebilirlik + getirim kanıtını basar (Faz 1 çıkış kapısı ölçütleri)."""
    embedder = get_embedder()
    query_vector = embedder.embed([query])[0]
    with tenant_session(tenant_id) as session:
        element_total = session.scalar(
            select(func.count())
            .select_from(ParsedElement)
            .where(ParsedElement.document_id == document_id)
        )
        with_bbox = session.scalar(
            select(func.count())
            .select_from(ParsedElement)
            .where(ParsedElement.document_id == document_id, ParsedElement.bbox_x0.isnot(None))
        )
        by_source = dict(
            session.execute(
                select(ParsedElement.source, func.count())
                .where(ParsedElement.document_id == document_id)
                .group_by(ParsedElement.source)
            ).all()
        )
        chunk_total = session.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
        )
        embedding_total = session.scalar(
            select(func.count())
            .select_from(Embedding)
            .join(Chunk, Embedding.chunk_id == Chunk.id)
            .where(Chunk.document_id == document_id)
        )
        page_count = session.scalar(select(Document.page_count).where(Document.id == document_id))
        if not (element_total and chunk_total and embedding_total):
            raise RuntimeError("boş indeksleme çıktısı — kapı ölçütü sağlanmadı")
        print(
            f"  sayfa: {page_count} | öğe: {element_total} "
            f"(bbox: {with_bbox}/{element_total} = {with_bbox / element_total:.0%}) "
            f"| kaynak: { {k.value: v for k, v in by_source.items()} }"
        )
        print(
            f"  chunk: {chunk_total} | embedding: {embedding_total} "
            f"(model: {embedder.model_name}, boyut: {embedder.dim})"
        )

        # Getirim kanıtı: cosine mesafesine göre ilk 3 chunk (pgvector <=>).
        rows = session.execute(
            select(
                Chunk.section,
                Chunk.page_start,
                Chunk.text,
                Embedding.vector.cosine_distance(query_vector).label("distance"),
            )
            .join(Chunk, Embedding.chunk_id == Chunk.id)
            .where(Chunk.document_id == document_id)
            .order_by(text("distance"))
            .limit(3)
        ).all()
        print(f"  sorgu: {query!r}")
        for section, page, chunk_text, distance in rows:
            preview = " ".join(chunk_text.split())[:110]
            print(f"    benzerlik={1 - distance:.3f} s.{page} [{section or '-'}] {preview}…")


def _cleanup(tenant_id: uuid.UUID) -> None:
    factory = get_session_factory()
    with factory() as session, session.begin():
        org = session.get(Organization, tenant_id)
        if org is not None:
            session.delete(org)  # RLS'siz kök tablo; kiracı verisi FK cascade ile gider


def main() -> int:
    parser = argparse.ArgumentParser(description="Faz 1 çıkış kapısı uçtan uca doğrulaması")
    parser.add_argument("pdf", type=Path, nargs="+", help="Gerçek şartname PDF'leri")
    parser.add_argument(
        "--query", default="geçici teminat oranı ve süresi", help="Getirim kanıtı için örnek sorgu"
    )
    parser.add_argument("--keep", action="store_true", help="Kayıtları silme (incelemek için)")
    args = parser.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() not in {"utf-8", "utf8"}:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    for pdf in args.pdf:
        if not pdf.is_file():
            print(f"HATA: dosya yok: {pdf}", file=sys.stderr)
            return 1
        print(f"\n=== {pdf.name} ===")
        worker_parsing._storage = LocalFileStorage(pdf)  # tek ikame: yerel dosya
        tenant_id, document_id, job_id = _setup_rows(pdf)
        started = time.perf_counter()
        try:
            result = _run_pipeline(job_id, tenant_id)
            elapsed = time.perf_counter() - started
            print(f"  pipeline: {result} ({elapsed:.1f} sn)")
            if result != "review_ready":
                print("HATA: pipeline review_ready'ye ulaşmadı", file=sys.stderr)
                return 2
            _report(tenant_id, document_id, args.query)
        finally:
            if args.keep:
                print(f"  kayıtlar korundu (tenant={tenant_id})")
            else:
                _cleanup(tenant_id)
    print("\nFaz 1 çıkış kapısı: uçtan uca akış doğrulandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
