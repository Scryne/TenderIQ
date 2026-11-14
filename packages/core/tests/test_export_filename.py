"""Rapor dosya adı: İKN'li ihale başlığı yılını kaybetmemeli, ad temiz olmalı."""

from __future__ import annotations

from datetime import datetime

from tenderiq_core.export import report_filename

AN = datetime(2026, 11, 14, 15, 43)


def test_ikn_yili_korunur_uzun_tire_temizlenir() -> None:
    ad = report_filename("2026/418732 — Veri Merkezi Sunucu Yenileme", AN, "docx")
    assert ad == "tenderiq-2026-418732 Veri Merkezi Sunucu Yenileme-20261114.docx"


def test_uzun_baslik_kirpilir_kenar_bosluk_kalmaz() -> None:
    baslik = "2026/418732 — Belediye Veri Merkezi Sunucu ve Depolama Altyapısı Yenileme İşi"
    ad = report_filename(baslik, AN, "xlsx")
    stem = ad.removeprefix("tenderiq-").removesuffix("-20261114.xlsx")
    assert len(stem) <= 60
    assert stem == stem.strip(" .-_")
    assert stem.startswith("2026-418732 Belediye")
    assert stem.endswith("Depolama")  # kelime ortasında kesilmez ("Altyapı…" değil)


def test_yol_ve_ozel_karakterler_dosya_adina_sizmaz() -> None:
    ad = report_filename('..\gizli/../"ihale"<:>|?*', AN, "docx")
    for yasak in '\/"<>:|?*':
        assert yasak not in ad
    assert not ad.removeprefix("tenderiq-").startswith(".")


def test_bos_baslik_yedek_ad() -> None:
    assert report_filename("  — / ", AN, "docx") == "tenderiq-rapor-20261114.docx"
