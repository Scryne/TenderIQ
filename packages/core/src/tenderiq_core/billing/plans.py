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


# ── Kota kalibrasyonu (Tur 16) ───────────────────────────────────────────────
#
# Doküman/sayfa kotaları artık **elle seçilmiş sayılar değil**, LLM bütçesinden
# TÜRETİLİR. Gerekçe Tur 15 ölçümünde: ücretsiz kademe 5 doküman vaat ediyordu
# ama 25 TL'lik bütçesi ~3 doküman finanse ediyordu; bütçe kotadan 3-5 kat önce
# doluyordu. Kota kullanıcıya verilen SÖZDÜR, bütçe gerçek kısıttır — tutulamayan
# söz iptal ve iade olarak geri döner.
#
# **Bu geçici bir kalibrasyondur.** Maliyet düştüğünde (ucuz modele inme, istem
# önbellekleme — bkz. docs/ops/maliyet-tavani.md §6) aşağıdaki ORTALAMA MALİYET
# sabiti düşürülür ve tüm planların kotası TEK YERDEN yükselir. Kotayı plan
# tablosuna sabit sayı olarak yazmak, o günü elle üç yerde güncellemek demekti.

#: Ölçülen ortalama analiz maliyeti (TL/doküman) — Tur 15, kur 42, muhafazakâr
#: tokenizer oranı; metni çıkarılabilen 11 gerçek şartname/form üzerinden.
#: Hesap `docs/ops/maliyet-tavani.md` §4'te. **Maliyet düşünce burayı düşür.**
MEASURED_AVERAGE_ANALYSIS_COST_TRY = 8.3

#: Aynı ölçümdeki ortalama doküman uzunluğu (sayfa).
MEASURED_AVERAGE_DOCUMENT_PAGES = 6.5

#: Tipik bir teknik şartnamenin uzunluğu. Sayfa kotası bundan KÜÇÜK olamaz:
#: aksi hâlde bütçesinin finanse ettiği tek dokümanı sayfa limiti reddederdi
#: (ücretsiz kademede ortalamadan türetilen 20 sayfa, 29 sayfalık bir şartnameyi
#: engelliyordu — kotanın kotayı bloke etmesi).
TYPICAL_LARGE_DOCUMENT_PAGES = 35


def documents_for_budget(budget_try: int | None) -> int | None:
    """Bütçenin ortalama maliyetle finanse ettiği doküman sayısı.

    ``None`` (sınırsız kademe) girdi ``None`` çıktı verir. Aşağı yuvarlama
    bilinçli: yukarı yuvarlamak kotayı yeniden bütçenin üstüne çıkarırdı.
    """
    if budget_try is None:
        return None
    return max(1, int(budget_try // MEASURED_AVERAGE_ANALYSIS_COST_TRY))


def pages_for_documents(documents: int | None) -> int | None:
    """Doküman kotasına karşılık gelen sayfa kotası.

    Ortalama doküman uzunluğundan türetilir ama **tek bir tipik şartmanenin
    altına inmez** — sayfa limiti, bütçenin izin verdiği işi engellememelidir.
    """
    if documents is None:
        return None
    from_average = round(documents * MEASURED_AVERAGE_DOCUMENT_PAGES)
    return max(from_average, TYPICAL_LARGE_DOCUMENT_PAGES)


#: Ücretsiz kademenin aylık LLM bütçesi (TL). Geliri sıfır ve kayıt açık:
#: tavan doğrudan zarar sınırıdır.
FREE_BUDGET_TRY = 25
#: Pro'nun aylık LLM bütçesi (TL) — aylık gelirin belirgin altında; LLM tek
#: gider kalemi değil (OCR/embedding/depolama da var).
PRO_BUDGET_TRY = 500


PLANS: dict[PlanTier, Plan] = {
    PlanTier.FREE: Plan(
        tier=PlanTier.FREE,
        display_name="Ücretsiz",
        # Kota BÜTÇEDEN türetilir (yukarıdaki kalibrasyon); elle yazılmaz.
        documents_per_month=documents_for_budget(FREE_BUDGET_TRY),
        pages_per_month=pages_for_documents(documents_for_budget(FREE_BUDGET_TRY)),
        monthly_price_try=0,
        llm_budget_try_per_month=FREE_BUDGET_TRY,
        storage_bytes=500 * 1024 * 1024,  # 500 MB
    ),
    PlanTier.PRO: Plan(
        tier=PlanTier.PRO,
        display_name="Pro",
        documents_per_month=documents_for_budget(PRO_BUDGET_TRY),
        pages_per_month=pages_for_documents(documents_for_budget(PRO_BUDGET_TRY)),
        monthly_price_try=1500,
        llm_budget_try_per_month=PRO_BUDGET_TRY,
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
