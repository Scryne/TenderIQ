"""Abonelik olaylarında e-posta bildirimi.

**Gönderim, olayı uygulayan transaction'ın DIŞINDADIR ve sonrasındadır.** Bu
sıralama bir tercih değil, doğruluk şartı:

* Aynı transaction içinde gönderseydik, e-posta sağlayıcısının bir hatası
  yetkilendirme değişikliğini geri sardırırdı — müşteri ödemiş, planı açılmamış
  olurdu. Ödemenin karşılığını vermemek, bildirim gönderememekten kat kat ağır.
* Gönderim hatası isteği DÜŞÜRMEZ. Düşürseydi sağlayıcı 5xx görüp aynı olayı
  yeniden gönderir ve durum ikinci kez uygulanırdı; yani "e-posta gidemedi"
  arızası bir "abonelik iki kez işlendi" arızasına dönüşürdü.

**Alıcı: kiracının yöneticileri.** Ödeme ve erişim kararları organizasyonu
ilgilendirir, tek bir kişiyi değil; ayrıca aboneliği başlatan kişi ayrılmış
olabilir. Üyelere gönderilmez — plan değişikliği onların işi değil ve gereksiz
e-posta bastırma listesine düşme riskidir.

Tekrar koruması şablonların ``idempotency_key``inden gelir (``<tür>:<event_id>``):
sağlayıcı aynı olayı mükerrer teslim ettiğinde kullanıcı iki kez "ödemeniz
alındı" almaz.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.billing.plans import PlanTier, get_plan
from tenderiq_core.billing.provider import WebhookEvent
from tenderiq_core.config import Settings
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.email import templates
from tenderiq_core.email.message import EmailMessage
from tenderiq_core.email.provider import EmailProvider
from tenderiq_core.email.service import send_email
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Membership, Role, Subscription, User

logger = get_logger("tenderiq.core.billing.notifications")


def _format_date(value: datetime | None) -> str:
    """Türkçe kısa tarih. Bilinmiyorsa eksiz bir kalıp — uydurma tarih YAZILMAZ.

    "Bilinmiyor" demek, yanlış bir tarih yazmaktan iyidir: kullanıcı o tarihe
    göre plan yapar.
    """
    return value.strftime("%d.%m.%Y") if value is not None else "bilinmiyor"


async def admin_recipients(session: AsyncSession, tenant_id: uuid.UUID) -> list[str]:
    """Kiracının yönetici e-posta adresleri.

    ``Membership`` RLS'siz bir kimlik tablosudur; bu sorgu kiracı bağlamından
    bağımsız çalışır. Pasif kullanıcılar dışlanır — hesabı kapatılmış birine
    fatura bildirimi göndermek hem yararsız hem de bounce üretir.
    """
    rows = await session.scalars(
        select(User.email)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.organization_id == tenant_id,
            Membership.role == Role.ADMIN,
            User.is_active.is_(True),
        )
    )
    return list(rows.all())


def build_message(
    *,
    event_type: str,
    to: str,
    plan: PlanTier,
    event_id: str,
    period_end: datetime | None,
    billing_url: str,
) -> EmailMessage | None:
    """Olay türünü şablona eşler. Bildirim gerektirmeyen olayda ``None``.

    Her olay için e-posta YOKTUR ve olmamalıdır: ``subscription.updated`` gibi
    kullanıcıya bir şey söylemeyen olaylar için mesaj üretmek, gerçekten önemli
    olanların okunmamasına yol açar.
    """
    plan_name = get_plan(plan).display_name
    period_text = _format_date(period_end)

    if event_type in {"subscription.activated", "subscription.started"}:
        return templates.subscription_started(
            to=to,
            plan=plan_name,
            next_charge_text=period_text,
            link=billing_url,
            event_id=event_id,
        )
    if event_type in {"subscription.renewed", "subscription.payment_succeeded"}:
        return templates.subscription_renewed(
            to=to,
            plan=plan_name,
            next_charge_text=period_text,
            link=billing_url,
            event_id=event_id,
        )
    if event_type == "subscription.past_due":
        return templates.payment_failed(
            to=to,
            plan=plan_name,
            attempt=1,
            max_attempts=3,
            link=billing_url,
            event_id=event_id,
        )
    if event_type in {"subscription.suspended", "subscription.unpaid"}:
        return templates.subscription_suspended(
            to=to, plan=plan_name, link=billing_url, event_id=event_id
        )
    if event_type in {"subscription.canceled", "subscription.expired"}:
        return templates.subscription_canceled(
            to=to, plan=plan_name, access_until_text=period_text, event_id=event_id
        )
    if event_type == "subscription.resumed":
        return templates.subscription_resumed(
            to=to,
            plan=plan_name,
            next_charge_text=period_text,
            link=billing_url,
            event_id=event_id,
        )
    return None


async def send_subscription_emails(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    provider: EmailProvider,
    tenant_id: uuid.UUID,
    event_type: str,
    event_id: str,
    plan: PlanTier,
    period_end: datetime | None,
) -> int:
    """Bir abonelik olayı için yöneticilere e-posta gönderir; gönderilen sayısı.

    **Hiçbir hata yukarı verilmez.** Çağıran yol (webhook ya da iptal ucu) çoktan
    commit edilmiştir; buradaki bir istisna, başarıyla tamamlanmış bir işlemi
    başarısız göstermekten başka bir işe yaramaz.
    """
    sent = 0
    try:
        recipients = await admin_recipients(session, tenant_id)
        if not recipients:
            logger.warning("abonelik_bildirimi_alici_yok", tenant_id=str(tenant_id))
            return 0
        for recipient in recipients:
            message = build_message(
                event_type=event_type,
                to=recipient,
                plan=plan,
                event_id=event_id,
                period_end=period_end,
                billing_url=f"{settings.app_base_url.rstrip('/')}/usage",
            )
            if message is None:
                return 0  # bu olay türü bildirim gerektirmiyor
            outcome = await send_email(
                message,
                provider=provider,
                settings=settings,
                session=session,
                redis=redis,
            )
            if outcome.value == "sent":
                sent += 1
    except Exception as exc:
        logger.warning(
            "abonelik_bildirimi_gonderilemedi",
            tenant_id=str(tenant_id),
            event_type=event_type,
            error=str(exc),
        )
    return sent


async def notify_subscription_event(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    email_provider: EmailProvider,
    event: WebhookEvent,
) -> int:
    """Webhook yolundan bildirim — olay uygulanıp COMMIT EDİLDİKTEN sonra çağrılır."""
    if event.tenant_id is None:
        return 0
    # Planı ve dönem sonunu aynadan okuruz, olaydan değil: olay bunları taşımak
    # zorunda değil ve kullanıcıya söyleyeceğimiz şey NİHAİ durumdur.
    #
    # Kiracı bağlamı YENİDEN kurulur: GUC transaction-local'dır (bkz. db.tenant)
    # ve olayı uygulayan transaction commit edildiğinde düşer. Kurmadan okumak
    # RLS yüzünden sessizce boş döner — yani bildirim hiç gitmez ve kimse fark
    # etmez.
    try:
        async with session.begin():
            await set_tenant_context(session, event.tenant_id)
            subscription = await session.scalar(
                select(Subscription).where(Subscription.tenant_id == event.tenant_id)
            )
    except SQLAlchemyError as exc:
        logger.warning("abonelik_bildirimi_durum_okunamadi", error=str(exc))
        return 0
    if subscription is None:
        return 0
    return await send_subscription_emails(
        session,
        redis,
        settings,
        provider=email_provider,
        tenant_id=event.tenant_id,
        event_type=event.event_type,
        event_id=event.event_id,
        plan=subscription.plan,
        period_end=subscription.current_period_end,
    )


async def notify_local_action(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    email_provider: EmailProvider,
    tenant_id: uuid.UUID,
    action: str,
    subscription: Subscription,
) -> int:
    """Kendi uçlarımızdan tetiklenen bildirim (iptal / geri alma).

    Webhook'tan farkı olay kimliğinin **bizde** üretilmesidir. Anahtar
    aboneliğin o anki durumundan türetilir (``<eylem>:<abonelik>:<dönem sonu>``):
    aynı iptal iki kez tıklansa tek e-posta gider, ama gerçekten yeni bir iptal
    (yeni dönem) yeni e-posta üretir.
    """
    stamp = subscription.current_period_end.isoformat() if subscription.current_period_end else "-"
    event_id = f"local:{action}:{subscription.id}:{stamp}"
    return await send_subscription_emails(
        session,
        redis,
        settings,
        provider=email_provider,
        tenant_id=tenant_id,
        event_type=action,
        event_id=event_id,
        plan=subscription.plan,
        period_end=subscription.current_period_end,
    )


__all__: Sequence[str] = (
    "admin_recipients",
    "build_message",
    "notify_local_action",
    "notify_subscription_event",
    "send_subscription_emails",
)
