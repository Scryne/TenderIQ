"""Abonelik planları — ürün-seviyesi kota yapılandırması (Sprint 3.3, §14).

Planlar **kodda** tanımlıdır (DB'de değil): fiyatlandırma ve kotalar bir ürün
kararıdır, kiracı verisi değil. Ödeme entegrasyonu (iyzico/PayTR, Sprint 3.3-B)
bu kademelere eşlenir; ``Subscription.plan`` yalnızca kademeyi (tier) saklar,
limitler her zaman buradan okunur — böylece plan değişikliği tek yerden yönetilir.

Kota dönemi takvim ayıdır (UTC); sayım ``tenderiq_core.services.quota``'da yapılır.
``None`` limit = sınırsız (kurumsal).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlanTier(StrEnum):
    """Abonelik kademesi."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class Plan:
    """Bir plan kademesinin kota ve fiyat tanımı.

    ``documents_per_month`` / ``pages_per_month`` ``None`` ise o boyut sınırsızdır.
    ``monthly_price_try`` gösterim ve ödeme eşlemesi içindir (TL; kuruş değil).
    """

    tier: PlanTier
    display_name: str
    documents_per_month: int | None
    pages_per_month: int | None
    monthly_price_try: int


PLANS: dict[PlanTier, Plan] = {
    PlanTier.FREE: Plan(
        tier=PlanTier.FREE,
        display_name="Ücretsiz",
        documents_per_month=5,
        pages_per_month=150,
        monthly_price_try=0,
    ),
    PlanTier.PRO: Plan(
        tier=PlanTier.PRO,
        display_name="Pro",
        documents_per_month=100,
        pages_per_month=5000,
        monthly_price_try=1500,
    ),
    PlanTier.ENTERPRISE: Plan(
        tier=PlanTier.ENTERPRISE,
        display_name="Kurumsal",
        documents_per_month=None,  # sınırsız
        pages_per_month=None,  # sınırsız
        monthly_price_try=0,  # özel fiyat (satışla belirlenir)
    ),
}

# Ödeme yapılmamış yeni kiracının varsayılan kademesi.
DEFAULT_PLAN_TIER = PlanTier.FREE


def get_plan(tier: PlanTier) -> Plan:
    """Bir kademe için plan tanımını döndürür."""
    return PLANS[tier]
