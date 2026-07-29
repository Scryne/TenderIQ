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

import hashlib
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from tenderiq_api.dependencies import (
    EmailProviderDep,
    PrincipalDep,
    RedisDep,
    SessionDep,
    SettingsDep,
    TenantSessionDep,
    require_role,
)
from tenderiq_api.errors import (
    AppError,
    ConflictError,
    ErrorCode,
    NotFoundError,
    ValidationFailedError,
)
from tenderiq_core.billing.plans import PLANS, Plan, PlanTier, get_plan
from tenderiq_core.billing.provider import (
    BillingError,
    BillingProvider,
    WebhookEvent,
    WebhookVerificationError,
    create_billing_provider,
)
from tenderiq_core.logging import get_logger
from tenderiq_core.models import (
    AuditAction,
    DeadLetterKind,
    DeadLetterStatus,
    Role,
    Subscription,
    SubscriptionStatus,
    WebhookDeadLetter,
)
from tenderiq_core.services import billing as billing_service
from tenderiq_core.services import dead_letter as dead_letter_service
from tenderiq_core.services import quota
from tenderiq_core.services.audit import record_audit
from tenderiq_core.services.dead_letter import DeadLetterError, TransientEventError
from tenderiq_core.services.subscription_notifications import (
    notify_local_action,
    notify_subscription_event,
)

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


async def _dead_letter_unparsed(
    session: SessionDep,
    redis: RedisDep,
    *,
    provider: str,
    raw_body: bytes,
    reason: str,
) -> None:
    """Doğrulanamayan gövdeyi kuyruğa yazar (ayrıştırılamadığı için alan yok).

    Olay kimliği bilinmediğinden gövdenin özeti kimlik olarak kullanılır: aynı
    bozuk gövde tekrar tekrar gelse de tek satır olur ve ``attempts`` artar.
    Kuyruk aynı arızanın kopyalarıyla dolmaz.
    """
    digest = hashlib.sha256(raw_body).hexdigest()[:32]
    try:
        async with session.begin():
            await dead_letter_service.enqueue(
                session,
                provider=provider,
                event_id=f"unverified:{digest}",
                event_type="unknown",
                tenant_id=None,
                signature_valid=False,
                kind=DeadLetterKind.PERMANENT,
                error=reason,
                raw_body=raw_body,
                redis=redis,
            )
    except SQLAlchemyError as exc:
        # Kuyruğa yazamamak isteğin sonucunu DEĞİŞTİRMEZ: imza zaten geçersiz ve
        # yanıt 400 olacak. Yutulmasının sebebi bu; sessiz kalmaması için loglanır.
        logger.warning("dlq_yazilamadi", provider=provider, error=str(exc))


async def _dead_letter_event(
    session: SessionDep,
    redis: RedisDep,
    *,
    provider: str,
    event: WebhookEvent,
    raw_body: bytes,
    failure: DeadLetterError,
) -> WebhookResponse:
    """Uygulanamayan (ama doğrulanmış) olayı kuyruğa yazar ve yanıtı belirler.

    Kuyruğa yazma AYRI bir transaction'dadır: olayı uygulayan transaction
    başarısız olup geri sarıldı; aynı oturumda devam etmek kuyruk kaydını da
    geri sardırırdı — yani tam olarak saklamak istediğimiz şeyi kaybederdik.
    """
    try:
        async with session.begin():
            row = await dead_letter_service.enqueue(
                session,
                provider=provider,
                event_id=event.event_id,
                event_type=event.event_type,
                tenant_id=event.tenant_id,
                signature_valid=True,
                kind=failure.kind,
                error=failure.reason,
                raw_body=raw_body,
                redis=redis,
            )
            attempts = row.attempts if row is not None else 1
    except SQLAlchemyError as exc:
        # Kuyruk da yazılamıyorsa altyapı gerçekten arızalıdır: sağlayıcıya
        # "sende kalsın, yeniden dene" demek (503) elimizdeki tek koruma.
        logger.error("dlq_yazilamadi", provider=provider, error=str(exc))
        raise AppError(
            "Webhook olayı işlenemedi.", code=ErrorCode.INTERNAL_ERROR, status_code=503
        ) from exc

    if failure.kind is DeadLetterKind.PERMANENT:
        raise ValidationFailedError(f"Webhook olayı işlenemedi: {failure.reason}")

    if attempts < dead_letter_service.MAX_TRANSIENT_ATTEMPTS:
        # Sağlayıcının kendi yeniden denemesi bunu çözebilir.
        raise AppError(
            "Webhook olayı geçici olarak işlenemedi.",
            code=ErrorCode.INTERNAL_ERROR,
            status_code=503,
        )
    # Tavan doldu: sağlayıcıyı durdur. Olay kuyrukta insanı bekliyor ve
    # yeniden deneme fırtınası gerçek arızayı log'da görünmez kılıyor.
    logger.error(
        "webhook_kalici_olarak_kuyruga_dustu",
        provider=provider,
        event_type=event.event_type,
        attempts=attempts,
    )
    return WebhookResponse(status="dead_lettered")


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
    session: TenantSessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    redis: RedisDep,
    email_provider: EmailProviderDep,
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
    response = _subscription_response(subscription)
    # Bildirim, isteği düşürmemesi için yanıt hazırlandıktan sonra tetiklenir;
    # gönderim hatası yutulur (bkz. subscription_notifications modül docstring'i).
    await notify_local_action(
        session,
        redis,
        settings,
        email_provider=email_provider,
        tenant_id=principal.tenant_id,
        action="subscription.canceled",
        subscription=subscription,
    )
    return response


@router.post("/subscription/resume", response_model=SubscriptionResponse, dependencies=[_admin])
async def resume_subscription(
    session: TenantSessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    redis: RedisDep,
    email_provider: EmailProviderDep,
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
    response = _subscription_response(subscription)
    await notify_local_action(
        session,
        redis,
        settings,
        email_provider=email_provider,
        tenant_id=principal.tenant_id,
        action="subscription.resumed",
        subscription=subscription,
    )
    return response


# ── Ölü mektup kuyruğu (yönetici) ────────────────────────────────────────────
#
# Kiracı sınırı RLS'te: ``webhook_dead_letter`` SELECT politikası yalnız kendi
# kiracısının satırlarını gösterir, bu yüzden liste ucu filtre YAZMAZ ve tekil
# uç "başkasının kaydı mı" diye kontrol ETMEZ — satır zaten görünmez, 404 olur.
# Atfedilemeyen (``tenant_id IS NULL``) olaylar hiçbir kiracıya görünmez;
# onlar operatör yüzeyinden (``/ops/metrics`` + log) izlenir.


class DeadLetterResponse(BaseModel):
    """Kuyruktaki tek bir olay (gövde REDAKTE edilmiş hâliyle)."""

    id: uuid.UUID
    provider: str
    event_id: str
    event_type: str
    signature_valid: bool
    kind: DeadLetterKind
    status: DeadLetterStatus
    error: str
    attempts: int
    payload: dict[str, object] | None
    last_attempt_at: datetime
    resolved_at: datetime | None


class DeadLetterRetryResponse(BaseModel):
    """Yeniden işleme sonucu."""

    #: ``applied`` · ``duplicate`` (zaten işlenmiş) · ``stale`` (eski olay)
    outcome: str
    dead_letter: DeadLetterResponse


def _dead_letter_response(row: WebhookDeadLetter) -> DeadLetterResponse:
    return DeadLetterResponse(
        id=row.id,
        provider=row.provider,
        event_id=row.event_id,
        event_type=row.event_type,
        signature_valid=row.signature_valid,
        kind=row.kind,
        status=row.status,
        error=row.error,
        attempts=row.attempts,
        payload=row.payload,
        last_attempt_at=row.last_attempt_at,
        resolved_at=row.resolved_at,
    )


@router.get("/dead-letters", response_model=list[DeadLetterResponse], dependencies=[_admin])
async def list_dead_letters(
    session: TenantSessionDep,
    status: Annotated[DeadLetterStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[DeadLetterResponse]:
    """Kiracının uygulanamamış ödeme olayları (admin)."""
    rows = await dead_letter_service.list_for_tenant(session, status=status, limit=limit)
    return [_dead_letter_response(row) for row in rows]


@router.post(
    "/dead-letters/{dead_letter_id}/retry",
    response_model=DeadLetterRetryResponse,
    dependencies=[_admin],
)
async def retry_dead_letter(
    dead_letter_id: uuid.UUID,
    session: TenantSessionDep,
    redis: RedisDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    email_provider: EmailProviderDep,
) -> DeadLetterRetryResponse:
    """Kuyruktaki bir olayı yeniden işler (admin).

    **Hiçbir korumayı atlamaz.** Olay, canlı webhook'la aynı yoldan
    (``apply_webhook_event``) geçer: idempotency damgası ve sırasız-olay
    (``occurred_at``) koruması aynen işler. Yani daha önce uygulanmış bir olay
    ``duplicate``, aboneliğin şimdiki durumundan eski bir olay ``stale`` döner
    ve durum DEĞİŞMEZ. Aksi hâlde "yeniden işle" düğmesi, iptal etmiş bir
    müşterinin aboneliğini geri açabilirdi.

    Olay kimliği **saklanan sütundan** alınır, gövdeden yeniden türetilmez:
    gövde redaktedir ve bazı sağlayıcılarda kimlik redakte edilen bir alandan
    türer — türetilseydi idempotency anahtarı kayar ve olay ikinci kez
    uygulanabilirdi.
    """
    row = await session.get(WebhookDeadLetter, dead_letter_id)
    if row is None:
        # RLS başka kiracının satırını zaten görünmez kılar; 404 doğru cevap.
        raise NotFoundError("Kayıt bulunamadı.")
    if row.payload is None:
        raise ConflictError("Olay gövdesi ayrıştırılamadığı için yeniden işlenemez.")
    if row.status is DeadLetterStatus.RESOLVED:
        raise ConflictError("Bu olay zaten işlenmiş.")

    provider = _provider(settings)
    try:
        event = billing_service.event_from_stored_payload(
            provider, payload=row.payload, event_id=row.event_id
        )
    except BillingError as exc:
        raise ConflictError(f"Olay yeniden kurulamadı: {exc}") from exc

    # ``TenantSessionDep`` transaction'ı ZATEN açmıştır (kiracı GUC'u
    # transaction-local'dır); burada ikinci bir ``session.begin()`` açmak
    # "A transaction is already begun" hatası verir. Commit bağımlılığa aittir.
    try:
        outcome = await billing_service.apply_webhook_event(
            session, redis, event, provider=row.provider
        )
        if outcome in {"applied", "duplicate"}:
            await dead_letter_service.mark_resolved(session, row, redis=redis)
        record_audit(
            session,
            tenant_id=principal.tenant_id,
            action=AuditAction.SUBSCRIPTION_CHANGED,
            resource_type="webhook_dead_letter",
            resource_id=row.id,
            actor_user_id=principal.user_id,
            meta={"source": "dead_letter_retry", "outcome": outcome},
        )
    except DeadLetterError as exc:
        # Hâlâ uygulanamıyor: satır kuyrukta kalır (ConflictError transaction'ı
        # geri sarar, yani "çözüldü" damgası da yazılmaz — doğru olan bu).
        raise ConflictError(f"Olay hâlâ işlenemiyor: {exc.reason}") from exc

    if outcome == "applied":
        await billing_service.mark_webhook_processed(
            redis, provider=row.provider, event_id=row.event_id
        )
        await notify_subscription_event(
            session, redis, settings, email_provider=email_provider, event=event
        )
    logger.info(
        "dlq_yeniden_islendi",
        provider=row.provider,
        event_type=row.event_type,
        outcome=outcome,
    )
    return DeadLetterRetryResponse(outcome=outcome, dead_letter=_dead_letter_response(row))


@router.post("/webhook", response_model=WebhookResponse)
async def billing_webhook(
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
    email_provider: EmailProviderDep,
) -> WebhookResponse:
    """Ödeme sağlayıcısı webhook'u (kimliksiz; HMAC imzayla doğrulanır, idempotent).

    **Hiçbir olay sessizce kaybolmaz.** Doğrulaması geçip uygulanamayan olay ölü
    mektup kuyruğuna yazılır ve yanıt, sağlayıcıya ne yapması gerektiğini söyler:

    * **kalıcı hata → 400.** Yeniden deneme düzeltmez (tanınmayan kiracı,
      eşlenmemiş durum); sağlayıcıyı denemeye çağırmak yalnız gürültü üretir.
    * **geçici hata → 503**, ta ki deneme tavanı dolana kadar; sonra 200. Çünkü
      sınırsız yeniden deneme fırtınası gerçek arızayı log'da görünmez kılar.
    * **imza geçersiz → 400**, ama gövde yine de (tavan dâhilinde) kuyruğa
      yazılır: imza BİÇİMİ hâlâ doğrulanmamış bir varsayımdır ve biçim yanlışsa
      gerçek olayların tamamı buraya düşer — teşhisin tek yolu budur.
    """
    raw_body = await request.body()
    provider = _provider(settings)
    try:
        event = provider.parse_webhook(headers=request.headers, raw_body=raw_body)
    except WebhookVerificationError as exc:
        await _dead_letter_unparsed(
            session, redis, provider=provider.name, raw_body=raw_body, reason=str(exc)
        )
        raise ValidationFailedError("Webhook doğrulanamadı.") from exc
    except BillingError as exc:
        raise AppError(str(exc), code=ErrorCode.INTERNAL_ERROR, status_code=503) from exc

    try:
        async with session.begin():
            outcome = await billing_service.apply_webhook_event(
                session, redis, event, provider=provider.name
            )
            # Daha önce kuyruğa düşmüş bir olay SONUNDA uygulandıysa satırı
            # çöz: kuyrukta kalan kayıt artık yanlış bilgidir.
            if outcome == "applied":
                await dead_letter_service.resolve_for_event(
                    session, provider=provider.name, event_id=event.event_id, redis=redis
                )
    except DeadLetterError as exc:
        return await _dead_letter_event(
            session, redis, provider=provider.name, event=event, raw_body=raw_body, failure=exc
        )
    except BillingError as exc:
        # Sınıflandırılmamış sağlayıcı hatası: kalıcı saymak, düzelebilecek bir
        # olayı çöpe atmak olurdu — geçici kabul edilip kuyruğa alınır.
        return await _dead_letter_event(
            session,
            redis,
            provider=provider.name,
            event=event,
            raw_body=raw_body,
            failure=TransientEventError(str(exc)),
        )

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
    # Bildirim COMMIT SONRASI ve webhook'tan BAĞIMSIZ: e-posta hatası isteği
    # düşürürse sağlayıcı yeniden dener ve durum ikinci kez uygulanır (madde 2).
    if outcome == "applied":
        await notify_subscription_event(
            session, redis, settings, email_provider=email_provider, event=event
        )
    return WebhookResponse(status=outcome)
