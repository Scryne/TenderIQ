"""/api/v1/billing — planlar, checkout ve webhook (Sprint 3.3-B).

- ``GET /billing/plans``: mevcut plan kademeleri + kiracının geçerli kademesi (her rol).
- ``POST /billing/checkout``: bir plana yükseltme başlatır (admin). Test-modu (manual)
  sağlayıcıda plan anında etkinleşir; gerçek sağlayıcıda ``checkout_url`` döner.
- ``POST /billing/webhook``: sağlayıcıdan gelen olay (kimliksiz — HMAC imzayla doğrulanır);
  idempotent uygulanır (aynı olay iki kez gelirse durum bir kez uygulanır).
"""

from __future__ import annotations

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
from tenderiq_api.errors import AppError, ErrorCode, ValidationFailedError
from tenderiq_core.billing.plans import PLANS, Plan, PlanTier
from tenderiq_core.billing.provider import (
    BillingError,
    WebhookVerificationError,
    create_billing_provider,
)
from tenderiq_core.logging import get_logger
from tenderiq_core.models import AuditAction, Role
from tenderiq_core.services import billing as billing_service
from tenderiq_core.services import quota
from tenderiq_core.services.audit import record_audit

logger = get_logger("tenderiq.api.billing")

router = APIRouter(prefix="/billing", tags=["billing"])

_admin = Depends(require_role(Role.ADMIN))


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
    """Checkout sonucu: anında etkinleşti mi, yoksa ağ geçidine mi yönlendirilecek."""

    provider: str
    activated: bool
    checkout_url: str | None
    plan: PlanTier


class WebhookResponse(BaseModel):
    """Webhook işleme sonucu."""

    status: str  # "applied" | "duplicate"


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


@router.post("/checkout", response_model=CheckoutResponse, dependencies=[_admin])
async def create_checkout(
    body: CheckoutRequest,
    session: TenantSessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
) -> CheckoutResponse:
    """Bir plana geçiş/yükseltme başlatır (admin).

    Test-modu (manual) sağlayıcıda plan anında etkinleşir ve denetime yazılır; gerçek
    sağlayıcıda ``checkout_url`` döner (etkinleşme webhook'la gelir).
    """
    try:
        provider = create_billing_provider(
            settings.billing_provider, webhook_secret=settings.billing_webhook_secret
        )
    except BillingError as exc:
        raise AppError(str(exc), code=ErrorCode.INTERNAL_ERROR, status_code=503) from exc

    result, subscription, old_plan = await billing_service.start_checkout(
        session, provider, tenant_id=principal.tenant_id, target_tier=body.plan
    )
    if result.activated and subscription is not None and old_plan is not None:
        record_audit(
            session,
            tenant_id=principal.tenant_id,
            action=AuditAction.SUBSCRIPTION_CHANGED,
            resource_type="subscription",
            resource_id=subscription.id,
            actor_user_id=principal.user_id,
            meta={
                "old_plan": old_plan.value,
                "new_plan": body.plan.value,
                "source": "checkout",
                "provider": result.provider,
            },
        )
    return CheckoutResponse(
        provider=result.provider,
        activated=result.activated,
        checkout_url=result.checkout_url,
        plan=body.plan,
    )


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
    try:
        provider = create_billing_provider(
            settings.billing_provider, webhook_secret=settings.billing_webhook_secret
        )
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
    logger.info(
        "billing_webhook_islendi",
        provider=provider.name,
        event_type=event.event_type,
        outcome=outcome,
    )
    return WebhookResponse(status=outcome)
