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
    #: Aylık LLM harcama tavanı (TL). ``None`` = sınırsız (kurumsal).
    #: **Ücretsiz kademeye ayrı ve sıkı tavan**: kayıt açık olduğu için
    #: kötüye kullanım yüzeyi orası ve geliri sıfır.
    llm_budget_try_per_month: int | None
    #: Toplam nesne depolama kotası (bayt). ``None`` = sınırsız.
    storage_bytes: int | None


PLANS: dict[PlanTier, Plan] = {
    PlanTier.FREE: Plan(
        tier=PlanTier.FREE,
        display_name="Ücretsiz",
        documents_per_month=5,
        pages_per_month=150,
        monthly_price_try=0,
        # Geliri sıfır olan kademe: tavan doğrudan zarar sınırıdır.
        llm_budget_try_per_month=25,
        storage_bytes=500 * 1024 * 1024,  # 500 MB
    ),
    PlanTier.PRO: Plan(
        tier=PlanTier.PRO,
        display_name="Pro",
        documents_per_month=100,
        pages_per_month=5000,
        monthly_price_try=1500,
        # Aylık gelirin belirgin altında: LLM maliyeti tek gider kalemi değil
        # (OCR/embedding/depolama da var). BAŞLANGIÇ değeri — gerçek kullanım
        # verisiyle kalibre edilecek (bkz. docs/ops/maliyet-tavani.md).
        llm_budget_try_per_month=500,
        storage_bytes=20 * 1024 * 1024 * 1024,  # 20 GB
    ),
    PlanTier.ENTERPRISE: Plan(
        tier=PlanTier.ENTERPRISE,
        display_name="Kurumsal",
        documents_per_month=None,  # sınırsız
        pages_per_month=None,  # sınırsız
        monthly_price_try=0,  # özel fiyat (satışla belirlenir)
        # Sınırsız: tavan sözleşmeyle konur, kodla değil.
        llm_budget_try_per_month=None,
        storage_bytes=None,
    ),
}

# Ödeme yapılmamış yeni kiracının varsayılan kademesi.
DEFAULT_PLAN_TIER = PlanTier.FREE

#: Kademeler ARTAN sırada. Yükseltme/düşürme ayrımı buradan çıkar ve fiyata
#: bakılarak yapılmaz: kurumsal planın listedeki fiyatı 0'dır (satışla belirlenir),
#: yani fiyat karşılaştırması kurumsalı "düşürme" sayardı.
PLAN_ORDER: tuple[PlanTier, ...] = (PlanTier.FREE, PlanTier.PRO, PlanTier.ENTERPRISE)


def get_plan(tier: PlanTier) -> Plan:
    """Bir kademe için plan tanımını döndürür."""
    return PLANS[tier]


def is_upgrade(current: PlanTier, target: PlanTier) -> bool:
    """Hedef kademe mevcut kademeden YUKARIDA mı.

    ``/sartlar`` §3'ün koddaki karşılığının girdisi: yükseltme anında etkili,
    düşürme dönem sonunda. Eşitlik yükseltme değildir.
    """
    return PLAN_ORDER.index(target) > PLAN_ORDER.index(current)
