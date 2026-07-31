"""/api/v1/usage — kiracının plan/kota kullanımı (Sprint 3.3-A; J.6 ile genişledi).

İki uç var ve ayrımları bilinçli:

- ``GET /usage`` — **herkes** (kiracının her üyesi). "Ne kadarım kaldı, ne zaman
  sıfırlanır, dolunca ne yapabilirim" sorusunu yanıtlar.
- ``GET /usage/admin`` — **yalnız kiracı yöneticisi**. "Tavan neden gevşek
  davrandı" sorusunu yanıtlar: fiyatlandırılamayan çağrı sayısı, rezerve tutar,
  kurun bayat olup olmadığı. Bunlar operasyonel teşhis verisidir; normal üyeye
  göstermek gürültüden başka bir şey üretmez.

**Rezerve tutar HARCANMIŞ DEĞİLDİR** ve iki uçta da ayrı alan olarak döner.
Devam eden işler için ayrılmış tutardır; iş bitince serbest kalır ve yerine
gerçek maliyet yazılır. Harcamanın içine katmak, kullanıcıya "param bitti"
dedirtecek bir rakam gösterirdi — oysa o para henüz harcanmadı.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from tenderiq_api.dependencies import (
    PrincipalDep,
    RedisDep,
    SettingsDep,
    TenantSessionDep,
    require_role,
)
from tenderiq_core.billing.plans import PlanTier, get_plan
from tenderiq_core.llm.pricing import MICROS_PER_TRY
from tenderiq_core.llm.pricing_posture import evaluate_pricing_posture
from tenderiq_core.models import Role, SubscriptionStatus
from tenderiq_core.services import llm_budget, quota, storage_quota
from tenderiq_core.services.llm_reservation import reserved_total_async

router = APIRouter(prefix="/usage", tags=["usage"])

_admin_only = Depends(require_role(Role.ADMIN))


class QuotaUsage(BaseModel):
    """Tek bir kota boyutu: kullanılan / limit (``limit=None`` ⇒ sınırsız)."""

    used: int
    limit: int | None


class BudgetUsage(BaseModel):
    """Dönem içi LLM harcaması (TL) — tavan, kalan ve REZERVE ayrı ayrı."""

    #: Kaydedilmiş, tutarı güvenilir harcama.
    spent_try: float
    #: Plan tavanı; ``None`` ⇒ sınırsız (kurumsal).
    limit_try: float | None
    #: Devam eden işler için AYRILMIŞ tutar — harcanmış DEĞİL.
    reserved_try: float
    #: `tavan − harcanan − rezerve`; sınırsız kademede ``None``.
    remaining_try: float | None
    #: Yumuşak eşik aşıldı mı (uyarı; yeni iş hâlâ kabul edilir).
    soft_exceeded: bool


class StorageUsageResponse(BaseModel):
    """Depolama kullanımı (bayt). Biçimlendirme arayüzün işi (Intl.*)."""

    used_bytes: int
    limit_bytes: int | None
    remaining_bytes: int | None
    soft_exceeded: bool


class UsageResponse(BaseModel):
    """Kiracının içinde bulunulan dönemdeki kullanımı ve plan limitleri."""

    plan: PlanTier
    plan_name: str
    status: SubscriptionStatus
    period_start: datetime
    period_end: datetime
    documents: QuotaUsage
    pages: QuotaUsage
    budget: BudgetUsage
    storage: StorageUsageResponse


class AdminUsageResponse(BaseModel):
    """Yönetici teşhis görünümü — "tavan neden gevşek davrandı" sorusu.

    `unpriced_calls` bu sorunun asıl yanıtıdır: tutarı hesaplanamamış her çağrı
    harcama toplamına GİRMEZ, yani tavan olduğundan gevşek davranır.
    """

    period_start: datetime
    period_end: datetime
    spent_try: float
    limit_try: float | None
    reserved_try: float
    #: Dönemdeki toplam LLM çağrısı.
    calls: int
    #: Tutarı HESAPLANAMAMIŞ çağrı sayısı (bilinmeyen model / kur yok).
    unpriced_calls: int
    #: Kur hiç tanımlı değil → harcama hep 0 sayılır, tavan fiilen YOK.
    fx_rate_missing: bool
    #: Kur bayat ya da tarihi yazılmamış → tavan yanıltıcı hesaplanıyor.
    fx_rate_stale: bool
    #: Kurun yaşı (gün); tarih yazılmamışsa ``None``.
    fx_rate_age_days: int | None
    #: Fiyatı sağlayıcıya karşı doğrulanmamış model adları.
    unverified_models: list[str]


async def _reserved_micros(redis: object, tenant_id: uuid.UUID, period_start: datetime) -> int:
    """Redis'teki rezervasyon toplamı; okunamazsa 0 (görüntü, karar değil).

    Kesintide 0 göstermek bilinçli: bu sayı bir KARAR girdisi değil, kullanıcıya
    "şu an ayrılmış" bilgisidir. Tavanı uygulayan yol (worker) kesintide zaten
    muhafazakâr moda düşüyor ve bunu `llm_budget_degraded` ile sayıyor — yani
    bu ekranın 0 göstermesi arızayı gizlemez, ölçüm başka yerde duruyor.
    """
    try:
        return await reserved_total_async(
            redis, tenant_id=tenant_id, period_key=llm_budget.period_key(period_start)
        )
    except Exception:
        return 0


@router.get("", response_model=UsageResponse)
async def get_usage(
    session: TenantSessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    redis: RedisDep,
) -> UsageResponse:
    """Aktif kiracının kullanımını döndürür.

    Abonelik yoksa ilk erişimde varsayılan FREE plan oluşturulur.
    """
    snapshot = await quota.compute_usage(session, principal.tenant_id)
    spend = await llm_budget.compute_spend(session)
    storage = await storage_quota.compute_storage_usage(
        session, principal.tenant_id, settings=settings
    )

    limit_try = snapshot.plan.llm_budget_try_per_month
    # Rezervasyon KULLANICI görünümüne de girer. Girmezse `remaining_try`,
    # kabul kontrolünün fiilen uyguladığı sınırdan (`tavan − rezervasyon`)
    # büyük çıkar: ekran "₺14 kaldı" derken sunucu reddeder ve arıza
    # kullanıcıya sebepsiz görünür. Redis okunamazsa 0'a düşülür — sayı
    # görüntüdür, karar değil (bkz. `_reserved_micros`).
    reserved_try = round(
        await _reserved_micros(redis, principal.tenant_id, spend.period_start) / MICROS_PER_TRY, 2
    )
    remaining = None if limit_try is None else max(0.0, limit_try - spend.spent_try - reserved_try)
    soft = (
        limit_try is not None and spend.spent_try >= limit_try * settings.llm_budget_soft_threshold
    )

    return UsageResponse(
        plan=snapshot.plan.tier,
        plan_name=snapshot.plan.display_name,
        status=snapshot.status,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        documents=QuotaUsage(used=snapshot.documents_used, limit=snapshot.plan.documents_per_month),
        pages=QuotaUsage(used=snapshot.pages_used, limit=snapshot.plan.pages_per_month),
        budget=BudgetUsage(
            spent_try=round(spend.spent_try, 2),
            limit_try=None if limit_try is None else float(limit_try),
            reserved_try=reserved_try,  # HARCANMIŞ değil — arayüz ayrı segment çizer
            remaining_try=None if remaining is None else round(remaining, 2),
            soft_exceeded=soft,
        ),
        storage=StorageUsageResponse(
            used_bytes=storage.used_bytes,
            limit_bytes=storage.limit_bytes,
            remaining_bytes=storage.remaining_bytes,
            soft_exceeded=storage.soft_exceeded,
        ),
    )


@router.get("/admin", response_model=AdminUsageResponse, dependencies=[_admin_only])
async def get_admin_usage(
    session: TenantSessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    redis: RedisDep,
) -> AdminUsageResponse:
    """Yönetici teşhis görünümü — YALNIZ kiracı yöneticisi.

    Kapsam kiracının KENDİsidir (RLS): bu bir operatör/çapraz-kiracı ucu
    değildir. Başka kiracının harcaması buradan görünmez.
    """
    spend = await llm_budget.compute_spend(session)
    plan = get_plan((await quota.get_or_create_subscription(session, principal.tenant_id)).plan)
    posture = evaluate_pricing_posture(settings)
    reserved = await _reserved_micros(redis, principal.tenant_id, spend.period_start)
    limit_try = plan.llm_budget_try_per_month

    return AdminUsageResponse(
        period_start=spend.period_start,
        period_end=spend.period_end,
        spent_try=round(spend.spent_try, 2),
        limit_try=None if limit_try is None else float(limit_try),
        reserved_try=round(reserved / MICROS_PER_TRY, 2),
        calls=spend.calls,
        unpriced_calls=spend.unpriced_calls,
        fx_rate_missing=posture.fx_rate_missing,
        fx_rate_stale=posture.fx_rate_stale or posture.fx_rate_date_missing,
        fx_rate_age_days=posture.fx_rate_age_days,
        unverified_models=list(posture.unverified_models),
    )
