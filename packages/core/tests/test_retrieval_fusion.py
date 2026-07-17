"""RRF birleştirme testleri (§6.6)."""

from __future__ import annotations

import pytest

from tenderiq_core.retrieval import reciprocal_rank_fusion


def test_iki_listede_gecen_aday_one_cikar() -> None:
    scores = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]], k=60)
    # b: 1/62 + 1/61 > a: 1/61
    assert scores["b"] > scores["a"] > scores["c"]
    assert set(scores) == {"a", "b", "c", "d"}


def test_tek_liste_sira_korunur() -> None:
    scores = reciprocal_rank_fusion([["x", "y", "z"]], k=60)
    assert scores["x"] > scores["y"] > scores["z"]


def test_skor_formulu() -> None:
    scores = reciprocal_rank_fusion([["a"], ["a"]], k=60)
    assert scores["a"] == pytest.approx(2.0 / 61.0)


def test_bos_girdi() -> None:
    assert reciprocal_rank_fusion([]) == {}
    assert reciprocal_rank_fusion([[], []]) == {}


def test_gecersiz_k() -> None:
    with pytest.raises(ValueError, match="pozitif"):
        reciprocal_rank_fusion([["a"]], k=0)
