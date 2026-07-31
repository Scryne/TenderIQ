"""Faturalama/kota saf birim testleri (DB'siz): plan kayıtları + dönem matematiği."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from tenderiq_core.billing.plans import (
    DEFAULT_PLAN_TIER,
    MEASURED_AVERAGE_ANALYSIS_COST_TRY,
    PLANS,
    TYPICAL_LARGE_DOCUMENT_PAGES,
    PlanTier,
    documents_for_budget,
    get_plan,
)
from tenderiq_core.services.quota import (
    LIMIT_LABELS_TR,
    QuotaExceededError,
    current_period_bounds,
)


def test_plan_registry_kademeler_ve_limitler() -> None:
    assert set(PLANS) == {PlanTier.FREE, PlanTier.PRO, PlanTier.ENTERPRISE}
    # Kotalar BÜTÇEDEN türetilir (Tur 16 kalibrasyonu); sayılar burada
    # tekrarlanmaz — tekrarlamak, kalibrasyon sabiti değiştiğinde testi
    # "kotayı koruyan" değil "kotayı donduran" bir bekçiye çevirirdi.
    assert PLANS[PlanTier.FREE].documents_per_month == documents_for_budget(
        PLANS[PlanTier.FREE].llm_budget_try_per_month
    )
    assert PLANS[PlanTier.PRO].documents_per_month == documents_for_budget(
        PLANS[PlanTier.PRO].llm_budget_try_per_month
    )
    # Kurumsal sınırsız (None) — enforcement bu boyutları hiç denetlemez.
    assert PLANS[PlanTier.ENTERPRISE].documents_per_month is None
    assert PLANS[PlanTier.ENTERPRISE].pages_per_month is None


@pytest.mark.parametrize("tier", [PlanTier.FREE, PlanTier.PRO])
def test_kotanin_tamami_ortalama_maliyette_butceyi_asmaz(tier: PlanTier) -> None:
    """Kota, bütçenin finanse ettiğinden FAZLA söz vermemeli.

    Tur 15'te bulunan uyuşmazlık buydu: ücretsiz kademe 5 doküman vaat
    ediyordu, 25 TL bütçesi ~3 doküman finanse ediyordu. Kullanıcı sözün
    ortasında ret görüyordu. Bu test o uyuşmazlığın geri gelmesini engeller —
    biri kotayı elle yükseltirse burada kırılır.
    """
    plan = PLANS[tier]
    assert plan.documents_per_month is not None
    assert plan.llm_budget_try_per_month is not None

    kotanin_maliyeti = plan.documents_per_month * MEASURED_AVERAGE_ANALYSIS_COST_TRY
    assert kotanin_maliyeti <= plan.llm_budget_try_per_month, (
        f"{tier.value}: kotanın tamamı ({plan.documents_per_month} doküman × "
        f"{MEASURED_AVERAGE_ANALYSIS_COST_TRY} TL = {kotanin_maliyeti:.1f} TL) "
        f"bütçeyi ({plan.llm_budget_try_per_month} TL) aşıyor — kullanıcıya "
        "tutulamayacak bir söz veriliyor."
    )


@pytest.mark.parametrize("tier", [PlanTier.FREE, PlanTier.PRO])
def test_sayfa_kotasi_tek_bir_tipik_sartnameyi_engellemez(tier: PlanTier) -> None:
    """Sayfa limiti, bütçenin izin verdiği işi bloke etmemeli.

    Ortalamadan türetilen sayfa kotası ücretsiz kademede ~20 sayfa veriyordu ve
    29 sayfalık tipik bir şartnameyi reddediyordu — kotanın kotayı bloke etmesi.
    """
    pages = PLANS[tier].pages_per_month
    assert pages is not None
    assert pages >= TYPICAL_LARGE_DOCUMENT_PAGES


def test_default_plan_ucretsizdir() -> None:
    assert DEFAULT_PLAN_TIER is PlanTier.FREE
    assert get_plan(DEFAULT_PLAN_TIER).monthly_price_try == 0


def test_get_plan_dogru_tanimi_dondurur() -> None:
    assert get_plan(PlanTier.PRO).display_name == "Pro"


def test_period_bounds_ay_ortasi() -> None:
    start, end = current_period_bounds(datetime(2026, 7, 22, 15, 30, tzinfo=UTC))
    assert start == datetime(2026, 7, 1, tzinfo=UTC)
    assert end == datetime(2026, 8, 1, tzinfo=UTC)


def test_period_bounds_aralik_yil_devri() -> None:
    start, end = current_period_bounds(datetime(2026, 12, 15, tzinfo=UTC))
    assert start == datetime(2026, 12, 1, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, tzinfo=UTC)


def test_period_bounds_utc_normalize_eder() -> None:
    # UTC+3'te 2026-01-01 01:00 = UTC'de 2025-12-31 22:00 → dönem ARALIK 2025.
    local = datetime(2026, 1, 1, 1, 0, tzinfo=timezone(timedelta(hours=3)))
    start, end = current_period_bounds(local)
    assert start == datetime(2025, 12, 1, tzinfo=UTC)
    assert end == datetime(2026, 1, 1, tzinfo=UTC)


def test_quota_exceeded_hata_alanlari() -> None:
    exc = QuotaExceededError("pages", used=150, limit=150)
    assert (exc.limit_kind, exc.used, exc.limit) == ("pages", 150, 150)
    assert "150/150" in str(exc)


@pytest.mark.parametrize(("kind", "label"), [("documents", "doküman"), ("pages", "sayfa")])
def test_limit_etiketleri_turkce(kind: str, label: str) -> None:
    assert LIMIT_LABELS_TR[kind] == label
