"""Abonelik/ödeme servisi (Sprint 3.3-B) — checkout başlatma + webhook uygulama.

Plan değişimi tek yerden (``apply_plan_change``) uygulanır ve idempotenttir (aynı
duruma tekrar yazmak zararsızdır). Webhook idempotency'si Redis'te olay-kimliği
tekilleştirmesiyle sağlanır.

**İşaret sırası kritiktir:** "işlendi" damgası olay UYGULANIP COMMIT EDİLDİKTEN
sonra yazılır (``mark_webhook_processed``). Damga önce yazılsaydı, uygulama veya
commit başarısız olduğunda damga Redis'te kalır ve sağlayıcının retry'ı
"duplicate" yanıtı alırdı — müşteri ödemesini yapmış ama planı hiç yükselmemiş
olurdu, üstelik sessizce. Bu sıralamanın bedeli, eşzamanlı gelen iki kopyanın
olayı iki kez uygulayabilmesidir; ``apply_plan_change`` idempotent olduğu için
bu zararsızdır (aynı duruma iki kez yazmak).

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

    Dönen değer: ``"duplicate"`` (daha önce BAŞARIYLA işlenmiş), ``"stale"``
    (sırasız gelmiş ESKİ olay — yok sayıldı) veya ``"applied"``.
    ``"applied"`` dönerse çağıran, transaction'ı commit ettikten SONRA
    ``mark_webhook_processed`` çağırmalıdır (sıralama gerekçesi modül docstring'inde).
    Olayda kiracı kimliği yoksa hata (imzalı gövde kiracıyı taşımalı). Redis
    kesintisinde tekilleştirme atlanır ama durum uygulaması zaten idempotenttir.
    """
    if event.tenant_id is None:
        from tenderiq_core.billing.provider import BillingError

        raise BillingError("Webhook olayında kiracı kimliği (tenant_id) yok.")

    # Yalnız OKUMA: damga başarılı uygulamadan sonra yazılır (bkz. docstring).
    try:
        if await redis.get(_dedup_key(provider, event.event_id)) is not None:
            return "duplicate"
    except RedisError as exc:
        # Tekilleştirme yumuşak: uygulama idempotent olduğundan çift-işlem zararsız.
        logger.warning("webhook_dedup_atlandi", error=str(exc))

    await set_tenant_context(session, event.tenant_id)
    subscription = await quota.get_or_create_subscription(session, event.tenant_id)

    # Sırasız teslim koruması. Webhook'lar sıra garantisi VERMEZ: sağlayıcının
    # yeniden denemesi ya da kuyruk gecikmesi yüzünden eski bir olay yenisinden
    # SONRA gelebilir. Damgasız uygulasaydık, geç gelen bir "iptal edildi"
    # olayı sonradan gelmiş "yeniden etkinleşti"yi ezer ve müşterinin ÖDEDİĞİ
    # erişimi kapatırdı — sessizce, ve ancak müşteri şikâyet edince fark edilir.
    #
    # Damgası olmayan olay (occurred_at=None) yok sayılmaz: eski sağlayıcı
    # gövdeleri ve manual sağlayıcı damga taşımayabilir; koruma ancak
    # karşılaştırılabilir iki damga varken devreye girer.
    if (
        event.occurred_at is not None
        and subscription.last_event_at is not None
        and event.occurred_at <= subscription.last_event_at
    ):
        logger.info(
            "webhook_eski_olay_atlandi",
            provider=provider,
            event_type=event.event_type,
        )
        return "stale"

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
    if event.occurred_at is not None:
        subscription.last_event_at = event.occurred_at
    return "applied"


async def mark_webhook_processed(redis: Redis, *, provider: str, event_id: str) -> None:
    """Olayı "işlendi" damgalar — YALNIZCA uygulama commit edildikten sonra.

    Commit'ten önce çağrılırsa başarısız bir uygulama kalıcı olarak "duplicate"
    görünür ve sağlayıcının retry'ı etkiyi hiç uygulamaz. Redis kesintisinde
    damga atlanır: olay tekrar gelirse yeniden uygulanır (idempotent).
    """
    try:
        await redis.set(_dedup_key(provider, event_id), "1", ex=WEBHOOK_DEDUP_TTL_SECONDS)
    except RedisError as exc:
        logger.warning("webhook_dedup_yazilamadi", error=str(exc))
