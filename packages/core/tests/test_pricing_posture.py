"""Fiyat duruşu: tavanın zemini kusurluysa SESSİZ kalmamalı (J.6, Tur 15).

Buradaki üç arıza da "hata" üretmez, hepsi tavanı sessizce zayıflatır:
kur yoksa harcama hep 0 TL sayılır ve tavan HİÇ dolmaz; kur bayatsa tavan geç
kapanır; fiyat doğrulanmamışsa tavan tahmini bir sayının üstünde durur.
"""

from __future__ import annotations

from datetime import date

import pytest

from tenderiq_core.config import Settings
from tenderiq_core.llm.pricing import ModelPrice, PricingTable, load_pricing, reset_pricing_cache
from tenderiq_core.llm.pricing_posture import evaluate_pricing_posture

BUGUN = date(2026, 7, 31)


def _table(**models: ModelPrice) -> PricingTable:
    return PricingTable(models=dict(models), usd_try_rate=42.0, source="test")


def _dogrulanmis() -> ModelPrice:
    return ModelPrice(
        input_per_mtok_usd=5.0,
        output_per_mtok_usd=25.0,
        verified=True,
        source="https://example.invalid/pricing",
        verified_at="2026-07-31",
    )


def _dogrulanmamis() -> ModelPrice:
    return ModelPrice(input_per_mtok_usd=0.0, output_per_mtok_usd=0.0, verified=False)


def test_kur_yoksa_tavan_fiilen_devre_disi_sayilir() -> None:
    """En sinsi hâl: sistem sağlıklı görünür, tavan yoktur."""
    durus = evaluate_pricing_posture(
        Settings(llm_usd_try_rate=None),
        _table(m=_dogrulanmis()),
        today=BUGUN,
    )
    assert durus.fx_rate_missing
    assert durus.cap_effectively_disabled
    assert durus.degraded


def test_kur_tarihi_yoksa_bayatlik_olculemez_uyarilir() -> None:
    durus = evaluate_pricing_posture(
        Settings(llm_usd_try_rate=42.0, llm_usd_try_rate_date=None),
        _table(m=_dogrulanmis()),
        today=BUGUN,
    )
    assert durus.fx_rate_date_missing
    assert durus.fx_rate_age_days is None
    assert durus.degraded
    assert not durus.cap_effectively_disabled  # kur VAR, yalnız yaşı bilinmiyor


def test_esigi_asan_kur_bayat_isaretlenir() -> None:
    durus = evaluate_pricing_posture(
        Settings(
            llm_usd_try_rate=42.0,
            llm_usd_try_rate_date="2026-06-01",
            llm_usd_try_rate_max_age_days=30,
        ),
        _table(m=_dogrulanmis()),
        today=BUGUN,
    )
    assert durus.fx_rate_age_days == 60
    assert durus.fx_rate_stale
    assert durus.degraded


def test_esik_icindeki_kur_bayat_degil() -> None:
    durus = evaluate_pricing_posture(
        Settings(
            llm_usd_try_rate=42.0,
            llm_usd_try_rate_date="2026-07-20",
            llm_usd_try_rate_max_age_days=30,
        ),
        _table(m=_dogrulanmis()),
        today=BUGUN,
    )
    assert durus.fx_rate_age_days == 11
    assert not durus.fx_rate_stale
    assert not durus.degraded


def test_dogrulanmamis_model_gorunur_olur() -> None:
    durus = evaluate_pricing_posture(
        Settings(llm_usd_try_rate=42.0, llm_usd_try_rate_date="2026-07-31"),
        _table(iyi=_dogrulanmis(), kotu=_dogrulanmamis()),
        today=BUGUN,
    )
    assert durus.unverified_models == ("kotu",)
    assert durus.degraded


def test_kaynaksiz_verified_bayragi_dogrulanmis_saymaz(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """`verified: true` ama `source`/`verified_at` yoksa DOĞRULANMAMIŞ sayılır.

    Aksi hâlde bayrağı elle çevirmek, tavanı denetlenemez bir sayının üstüne
    oturtmaya yeterdi — doğrulama borcunun tam olarak kapatmaya çalıştığı şey bu.
    """
    path = tmp_path / "pricing.json"
    path.write_text(
        '{"models": {"kaynaksiz": {"input_per_mtok": 1, "output_per_mtok": 2, "verified": true}}}',
        encoding="utf-8",
    )
    reset_pricing_cache()
    table = load_pricing(Settings(llm_pricing_path=str(path), llm_usd_try_rate=42.0))
    reset_pricing_cache()
    assert table.models["kaynaksiz"].verified is False


@pytest.mark.parametrize("model", ["claude-opus-4-8"])
def test_uretim_modeli_depoda_dogrulanmis(model: str) -> None:
    """Yayın birincil modelinin fiyatı depoda doğrulanmış ve kaynaklı olmalı.

    GA engeli buydu: tavan doğrulanmamış sayıların üstünde duruyordu.
    """
    reset_pricing_cache()
    table = load_pricing(Settings(llm_usd_try_rate=42.0))
    reset_pricing_cache()
    price = table.models[model]
    assert price.verified, f"{model} doğrulanmamış"
    assert price.source is not None, f"{model}: kaynak URL yok"
    assert price.source.startswith("https://"), f"{model}: kaynak sağlayıcı sayfası değil"
    assert price.verified_at, f"{model}: doğrulama tarihi yok"
