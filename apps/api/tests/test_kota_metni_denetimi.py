"""Pazarlama metnindeki kota sayıları plan kaydıyla AYNI olmalı (Tur 16).

## Neden bu test var

Kota üç yerde yaşıyor: plan kaydı (`billing/plans.py`, tek gerçek kaynak),
landing fiyat kartları ve kayıt ekranı alt metni. Tur 15'te bulunan uyuşmazlık
kotanın kendisiyle bütçe arasındaydı; ikinci bir uyuşmazlık türü daha var ve
sessizdir: **plan kaydı değişir, pazarlama metni eski sayıda kalır.**

Bu, hukuki metinlerin dayandığı bir vaattir (`/sartlar` §3 fiyat sayfasına
işaret eder) — yani eski sayı yalnız yanlış değil, tutulmayan bir taahhüttür.
Kota kalibrasyonu maliyet düştükçe DEĞİŞECEK (bkz. `MEASURED_AVERAGE_
ANALYSIS_COST_TRY`), dolayısıyla bu uyuşmazlık bir kez değil her kalibrasyonda
üretilebilir. Test, kalibrasyonu değiştiren kişiyi metni de güncellemeye zorlar.

Sayıları burada TEKRARLAMIYORUZ: beklenen değer plan kaydından okunur, aksi
hâlde test üçüncü bir kopya olurdu.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tenderiq_core.billing.plans import PLANS, PlanTier

REPO_ROOT = Path(__file__).resolve().parents[3]
LANDING = REPO_ROOT / "apps" / "web" / "src" / "app" / "page.tsx"
REGISTER = REPO_ROOT / "apps" / "web" / "src" / "app" / "register" / "page.tsx"


def _text(path: Path) -> str:
    assert path.is_file(), f"dosya bulunamadı: {path}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("tier", "label"),
    [(PlanTier.FREE, "ücretsiz"), (PlanTier.PRO, "pro")],
)
def test_landing_kota_sayilari_plan_kaydiyla_ayni(tier: PlanTier, label: str) -> None:
    """Landing fiyat kartındaki doküman/sayfa sayıları plan kaydından gelmeli."""
    plan = PLANS[tier]
    assert plan.documents_per_month is not None
    assert plan.pages_per_month is not None
    landing = _text(LANDING)

    documents = {int(m) for m in re.findall(r'"([\d.]+) doküman / ay"', landing)}
    pages = {int(m.replace(".", "")) for m in re.findall(r'"([\d.]+) sayfa / ay"', landing)}

    assert plan.documents_per_month in documents, (
        f"{label}: landing'de '{plan.documents_per_month} doküman / ay' yok "
        f"(bulunanlar: {sorted(documents)}). Plan kaydı değişti, metin kalmış."
    )
    assert plan.pages_per_month in pages, (
        f"{label}: landing'de '{plan.pages_per_month} sayfa / ay' yok "
        f"(bulunanlar: {sorted(pages)}). Plan kaydı değişti, metin kalmış."
    )


def test_ucretsiz_kota_kayit_ve_hero_metninde_guncel() -> None:
    """ "Ayda N doküman" vaadi iki ekranda geçiyor; ikisi de plan kaydını izlemeli."""
    documents = PLANS[PlanTier.FREE].documents_per_month
    assert documents is not None
    beklenen = f"ayda {documents} doküman"
    for path in (LANDING, REGISTER):
        assert beklenen in _text(path), (
            f"{path.name}: '{beklenen}' geçmiyor — ücretsiz kota vaadi eski sayıda kalmış."
        )
