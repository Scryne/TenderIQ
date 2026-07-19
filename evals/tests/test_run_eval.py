"""Golden-set eval scripti birim testleri (eşleme + metrikler + CLI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from run_eval import (
    CATEGORIES,
    EvalInputError,
    EvalResult,
    GoldenCase,
    Predictions,
    evaluate_case,
    greedy_match,
    main,
    normalize,
    run,
    similarity,
)

EVALS_DIR = Path(__file__).resolve().parents[1]


def _case(**labels: list[dict[str, object]]) -> GoldenCase:
    return GoldenCase.model_validate(
        {
            "schema_version": 1,
            "case_id": "test",
            "document": {"filename": "t.pdf", "kind": "technical", "source": "digital"},
            "labels": labels,
        }
    )


def test_normalize_turkce_farkinda() -> None:
    # İ→i ve I→ı: casefold'un bilmediği TR kuralı; noktalama/boşluk sadeleşir.
    assert normalize("İMZA SİRKÜLERİ") == normalize("imza sirküleri")
    assert normalize("ISO 9001  Belgesi.") == "ıso 9001 belgesi"


def test_similarity_esanlamli_ifadeler_yuksek_skor() -> None:
    a = "Geçici teminat mektubu teklif bedelinin en az %3'ü oranında olacaktır."
    b = "Teklif bedelinin en az %3'ü oranında geçici teminat mektubu verilecektir."
    assert similarity(a, b) >= 0.6
    assert similarity("tamamen alakasız bir metin", a) < 0.3
    assert similarity("", a) == 0.0


def test_greedy_match_bire_bir() -> None:
    expected = ["kırmızı elma", "yeşil armut"]
    predicted = ["yeşil armut", "kırmızı elma", "kırmızı elma"]
    matched = greedy_match(expected, predicted, threshold=0.9)
    # Her beklenen en fazla bir tahminle eşleşir; üçüncü (mükerrer) tahmin FP kalır.
    assert len(matched) == 2
    assert {exp for exp, _ in matched} == {0, 1}


def test_evaluate_case_sayaclari_ve_zorunlu_belge() -> None:
    case = _case(
        deliverables=[
            {"id": "d1", "name": "Geçici teminat mektubu", "mandatory": True},
            {"id": "d2", "name": "İş deneyim belgesi", "mandatory": True},
            {"id": "d3", "name": "ISO 9001 belgesi", "mandatory": False},
        ]
    )
    predictions = Predictions(deliverables=["geçici teminat mektubu", "kalite el kitabı"])
    result = EvalResult()
    evaluate_case(case, predictions, result, threshold=0.6)
    counts = result.counts["deliverables"]
    assert (counts.true_positive, counts.false_positive, counts.false_negative) == (1, 1, 2)
    # Kritik metrik: kaçırılan zorunlu belge — d2 kaçtı, d3 opsiyonel olduğundan sayılmaz.
    assert result.mandatory_deliverables_total == 2
    assert result.mandatory_deliverables_missed == 1
    assert result.missed_mandatory_rate == 0.5
    assert result.missed_mandatory_items == ["test: İş deneyim belgesi"]


def test_bos_kategori_sifir_metrik_uretmez() -> None:
    result = EvalResult()
    evaluate_case(_case(), Predictions(), result, threshold=0.6)
    for category in CATEGORIES:
        assert result.counts[category].precision == 0.0
        assert result.counts[category].recall == 0.0
    assert result.missed_mandatory_rate == 0.0


def test_sample_fixture_beklenen_metrikleri_uretir() -> None:
    """Commit'lenen sample fixture 'geçer baseline'dır (CI kapısı bunu koşar).

    Sprint 2.4'te kapı bloke edici olduğundan sample, eşikleri sağlayan iyi bir
    çıkarımı temsil eder (tüm zorunlu belgeler bulunmuş). Kapı-ihlali tespiti
    ``test_cli_gate_ihlalde_iki_doner`` ve ``test_evaluate_case...``ta korunur.
    """
    result = run(
        EVALS_DIR / "golden" / "sample",
        EVALS_DIR / "predictions" / "sample",
        threshold=0.6,
    )
    assert result.evaluated_cases == ["ornek-sartname"]
    requirements = result.counts["requirements"]
    assert (requirements.true_positive, requirements.false_positive) == (5, 1)
    assert requirements.false_negative == 0
    deliverables = result.counts["deliverables"]
    assert (deliverables.true_positive, deliverables.false_negative) == (5, 0)
    # Tüm zorunlu belgeler bulundu → kaçırılan zorunlu belge oranı 0.
    assert result.mandatory_deliverables_total == 4
    assert result.missed_mandatory_rate == 0.0
    risks = result.counts["risks"]
    assert (risks.true_positive, risks.false_positive, risks.false_negative) == (2, 0, 0)


def test_cli_sample_gate_gecer(capsys: pytest.CaptureFixture[str]) -> None:
    """Sample fixture, varsayılan gate eşiklerini sağlar (CI kapısı sözleşmesi)."""
    exit_code = main(
        [
            "--golden",
            str(EVALS_DIR / "golden" / "sample"),
            "--predictions",
            str(EVALS_DIR / "predictions" / "sample"),
            "--gate",
            "--min-recall",
            "0.8",
            "--max-missed-mandatory",
            "0.05",
        ]
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "KAÇIRILAN ZORUNLU BELGE ORANI: 0.000" in output
    assert "Gate: tüm eşikler sağlandı." in output


def _write_case(directory: Path, case: GoldenCase) -> None:
    directory.mkdir(exist_ok=True)
    (directory / f"{case.case_id}.json").write_text(case.model_dump_json(), encoding="utf-8")


def test_cli_gate_ihlalde_iki_doner(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    # Kaçırılan zorunlu belge içeren (kusurlu) çıkarım → gate kırılmalı (çıkış 2).
    golden = tmp_path / "golden"
    _write_case(
        golden,
        _case(
            deliverables=[
                {"id": "d1", "name": "Geçici teminat mektubu", "mandatory": True},
                {"id": "d2", "name": "İş deneyim belgesi", "mandatory": True},
            ]
        ),
    )
    predictions = tmp_path / "predictions"
    predictions.mkdir()
    (predictions / "test.json").write_text(
        '{"schema_version": 1, "case_id": "test", '
        '"predictions": {"deliverables": ["Geçici teminat mektubu"]}}',
        encoding="utf-8",
    )
    exit_code = main(["--golden", str(golden), "--predictions", str(predictions), "--gate"])
    assert exit_code == 2
    assert "GATE İHLALİ" in capsys.readouterr().err


def test_bilinmeyen_case_prediction_hata(tmp_path: Path) -> None:
    golden = tmp_path / "golden"
    golden.mkdir()
    (golden / "a.json").write_text(_case().model_dump_json(), encoding="utf-8")
    predictions = tmp_path / "predictions"
    predictions.mkdir()
    (predictions / "b.json").write_text(
        '{"schema_version": 1, "case_id": "yok-boyle-case", "predictions": {}}',
        encoding="utf-8",
    )
    with pytest.raises(EvalInputError, match="bilinmeyen"):
        run(golden, predictions, threshold=0.6)


def test_prediction_olmayan_case_atlanir_ve_raporlanir(tmp_path: Path) -> None:
    golden = tmp_path / "golden"
    golden.mkdir()
    (golden / "a.json").write_text(_case().model_dump_json(), encoding="utf-8")
    other = _case()
    other = other.model_copy(update={"case_id": "digeri"})
    (golden / "b.json").write_text(other.model_dump_json(), encoding="utf-8")
    predictions = tmp_path / "predictions"
    predictions.mkdir()
    (predictions / "a.json").write_text(
        '{"schema_version": 1, "case_id": "test", "predictions": {}}', encoding="utf-8"
    )
    result = run(golden, predictions, threshold=0.6)
    assert result.evaluated_cases == ["test"]
    assert result.skipped_cases == ["digeri"]
