"""Abonelik/ödeme servisi (Sprint 3.3-B) — checkout başlatma + webhook uygulama.

Plan değişimi tek yerden (``apply_plan_change``) uygulanır ve idempotenttir (aynı
duruma tekrar yazmak zararsızdır). Webhook idempotency'si Redis'te olay-kimliği
tekilleştirmesiyle sağlanır; olay iki kez gelse bile durum yalnız bir kez uygulanır
ve zaten idempotent olduğundan çift-faturalama/çift-etki oluşmaz.

Kiracı bağlamı (RLS): ``apply_plan_change`` çağıranın kiracı bağlamını ayarlamış
olmasını bekler. Webhook yolu kimliksizdir; ``apply_webhook_event`` olayın (imzalı
gövdeden gelen, güvenilir) ``tenant_id``'sini bağlama yazar.
"""

from __future__ import annotations

import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.billing.plans import DEFAULT_PLAN_TIER, PlanTier
from tenderiq_core.billing.provider import BillingProvider, CheckoutResult, WebhookEvent
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Subscription, SubscriptionStatus
from tenderiq_core.services import quota

logger = get_logger("tenderiq.core.billing")

# İşlenmiş webhook olaylarının Redis'te tutulma süresi (idempotency penceresi).
WEBHOOK_DEDUP_TTL_SECONDS = 90 * 24 * 3600


def _dedup_key(provider: str, event_id: str) -> str:
    return f"billing:event:{provider}:{event_id}"


async def apply_plan_change(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    plan: PlanTier,
    status: SubscriptionStatus,
    provider: str | None = None,
    provider_customer_id: str | None = None,
    provider_subscription_id: str | None = None,
) -> tuple[Subscription, PlanTier]:
    """Kiracının aboneliğini hedef plana/duruma getirir (idempotent).

    Önceki plan kademesini de döndürür (denetim/log için). Kiracı bağlamı ayarlı bir
    oturumda çağrılmalıdır (RLS). Flush/commit çağıranın sorumluluğundadır.
    """
    subscription = await quota.get_or_create_subscription(session, tenant_id)
    old_plan = subscription.plan
    subscription.plan = plan
    subscription.status = status
    if provider is not None:
        subscription.provider = provider
    if provider_customer_id is not None:
        subscription.provider_customer_id = provider_customer_id
    if provider_subscription_id is not None:
        subscription.provider_subscription_id = provider_subscription_id
    return subscription, old_plan


async def start_checkout(
    session: AsyncSession,
    provider: BillingProvider,
    *,
    tenant_id: uuid.UUID,
    target_tier: PlanTier,
) -> tuple[CheckoutResult, Subscription | None, PlanTier | None]:
    """Bir plan yükseltmesi başlatır.

    Test-modu (manual) sağlayıcı anında etkinleştirir → plan hemen uygulanır;
    güncellenen abonelik + önceki kademe döndürülür (denetim için). Gerçek sağlayıcı
    ``checkout_url`` döndürür (etkinleşme webhook'la gelir) → abonelik/old_plan ``None``.
    """
    result = await provider.create_checkout(tenant_id=tenant_id, target_tier=target_tier)
    if not result.activated:
        return result, None, None
    subscription, old_plan = await apply_plan_change(
        session,
        tenant_id=tenant_id,
        plan=target_tier,
        status=SubscriptionStatus.ACTIVE,
        provider=result.provider,
        provider_customer_id=result.provider_customer_id,
        provider_subscription_id=result.provider_subscription_id,
    )
    return result, subscription, old_plan


def _resolve_target(
    event: WebhookEvent, current_plan: PlanTier
) -> tuple[PlanTier, SubscriptionStatus]:
    """Olay türüne göre hedef plan + durum belirler."""
    if event.event_type == "subscription.canceled":
        return DEFAULT_PLAN_TIER, SubscriptionStatus.CANCELED
    if event.event_type == "subscription.past_due":
        # Plan korunur; yalnız durum düşer (kota dondurma kararı ayrıca alınır).
        return current_plan, SubscriptionStatus.PAST_DUE
    # activated / updated: olaydaki plan uygulanır (yoksa mevcut korunur).
    return event.plan_tier or current_plan, event.status


async def apply_webhook_event(
    session: AsyncSession, redis: Redis, event: WebhookEvent, *, provider: str
) -> str:
    """Doğrulanmış bir webhook olayını idempotent uygular.

    Dönen değer: ``"duplicate"`` (daha önce işlenmiş) veya ``"applied"``. Olayda
    kiracı kimliği yoksa hata (imzalı gövde kiracıyı taşımalı). Redis kesintisinde
    idempotency atlanır ama durum uygulaması zaten idempotent olduğundan güvenlidir.
    """
    if event.tenant_id is None:
        from tenderiq_core.billing.provider import BillingError

        raise BillingError("Webhook olayında kiracı kimliği (tenant_id) yok.")

    # Idempotency: olay daha önce işlendiyse (SET NX başarısız) tekrar uygulama.
    try:
        stored = await redis.set(
            _dedup_key(provider, event.event_id), "1", nx=True, ex=WEBHOOK_DEDUP_TTL_SECONDS
        )
        if stored is None:
            return "duplicate"
    except RedisError as exc:
        # Idempotency yumuşak: uygulama idempotent olduğundan çift-işlem zararsız.
        logger.warning("webhook_dedup_atlandi", error=str(exc))

    await set_tenant_context(session, event.tenant_id)
    subscription = await quota.get_or_create_subscription(session, event.tenant_id)
    target_plan, target_status = _resolve_target(event, subscription.plan)
    await apply_plan_change(
        session,
        tenant_id=event.tenant_id,
        plan=target_plan,
        status=target_status,
        provider=provider,
        provider_customer_id=event.provider_customer_id,
        provider_subscription_id=event.provider_subscription_id,
    )
    return "applied"
