"""Faz 2 çıkış kapısı doğrulaması: gerçek şartname → uçtan uca çıkarım → prediction + metrik.

Kullanım (compose postgres ayakta + migration'lar uygulanmış + Ollama qwen çalışır):
    LLM_PROVIDER=ollama RETRIEVAL_RERANKER_PROVIDER=none \\
        uv run python scripts/faz2_gate_check.py \\
        [--golden evals/golden/private] [--docs spike-docs] \\
        [--out evals/predictions/private] [--case idari-sartname-6428] [--keep]

Ne yapar (``faz1_gate_check`` deseniyle simetrik):
- Golden-set'teki (private) her case için, ``document.filename``i ``--docs``
  dizininde bulur; atılabilir Organization/Tender/Document/Job kaydı açar.
- Worker'ın GERÇEK pipeline'ını (``_run_pipeline``: parsing → indexing →
  extracting → review_ready) senkron koşar — Celery broker gerekmez. Extracting
  fazı ``LLM_PROVIDER=ollama`` ile qwen2.5 ajanlarını çağırır (Sprint 2.2/2.3).
  Tek ikame: nesne depolama yerine yerel dosyayı sunan LocalFileStorage.
- Sonra DB'ye yazılan bulguları okur:
  * **GROUNDED** bulgular (kaynak öğeye bağlı; API'nin döndürdüğüyle aynı küme)
    → ``evals/predictions/private/<case_id>.json`` PredictionSet'i (run_eval girdisi).
  * Ajan başına grounded/ungrounded sayımı → grounding zorunluluğu kanıtı (§6.9).
  * Kaynak-eşleme (sayfa) doğruluğu → eşleşen bulgunun kaynak öğesinin sayfası
    golden etiketteki sayfa ile tutuyor mu (bire-bir açgözlü metin eşlemesi).
- Kayıtları temizler (``--keep`` verilmedikçe).

KVKK: gerçek şartname içeriği yalnız yerel DB'ye + gitignore'lu
``evals/predictions/private/`` altına yazılır; koşum sonunda DB kayıtları silinir.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
import uuid
from pathlib import Path

from sqlalchemy import func, select

# run_eval'ı (golden yükleme + eşleme/benzerlik) yeniden kullan.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "evals"))
import run_eval  # noqa: E402

import tenderiq_worker.parsing as worker_parsing  # noqa: E402
from tenderiq_core.models import (  # noqa: E402
    Deliverable,
    Document,
    DocumentKind,
    DocumentStatus,
    Organization,
    ParsedElement,
    Requirement,
    RiskFlag,
    Tender,
    TenderStatus,
)
from tenderiq_worker.db import get_session_factory, tenant_session  # noqa: E402
from tenderiq_worker.tasks.documents import _run_pipeline  # noqa: E402

# Golden ``document.kind`` → ORM ``DocumentKind`` (çıkarımı etkilemez; kayıt için).
_KIND_MAP = {
    "administrative": DocumentKind.ADMINISTRATIVE,
    "technical": DocumentKind.TECHNICAL,
    "contract": DocumentKind.OTHER,
    "addendum": DocumentKind.OTHER,
    "other": DocumentKind.OTHER,
}


class LocalFileStorage:
    """Depolama ikamesi: hangi anahtar istenirse istensin verilen dosyayı sunar."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def download_file(self, key: str, destination: Path) -> None:
        shutil.copyfile(self.path, destination)


def _setup_rows(pdf: Path, kind: DocumentKind) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Atılabilir kiracı + tender + doküman + iş kaydı açar (faz1 deseni)."""
    suffix = uuid.uuid4().hex[:8]
    factory = get_session_factory()
    with factory() as session, session.begin():
        org = Organization(name=f"Faz2 Gate {suffix}", slug=f"faz2-gate-{suffix}")
        session.add(org)
        session.flush()
        tenant_id = org.id
    with tenant_session(tenant_id) as session:
        tender = Tender(
            tenant_id=tenant_id, title=f"Faz2 Gate — {pdf.name}", status=TenderStatus.DRAFT
        )
        session.add(tender)
        session.flush()
        document = Document(
            tenant_id=tenant_id,
            tender_id=tender.id,
            filename=pdf.name,
            content_type="application/pdf",
            storage_key=f"faz2-gate/{suffix}/{pdf.name}",
            kind=kind,
            status=DocumentStatus.UPLOADED,
        )
        session.add(document)
        session.flush()
        from tenderiq_core.models import Job, JobStatus

        job = Job(tenant_id=tenant_id, document_id=document.id, status=JobStatus.QUEUED)
        session.add(job)
        session.flush()
        return tenant_id, document.id, job.id


def _grounding_counts(tenant_id: uuid.UUID, document_id: uuid.UUID) -> dict[str, tuple[int, int]]:
    """Ajan başına (grounded, ungrounded) sayımı — grounding zorunluluğu kanıtı."""
    from tenderiq_core.findings import GroundingResolution

    counts: dict[str, tuple[int, int]] = {}
    with tenant_session(tenant_id) as session:
        for label, model in (
            ("requirements", Requirement),
            ("deliverables", Deliverable),
            ("risks", RiskFlag),
        ):
            total = session.scalar(
                select(func.count()).select_from(model).where(model.document_id == document_id)
            )
            ungrounded = session.scalar(
                select(func.count())
                .select_from(model)
                .where(
                    model.document_id == document_id,
                    model.grounding_resolution == GroundingResolution.UNGROUNDED,
                )
            )
            counts[label] = (int(total or 0) - int(ungrounded or 0), int(ungrounded or 0))
    return counts


def _grounded_predictions(
    tenant_id: uuid.UUID, document_id: uuid.UUID
) -> dict[str, list[tuple[str, int]]]:
    """GROUNDED bulguları (metin, kaynak sayfası) olarak okur — API inner join'iyle aynı küme."""
    predictions: dict[str, list[tuple[str, int]]] = {}
    with tenant_session(tenant_id) as session:
        for label, model, text_col in (
            ("requirements", Requirement, Requirement.text),
            ("deliverables", Deliverable, Deliverable.name),
            ("risks", RiskFlag, RiskFlag.text),
        ):
            rows = session.execute(
                select(text_col, ParsedElement.page)
                .join(ParsedElement, model.source_element_id == ParsedElement.id)
                .where(model.document_id == document_id)
                .order_by(model.seq)
            ).all()
            predictions[label] = [(str(t), int(p)) for t, p in rows]
    return predictions


def _source_match(
    case: run_eval.GoldenCase,
    predictions: dict[str, list[tuple[str, int]]],
    *,
    threshold: float,
) -> tuple[int, int]:
    """Eşleşen bulguların kaynak sayfası golden etiketle tutuyor mu (matched_correct, matched)."""
    matched_correct = 0
    matched_total = 0
    for category in run_eval.CATEGORIES:
        expected_items = _golden_items(case, category)  # (text, page|None)
        predicted_items = predictions.get(category, [])
        pairs = run_eval.greedy_match(
            [t for t, _ in expected_items],
            [t for t, _ in predicted_items],
            threshold=threshold,
        )
        for exp_index, pred_index in pairs:
            expected_page = expected_items[exp_index][1]
            predicted_page = predicted_items[pred_index][1]
            if expected_page is None:  # golden'da sayfa yoksa eşleme değerlendirilmez
                continue
            matched_total += 1
            if expected_page == predicted_page:
                matched_correct += 1
    return matched_correct, matched_total


def _golden_items(case: run_eval.GoldenCase, category: str) -> list[tuple[str, int | None]]:
    if category == "requirements":
        return [(i.text, i.page) for i in case.labels.requirements]
    if category == "deliverables":
        return [(i.name, i.page) for i in case.labels.deliverables]
    return [(i.description, i.page) for i in case.labels.risks]


def _write_prediction(
    out_dir: Path, case_id: str, predictions: dict[str, list[tuple[str, int]]]
) -> Path:
    """PredictionSet JSON'unu (run_eval şeması) yazar — yalnız metinler (sayfa değil)."""
    import json

    payload = {
        "schema_version": 1,
        "case_id": case_id,
        "predictions": {
            "requirements": [t for t, _ in predictions["requirements"]],
            "deliverables": [t for t, _ in predictions["deliverables"]],
            "risks": [t for t, _ in predictions["risks"]],
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{case_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _cleanup(tenant_id: uuid.UUID) -> None:
    factory = get_session_factory()
    with factory() as session, session.begin():
        org = session.get(Organization, tenant_id)
        if org is not None:
            session.delete(org)  # RLS'siz kök tablo; kiracı verisi FK cascade ile gider


def main() -> int:
    parser = argparse.ArgumentParser(description="Faz 2 çıkış kapısı uçtan uca çıkarım doğrulaması")
    parser.add_argument("--golden", type=Path, default=_REPO_ROOT / "evals/golden/private")
    parser.add_argument("--docs", type=Path, default=_REPO_ROOT / "spike-docs")
    parser.add_argument("--out", type=Path, default=_REPO_ROOT / "evals/predictions/private")
    parser.add_argument(
        "--case", action="append", default=None, help="Yalnız bu case_id (tekrarlı)"
    )
    parser.add_argument("--threshold", type=float, default=0.6, help="Kaynak-eşleme metin eşiği")
    parser.add_argument("--keep", action="store_true", help="DB kayıtlarını silme")
    args = parser.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() not in {"utf-8", "utf8"}:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    cases = run_eval.load_golden(args.golden)
    selected = args.case or sorted(cases)
    exit_code = 0
    for case_id in selected:
        case = cases.get(case_id)
        if case is None:
            print(f"HATA: golden case yok: {case_id}", file=sys.stderr)
            return 1
        pdf = args.docs / case.document.filename
        if not pdf.is_file():
            print(f"HATA: doküman yok: {pdf}", file=sys.stderr)
            return 1
        print(f"\n=== {case_id} ({case.document.filename}) ===")
        worker_parsing._storage = LocalFileStorage(pdf)  # tek ikame: yerel dosya
        kind = _KIND_MAP.get(case.document.kind, DocumentKind.OTHER)
        tenant_id, document_id, job_id = _setup_rows(pdf, kind)
        started = time.perf_counter()
        try:
            result = _run_pipeline(job_id, tenant_id)
            elapsed = time.perf_counter() - started
            if result != "review_ready":
                print(f"HATA: pipeline review_ready'ye ulaşmadı ({result})", file=sys.stderr)
                exit_code = 2
                continue
            counts = _grounding_counts(tenant_id, document_id)
            predictions = _grounded_predictions(tenant_id, document_id)
            path = _write_prediction(args.out, case_id, predictions)
            correct, total = _source_match(case, predictions, threshold=args.threshold)
            print(f"  pipeline: review_ready ({elapsed:.0f} sn)")
            for label in ("requirements", "deliverables", "risks"):
                grounded, ungrounded = counts[label]
                print(
                    f"  {label:<13} grounded={grounded:>3} ungrounded={ungrounded:>3} "
                    f"(API'ye yalnız {grounded} döner)"
                )
            match_pct = f"{correct}/{total} = {correct / total:.0%}" if total else "n/a"
            print(f"  kaynak-eşleme (sayfa): {match_pct}")
            print(f"  prediction yazıldı: {path.relative_to(_REPO_ROOT)}")
        finally:
            if args.keep:
                print(f"  kayıtlar korundu (tenant={tenant_id})")
            else:
                _cleanup(tenant_id)
    print("\nFaz 2 kapı: çıkarım tamam. Metrikler için:")
    print(
        f"  uv run python evals/run_eval.py --golden {args.golden} "
        f"--predictions {args.out} --gate --min-recall 0.8 --max-missed-mandatory 0.05"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
