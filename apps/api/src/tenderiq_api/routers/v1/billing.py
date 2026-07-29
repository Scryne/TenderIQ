"""/api/v1/billing — planlar, abonelik yaşam döngüsü ve webhook (Sprint 3.3-B).

- ``GET /billing/plans``: mevcut plan kademeleri + kiracının geçerli kademesi (her rol).
- ``GET /billing/subscription``: aboneliğin durumu, sıradaki tahsilat tarihi, bekleyen
  iptal/düşürme (her rol — yalnız yönetici *değiştirebilir*, herkes *görebilir*).
- ``POST /billing/checkout``: bir plana geçiş başlatır (admin). Mevcut bir abonelik
  varsa plan değişimine yönlenir: yükseltme anında, düşürme dönem sonunda.
- ``POST /billing/subscription/cancel``: aboneliği dönem sonunda bitirir (admin).
- ``POST /billing/subscription/resume``: iptali dönem sonundan önce geri alır (admin).
- ``POST /billing/webhook``: sağlayıcıdan gelen olay (kimliksiz — HMAC imzayla doğrulanır);
  idempotent uygulanır (aynı olay iki kez gelirse durum bir kez uygulanır).

**Kiracı sınırı yapısaldır.** Yaşam döngüsü uçlarının hiçbiri gövdeden ya da
yoldan kiracı/abonelik kimliği ALMAZ; hepsi ``principal.tenant_id`` üzerinde
çalışır ve ``TenantSessionDep`` ile RLS bağlamı kurulur. Böylece "başka kiracının
aboneliğini iptal et" diye bir istek İFADE EDİLEMEZ — yetki kontrolü unutulsa
bile sızıntı olmaz.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from tenderiq_api.dependencies import (
    PrincipalDep,
    RedisDep,
    SessionDep,
    SettingsDep,
    TenantSessionDep,
    require_role,
)
from tenderiq_api.errors import AppError, ConflictError, ErrorCode, ValidationFailedError
from tenderiq_core.billing.plans import PLANS, Plan, PlanTier, get_plan
from tenderiq_core.billing.provider import (
    BillingError,
    BillingProvider,
    WebhookVerificationError,
    create_billing_provider,
)
from tenderiq_core.logging import get_logger
from tenderiq_core.models import AuditAction, Role, Subscription, SubscriptionStatus
from tenderiq_core.services import billing as billing_service
from tenderiq_core.services import quota
from tenderiq_core.services.audit import record_audit

logger = get_logger("tenderiq.api.billing")

router = APIRouter(prefix="/billing", tags=["billing"])

_admin = Depends(require_role(Role.ADMIN))


def _provider(settings: SettingsDep) -> BillingProvider:
    """Yapılandırılmış sağlayıcıyı üretir; bağlı değilse 503.

    Sağlayıcının yapılandırılmamış olması bir kullanıcı hatası değildir —
    yapılandırma eksiğidir; 4xx dönmek kullanıcıyı kendi isteğini düzeltmeye
    çalıştırırdı.
    """
    try:
        return create_billing_provider(
            settings.billing_provider,
            webhook_secret=settings.billing_webhook_secret,
            settings=settings,
        )
    except BillingError as exc:
        raise AppError(str(exc), code=ErrorCode.INTERNAL_ERROR, status_code=503) from exc


class PlanInfo(BaseModel):
    """Bir plan kademesinin kullanıcıya-görünür tanımı."""

    tier: PlanTier
    display_name: str
    documents_per_month: int | None
    pages_per_month: int | None
    monthly_price_try: int
    is_current: bool


class CheckoutRequest(BaseModel):
    """Bir plana yükseltme/geçiş talebi."""

    plan: PlanTier


class CheckoutResponse(BaseModel):
    """Checkout/plan değişimi sonucu.

    ``activated`` plan ANINDA açıldı mı (yükseltme ya da test-modu). ``checkout_url``
    doluysa kullanıcı ağ geçidine yönlendirilir. ``effective_at`` doluysa değişim
    henüz uygulanmadı ve o tarihte uygulanacaktır (düşürme, `/sartlar` §3).
    """

    provider: str
    activated: bool
    checkout_url: str | None
    plan: PlanTier
    effective_at: datetime | None = None


class SubscriptionResponse(BaseModel):
    """Kiracının abonelik durumu — iptal/geri alma arayüzünün tek kaynağı."""

    plan: PlanTier
    plan_name: str
    status: SubscriptionStatus
    provider: str | None
    #: İptal edildi; erişim ``current_period_end``e kadar sürüyor.
    cancel_at_period_end: bool
    #: Ödenmiş dönemin bitişi. İptal edilmişse "erişim şu tarihe kadar sürüyor",
    #: edilmemişse sıradaki tahsilat tarihidir (``next_charge_at``).
    current_period_end: datetime | None
    #: Sıradaki tahsilat tarihi; iptal edilmişse ya da ücretsiz plandaysa ``None``
    #: — iptal etmiş kullanıcıya "sıradaki tahsilat" göstermek yanlış olurdu.
    next_charge_at: datetime | None
    #: Dönem sonunda geçilecek kademe (düşürme talebi).
    pending_plan: PlanTier | None
    pending_plan_name: str | None
    #: Yönetici bu aboneliği iptal edebilir mi (ücretsiz planda edilecek bir şey yok).
    can_cancel: bool
    #: İptal geri alınabilir mi (dönem sonu henüz geçmemişse).
    can_resume: bool


class WebhookResponse(BaseModel):
    """Webhook işleme sonucu.

    ``applied`` uygulandı · ``duplicate`` daha önce işlenmiş (idempotency) ·
    ``stale`` sırasız gelmiş ESKİ olay, yok sayıldı. Üçü de 200'dür: sağlayıcı
    için "aldım, işim bitti" demektir ve yeniden deneme gerektirmez.
    """

    status: str  # "applied" | "duplicate" | "stale"


def _subscription_response(subscription: Subscription) -> SubscriptionResponse:
    """Abonelik satırını arayüzün ihtiyaç duyduğu türetilmiş alanlarla döndürür.

    ``can_cancel``/``can_resume`` ve ``next_charge_at`` burada TEK yerde
    hesaplanır: arayüz aynı koşulları kendi kurarsa (ör. "planı free değilse
    iptal edilebilir") sunucu kuralı değiştiğinde sessizce ayrışır ve kullanıcıya
    çalışmayan bir buton gösterilir.
    """
    paid = subscription.plan != PlanTier.FREE
    canceling = subscription.cancel_at_period_end
    return SubscriptionResponse(
        plan=subscription.plan,
        plan_name=get_plan(subscription.plan).display_name,
        status=subscription.status,
        provider=subscription.provider,
        cancel_at_period_end=canceling,
        current_period_end=subscription.current_period_end,
        next_charge_at=None if canceling or not paid else subscription.current_period_end,
        pending_plan=subscription.pending_plan,
        pending_plan_name=(
            get_plan(subscription.pending_plan).display_name
            if subscription.pending_plan is not None
            else None
        ),
        can_cancel=paid and not canceling,
        can_resume=canceling,
    )


def _plan_info(plan: Plan, *, current: PlanTier) -> PlanInfo:
    return PlanInfo(
        tier=plan.tier,
        display_name=plan.display_name,
        documents_per_month=plan.documents_per_month,
        pages_per_month=plan.pages_per_month,
        monthly_price_try=plan.monthly_price_try,
        is_current=plan.tier == current,
    )


@router.get("/plans", response_model=list[PlanInfo])
async def list_plans(session: TenantSessionDep, principal: PrincipalDep) -> list[PlanInfo]:
    """Mevcut plan kademelerini listeler; kiracının geçerli kademesini işaretler."""
    subscription = await quota.get_or_create_subscription(session, principal.tenant_id)
    return [_plan_info(plan, current=subscription.plan) for plan in PLANS.values()]


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    session: TenantSessionDep, principal: PrincipalDep
) -> SubscriptionResponse:
    """Kiracının abonelik durumunu döndürür (her rol görebilir).

    Görüntüleme yönetici yetkisi istemez: hangi planda olduğunu, ne zaman
    yenileneceğini ve iptal edilip edilmediğini bilmek ekibin tamamını ilgilendirir.
    Değiştirme uçları ayrıca yöneticiyle sınırlıdır.
    """
    subscription = await quota.get_or_create_subscription(session, principal.tenant_id)
    return _subscription_response(subscription)


@router.post("/checkout", response_model=CheckoutResponse, dependencies=[_admin])
async def create_checkout(
    body: CheckoutRequest,
    session: TenantSessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
) -> CheckoutResponse:
    """Bir plana geçiş başlatır (admin).

    Kiracının sağlayıcıda aboneliği yoksa yeni satın alma başlar (test-modunda
    plan anında etkinleşir; gerçek sağlayıcıda ``checkout_url`` döner ve
    etkinleşme webhook'la gelir). Aboneliği VARSA `/sartlar` §3 uygulanır:
    yükseltme anında, düşürme dönem sonunda.
    """
    provider = _provider(settings)
    try:
        result = await billing_service.request_plan_change(
            session, provider, tenant_id=principal.tenant_id, target_tier=body.plan
        )
    except billing_service.SubscriptionStateError as exc:
        raise ConflictError(str(exc)) from exc
    except BillingError as exc:
        # Sağlayıcı reddetti/ulaşılamadı: hiçbir şey commit edilmedi.
        raise AppError(str(exc), code=ErrorCode.INTERNAL_ERROR, status_code=503) from exc

    if result.subscription is not None and result.previous_plan is not None:
        record_audit(
            session,
            tenant_id=principal.tenant_id,
            action=AuditAction.SUBSCRIPTION_CHANGED,
            resource_type="subscription",
            resource_id=result.subscription.id,
            actor_user_id=principal.user_id,
            meta={
                "old_plan": result.previous_plan.value,
                "new_plan": body.plan.value,
                "source": "checkout",
                "provider": provider.name,
                "effective_at": (
                    result.effective_at.isoformat() if result.effective_at is not None else "now"
                ),
            },
        )
    return CheckoutResponse(
        provider=provider.name,
        activated=result.checkout is None and result.effective_at is None,
        checkout_url=result.checkout.checkout_url if result.checkout is not None else None,
        plan=body.plan,
        effective_at=result.effective_at,
    )


@router.post("/subscription/cancel", response_model=SubscriptionResponse, dependencies=[_admin])
async def cancel_subscription(
    session: TenantSessionDep, principal: PrincipalDep, settings: SettingsDep
) -> SubscriptionResponse:
    """Aboneliği dönem sonunda bitecek şekilde iptal eder (admin).

    Erişim ödenmiş dönemin sonuna kadar sürer (`/sartlar` §3); yanıttaki
    ``current_period_end`` kullanıcıya gösterilecek tarihtir. İşlem tek adımdır
    ve geri alınabilir — 14 gün koşulsuz cayma hakkı ayrıca işler.
    """
    provider = _provider(settings)
    try:
        subscription = await billing_service.schedule_cancellation(
            session, provider, tenant_id=principal.tenant_id
        )
    except billing_service.SubscriptionStateError as exc:
        raise ConflictError(str(exc)) from exc
    except BillingError as exc:
        raise AppError(str(exc), code=ErrorCode.INTERNAL_ERROR, status_code=503) from exc

    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.SUBSCRIPTION_CHANGED,
        resource_type="subscription",
        resource_id=subscription.id,
        actor_user_id=principal.user_id,
        meta={
            "old_plan": subscription.plan.value,
            "new_plan": subscription.plan.value,
            "source": "cancel",
            "provider": provider.name,
            "effective_at": (
                subscription.current_period_end.isoformat()
                if subscription.current_period_end is not None
                else None
            ),
        },
    )
    return _subscription_response(subscription)


@router.post("/subscription/resume", response_model=SubscriptionResponse, dependencies=[_admin])
async def resume_subscription(
    session: TenantSessionDep, principal: PrincipalDep, settings: SettingsDep
) -> SubscriptionResponse:
    """İptali geri alır — dönem sonu henüz geçmemişse (admin)."""
    provider = _provider(settings)
    try:
        subscription = await billing_service.resume_subscription(
            session, provider, tenant_id=principal.tenant_id
        )
    except billing_service.SubscriptionStateError as exc:
        raise ConflictError(str(exc)) from exc
    except BillingError as exc:
        raise AppError(str(exc), code=ErrorCode.INTERNAL_ERROR, status_code=503) from exc

    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.SUBSCRIPTION_CHANGED,
        resource_type="subscription",
        resource_id=subscription.id,
        actor_user_id=principal.user_id,
        meta={
            "old_plan": subscription.plan.value,
            "new_plan": subscription.plan.value,
            "source": "resume",
            "provider": provider.name,
        },
    )
    return _subscription_response(subscription)


@router.post("/webhook", response_model=WebhookResponse)
async def billing_webhook(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> WebhookResponse:
    """Ödeme sağlayıcısı webhook'u (kimliksiz; HMAC imzayla doğrulanır, idempotent).

    İmza geçersizse 400. Olay daha önce işlenmişse durum tekrar uygulanmaz
    (``duplicate``). Kiracı bağlamı olayın imzalı gövdesinden (güvenilir) türetilir.
    """
    raw_body = await request.body()
    provider = _provider(settings)
    try:
        event = provider.parse_webhook(headers=request.headers, raw_body=raw_body)
    except WebhookVerificationError as exc:
        raise ValidationFailedError("Webhook doğrulanamadı.") from exc
    except BillingError as exc:
        raise AppError(str(exc), code=ErrorCode.INTERNAL_ERROR, status_code=503) from exc

    async with session.begin():
        try:
            outcome = await billing_service.apply_webhook_event(
                session, redis, event, provider=provider.name
            )
        except BillingError as exc:
            raise ValidationFailedError("Webhook olayı işlenemedi.") from exc
    # "İşlendi" damgası COMMIT SONRASI yazılır: uygulama/commit başarısız olursa
    # damga kalmaz ve sağlayıcının retry'ı olayı gerçekten uygulayabilir.
    if outcome == "applied":
        await billing_service.mark_webhook_processed(
            redis, provider=provider.name, event_id=event.event_id
        )
    logger.info(
        "billing_webhook_islendi",
        provider=provider.name,
        event_type=event.event_type,
        outcome=outcome,
    )
    return WebhookResponse(status=outcome)
