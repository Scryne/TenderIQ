"""Golden-set değerlendirme scripti (§6.10): precision/recall + kaçırılan zorunlu belge oranı.

Kullanım:
    uv run python evals/run_eval.py \\
        --golden evals/golden/sample --predictions evals/predictions/sample \\
        [--report rapor.json] [--threshold 0.6] \\
        [--gate --min-recall 0.8 --max-missed-mandatory 0.05]

Tasarım:
- **Golden case** (``evals/golden/**/*.json``): bir dokümanın el ile etiketlenmiş
  beklenen çıktıları — gereksinimler, zorunlu belgeler (deliverables), riskler.
  Gerçek şartname etiketleri KVKK gereği ``evals/golden/private/`` altında tutulur
  ve commit edilmez; format standardı için bkz. ``evals/README.md``.
- **Prediction** (``evals/predictions/**/*.json``): ajan çıktısının metin temsili
  (Faz 2'de extraction ajanları üretecek; iskelet, sample fixture ile doğrulanır).
- **Eşleme:** normalize edilmiş metinler üzerinde bire-bir açgözlü eşleme
  (SequenceMatcher oranı ile token Jaccard'ın büyüğü ≥ eşik). LLM YOK —
  deterministik, CI'da tekrarlanabilir.
- **Kritik metrik:** kaçırılan zorunlu belge oranı = eşleşmeyen zorunlu
  deliverable / toplam zorunlu deliverable. Ürünün "yaşar mı" metriği (§12.6).
- ``--gate`` bayrağı eşikleri zorlar (çıkış kodu 2) — Faz 2 Sprint 2.4'te CI'da
  aktifleşecek; o zamana dek iskelet modu yalnızca format/script'i doğrular.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

CATEGORIES = ("requirements", "deliverables", "risks")


# ── Format sözleşmesi (schema_version=1) ────────────────────────────────────


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabeledRequirement(_StrictModel):
    """Beklenen tek gereksinim (teknik/idari/mali)."""

    id: str
    text: str
    type: Literal["technical", "administrative", "financial"]
    mandatory: bool = True
    page: int | None = None  # kaynak sayfa (izlenebilirlik; eşlemede kullanılmaz)


class LabeledDeliverable(_StrictModel):
    """Beklenen tek belge/sertifika/teminat kalemi."""

    id: str
    name: str
    mandatory: bool = True
    page: int | None = None


class LabeledRisk(_StrictModel):
    """Beklenen tek risk bulgusu (cezai şart, olağandışı madde...)."""

    id: str
    description: str
    severity: Literal["low", "medium", "high"]
    page: int | None = None


class GoldenLabels(_StrictModel):
    requirements: list[LabeledRequirement] = Field(default_factory=list)
    deliverables: list[LabeledDeliverable] = Field(default_factory=list)
    risks: list[LabeledRisk] = Field(default_factory=list)


class GoldenDocument(_StrictModel):
    """Etiketlenen dokümanın kimliği (dosya repoya girmez; ad + tür yeterli)."""

    filename: str
    kind: Literal["administrative", "technical", "contract", "addendum", "other"]
    source: Literal["digital", "scanned", "mixed"]
    page_count: int | None = None
    notes: str | None = None


class GoldenCase(_StrictModel):
    """Bir dokümanın golden-set girdisi."""

    schema_version: Literal[1]
    case_id: str
    document: GoldenDocument
    labels: GoldenLabels


class Predictions(_StrictModel):
    """Ajan çıktısının değerlendirme için metin temsili (kategori → metin listesi)."""

    requirements: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class PredictionSet(_StrictModel):
    schema_version: Literal[1]
    case_id: str
    predictions: Predictions


# ── Metin normalizasyonu ve benzerlik ────────────────────────────────────────

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(text: str) -> str:
    """Eşleme öncesi normalizasyon: Türkçe-farkında küçük harf + noktalama/boşluk sadeleştirme."""
    text = text.replace("İ", "i").replace("I", "ı")  # TR: İ→i, I→ı (casefold bunu bilmez)
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _PUNCTUATION.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def similarity(a: str, b: str) -> float:
    """İki metnin benzerliği: dizgi oranı ile token Jaccard'ın büyüğü [0,1]."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    tokens_a, tokens_b = set(na.split()), set(nb.split())
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    return max(ratio, jaccard)


def greedy_match(
    expected: list[str], predicted: list[str], *, threshold: float
) -> list[tuple[int, int]]:
    """Bire-bir açgözlü eşleme: en benzer çiftten başlayarak eşik üstündekileri eşler."""
    pairs = sorted(
        (
            (similarity(exp, pred), exp_index, pred_index)
            for exp_index, exp in enumerate(expected)
            for pred_index, pred in enumerate(predicted)
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    matched: list[tuple[int, int]] = []
    used_expected: set[int] = set()
    used_predicted: set[int] = set()
    for score, exp_index, pred_index in pairs:
        if score < threshold:
            break
        if exp_index in used_expected or pred_index in used_predicted:
            continue
        matched.append((exp_index, pred_index))
        used_expected.add(exp_index)
        used_predicted.add(pred_index)
    return matched


# ── Metrikler ────────────────────────────────────────────────────────────────


@dataclass
class CategoryCounts:
    """Bir kategorinin (mikro-ortalama için) ham sayaçları."""

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)


@dataclass
class EvalResult:
    """Tüm case'lerin birleşik sonucu."""

    counts: dict[str, CategoryCounts] = field(
        default_factory=lambda: {category: CategoryCounts() for category in CATEGORIES}
    )
    mandatory_deliverables_total: int = 0
    mandatory_deliverables_missed: int = 0
    missed_mandatory_items: list[str] = field(default_factory=list)  # "case_id: belge adı"
    evaluated_cases: list[str] = field(default_factory=list)
    skipped_cases: list[str] = field(default_factory=list)  # prediction dosyası olmayanlar

    @property
    def missed_mandatory_rate(self) -> float:
        if self.mandatory_deliverables_total == 0:
            return 0.0
        return self.mandatory_deliverables_missed / self.mandatory_deliverables_total

    def to_report(self) -> dict[str, object]:
        return {
            "evaluated_cases": self.evaluated_cases,
            "skipped_cases": self.skipped_cases,
            "categories": {
                category: {
                    "true_positive": counts.true_positive,
                    "false_positive": counts.false_positive,
                    "false_negative": counts.false_negative,
                    "precision": round(counts.precision, 4),
                    "recall": round(counts.recall, 4),
                    "f1": round(counts.f1, 4),
                }
                for category, counts in self.counts.items()
            },
            "missed_mandatory_deliverable_rate": round(self.missed_mandatory_rate, 4),
            "missed_mandatory_deliverables": self.missed_mandatory_items,
        }


def _expected_texts(case: GoldenCase, category: str) -> list[str]:
    if category == "requirements":
        return [item.text for item in case.labels.requirements]
    if category == "deliverables":
        return [item.name for item in case.labels.deliverables]
    return [item.description for item in case.labels.risks]


def evaluate_case(
    case: GoldenCase, predictions: Predictions, result: EvalResult, *, threshold: float
) -> None:
    """Tek case'in eşleme sonuçlarını birleşik sayaçlara ekler."""
    for category in CATEGORIES:
        expected = _expected_texts(case, category)
        predicted = getattr(predictions, category)
        matched = greedy_match(expected, predicted, threshold=threshold)
        matched_expected = {exp_index for exp_index, _ in matched}
        counts = result.counts[category]
        counts.true_positive += len(matched)
        counts.false_positive += len(predicted) - len(matched)
        counts.false_negative += len(expected) - len(matched)
        if category == "deliverables":
            for index, deliverable in enumerate(case.labels.deliverables):
                if not deliverable.mandatory:
                    continue
                result.mandatory_deliverables_total += 1
                if index not in matched_expected:
                    result.mandatory_deliverables_missed += 1
                    result.missed_mandatory_items.append(f"{case.case_id}: {deliverable.name}")


# ── Yükleme + CLI ────────────────────────────────────────────────────────────


class EvalInputError(Exception):
    """Girdi/format hatası (çıkış kodu 1)."""


def _load_json_files(directory: Path) -> list[tuple[Path, dict[str, object]]]:
    if not directory.is_dir():
        raise EvalInputError(f"Dizin yok: {directory}")
    files = sorted(directory.rglob("*.json"))
    loaded: list[tuple[Path, dict[str, object]]] = []
    for path in files:
        try:
            loaded.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as exc:
            raise EvalInputError(f"Geçersiz JSON: {path} ({exc})") from exc
    return loaded


def load_golden(directory: Path) -> dict[str, GoldenCase]:
    cases: dict[str, GoldenCase] = {}
    for path, payload in _load_json_files(directory):
        try:
            case = GoldenCase.model_validate(payload)
        except ValidationError as exc:
            raise EvalInputError(f"Golden case şemaya uymuyor: {path}\n{exc}") from exc
        if case.case_id in cases:
            raise EvalInputError(f"case_id tekrarı: {case.case_id} ({path})")
        cases[case.case_id] = case
    if not cases:
        raise EvalInputError(f"Golden case bulunamadı: {directory}")
    return cases


def load_predictions(directory: Path, golden: dict[str, GoldenCase]) -> dict[str, Predictions]:
    predictions: dict[str, Predictions] = {}
    for path, payload in _load_json_files(directory):
        try:
            prediction_set = PredictionSet.model_validate(payload)
        except ValidationError as exc:
            raise EvalInputError(f"Prediction şemaya uymuyor: {path}\n{exc}") from exc
        if prediction_set.case_id not in golden:
            raise EvalInputError(
                f"Prediction, bilinmeyen bir case'i gösteriyor: {prediction_set.case_id} ({path})"
            )
        if prediction_set.case_id in predictions:
            raise EvalInputError(f"Prediction tekrarı: {prediction_set.case_id} ({path})")
        predictions[prediction_set.case_id] = prediction_set.predictions
    if not predictions:
        raise EvalInputError(f"Prediction bulunamadı: {directory}")
    return predictions


def run(golden_dir: Path, predictions_dir: Path, *, threshold: float) -> EvalResult:
    """Golden + prediction dizinlerini yükler ve birleşik sonucu üretir."""
    golden = load_golden(golden_dir)
    predictions = load_predictions(predictions_dir, golden)
    result = EvalResult()
    for case_id, case in sorted(golden.items()):
        if case_id not in predictions:
            result.skipped_cases.append(case_id)
            continue
        result.evaluated_cases.append(case_id)
        evaluate_case(case, predictions[case_id], result, threshold=threshold)
    return result


def _print_summary(result: EvalResult) -> None:
    print(
        f"Değerlendirilen case: {len(result.evaluated_cases)} ({', '.join(result.evaluated_cases)})"
    )
    if result.skipped_cases:
        print(f"Prediction'ı olmayan case (atlandı): {', '.join(result.skipped_cases)}")
    print()
    header = f"{'Kategori':<14} {'TP':>4} {'FP':>4} {'FN':>4} "
    header += f"{'Precision':>10} {'Recall':>8} {'F1':>8}"
    print(header)
    for category, counts in result.counts.items():
        print(
            f"{category:<14} {counts.true_positive:>4} {counts.false_positive:>4} "
            f"{counts.false_negative:>4} {counts.precision:>10.3f} "
            f"{counts.recall:>8.3f} {counts.f1:>8.3f}"
        )
    print()
    print(
        f"KAÇIRILAN ZORUNLU BELGE ORANI: {result.missed_mandatory_rate:.3f} "
        f"({result.mandatory_deliverables_missed}/{result.mandatory_deliverables_total})"
    )
    for item in result.missed_mandatory_items:
        print(f"  - kaçırıldı: {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])  # type: ignore[union-attr]
    parser.add_argument("--golden", type=Path, required=True, help="Golden case dizini")
    parser.add_argument("--predictions", type=Path, required=True, help="Prediction dizini")
    parser.add_argument("--threshold", type=float, default=0.6, help="Eşleme benzerlik eşiği")
    parser.add_argument("--report", type=Path, default=None, help="JSON rapor çıktısı yolu")
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Eşikleri zorla (Faz 2'de CI kapısı); ihlalde çıkış kodu 2",
    )
    parser.add_argument("--min-recall", type=float, default=0.8, help="Gate: kategori min recall")
    parser.add_argument(
        "--max-missed-mandatory",
        type=float,
        default=0.05,
        help="Gate: kaçırılan zorunlu belge oranı tavanı",
    )
    args = parser.parse_args(argv)

    # Windows konsolu (cp1254 vb.) Türkçe raporu bozar; çıktı UTF-8'e sabitlenir.
    for stream in (sys.stdout, sys.stderr):
        if stream.encoding and stream.encoding.lower() not in {"utf-8", "utf8"}:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    try:
        result = run(args.golden, args.predictions, threshold=args.threshold)
    except EvalInputError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 1

    _print_summary(result)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result.to_report(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nRapor yazıldı: {args.report}")

    if args.gate:
        failures: list[str] = []
        if result.skipped_cases:
            failures.append(f"prediction'ı olmayan case var: {', '.join(result.skipped_cases)}")
        for category, counts in result.counts.items():
            if counts.recall < args.min_recall:
                failures.append(f"{category} recall {counts.recall:.3f} < {args.min_recall:.3f}")
        if result.missed_mandatory_rate > args.max_missed_mandatory:
            failures.append(
                f"kaçırılan zorunlu belge oranı {result.missed_mandatory_rate:.3f} > "
                f"{args.max_missed_mandatory:.3f}"
            )
        if failures:
            print("\nGATE İHLALİ:", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 2
        print("\nGate: tüm eşikler sağlandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
