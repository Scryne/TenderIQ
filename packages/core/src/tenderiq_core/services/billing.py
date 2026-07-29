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

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.billing.plans import DEFAULT_PLAN_TIER, PlanTier, is_upgrade
from tenderiq_core.billing.provider import BillingError as BillingProviderError
from tenderiq_core.billing.provider import BillingProvider, CheckoutResult, WebhookEvent
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Subscription, SubscriptionStatus
from tenderiq_core.services import quota
from tenderiq_core.services.dead_letter import PermanentEventError

logger = get_logger("tenderiq.core.billing")

# İşlenmiş webhook olaylarının Redis'te tutulma süresi (idempotency penceresi).
WEBHOOK_DEDUP_TTL_SECONDS = 90 * 24 * 3600


def _dedup_key(provider: str, event_id: str) -> str:
    return f"billing:event:{provider}:{event_id}"


async def _tenant_exists(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Kiracı (organizasyon) satırı var mı — webhook yolunda zorunlu kontrol.

    ``Organization`` RLS'siz bir kimlik tablosudur; bu sorgu kiracı bağlamı
    kurulmadan da çalışır ve zaten kurulmadan ÖNCE çalışmalıdır: var olmayan bir
    kiracının bağlamını kurmanın anlamı yok.
    """
    from tenderiq_core.models import Organization

    return (
        await session.scalar(select(Organization.id).where(Organization.id == tenant_id))
    ) is not None


async def apply_plan_change(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    plan: PlanTier,
    status: SubscriptionStatus,
    provider: str | None = None,
    provider_customer_id: str | None = None,
    provider_subscription_id: str | None = None,
    now: datetime | None = None,
) -> tuple[Subscription, PlanTier]:
    """Kiracının aboneliğini hedef plana/duruma getirir (idempotent).

    Önceki plan kademesini de döndürür (denetim/log için). Kiracı bağlamı ayarlı bir
    oturumda çağrılmalıdır (RLS). Flush/commit çağıranın sorumluluğundadır.

    Dönem sonu da BURADA tutulur, çünkü plana yazan her yol (checkout, webhook,
    mutabakat) buradan geçer: ücretli bir plana geçen aboneliğin bir yenileme
    tarihi OLMAK zorundadır — kullanıcıya "sıradaki tahsilat" olarak gösterilen
    şey odur ve tarihsiz bir abonelik iptal edildiğinde erişimin ne zaman
    biteceği de söylenemez. Sağlayıcı kendi tarihini bildirirse (webhook) üstüne
    yazar; bildirmezse kota takvimi kullanılır.
    """
    now = now or datetime.now(UTC)
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

    if plan == DEFAULT_PLAN_TIER:
        # Ücretsiz planda yenilenecek bir dönem, bitecek bir abonelik ve
        # bekleyen bir düşürme yoktur; kalan işaretler yalnız yanlış bilgi üretir.
        subscription.current_period_end = None
        subscription.cancel_at_period_end = False
        subscription.pending_plan = None
    elif subscription.current_period_end is None or subscription.current_period_end <= now:
        subscription.current_period_end = quota.current_period_bounds(now)[1]
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


# ── Yaşam döngüsü: iptal, geri alma, plan değişimi (`/sartlar` §3) ───────────
#
# `/sartlar` üç kural taahhüt eder ve üçü de burada, TEK yerde uygulanır:
#
#   1. Yükseltme ANINDA etkilidir.
#   2. Düşürme DÖNEM SONUNDA uygulanır (ödenmiş dönemin ortasında kotayı kısmak,
#      satın alınan hizmeti geri almaktır).
#   3. İptal DÖNEM SONUNDA erişimi keser (14 gün koşulsuz cayma hakkı ayrıca
#      işler; bkz. `/sartlar` §3 ve LEGAL_TODO.md §E).
#
# Kuralların uçlarda değil serviste durmasının sebebi: aynı üç kural HTTP
# ucundan da (kullanıcı iptali), webhook'tan da (sağlayıcı olayı), zamanlanmış
# görevden de (dönem sonu) tetiklenir. Üç kopya, üç farklı hata demektir.


class SubscriptionStateError(Exception):
    """İstenen işlem aboneliğin MEVCUT durumunda anlamlı değil.

    Örn. iptal edilmemiş bir aboneliği "geri almak" ya da hâlihazırda kullanılan
    plana "geçmek". Sunucu hatası değildir; çağıran kullanıcıya-okur bir çakışma
    yanıtına çevirir.
    """


def _period_end(subscription: Subscription, now: datetime) -> datetime:
    """Ödenmiş dönemin bittiği an; sağlayıcı söylemediyse kota takviminden.

    Sağlayıcı dönem sonunu her zaman göndermez (manual/test sağlayıcıda hiç yok,
    iyzico'da alan adı henüz doğrulanmadı). Bu durumda kota dönemiyle (takvim ayı,
    ``quota.current_period_bounds``) aynı sınır kullanılır — kullanıcıya gösterilen
    "erişiminiz şu tarihe kadar" ile kotanın gerçekten sıfırlandığı an aynı olur;
    iki ayrı tarih göstermek kullanıcıyı yanıltırdı.

    Geçmişte kalmış bir damga kullanılmaz: aksi hâlde iptal, dönem sonu ÇOKTAN
    geçtiği için anında erişim kesmeye dönüşürdü.
    """
    stored = subscription.current_period_end
    if stored is not None and stored > now:
        return stored
    return quota.current_period_bounds(now)[1]


async def schedule_cancellation(
    session: AsyncSession,
    provider: BillingProvider,
    *,
    tenant_id: uuid.UUID,
    now: datetime | None = None,
) -> Subscription:
    """Aboneliği dönem sonunda biter şekilde işaretler (kullanıcı iptali).

    Erişim ``current_period_end``e kadar SÜRER: durum ``ACTIVE`` kalır, plan
    değişmez, yalnız ``cancel_at_period_end`` işaretlenir. Sağlayıcıdaki
    tekrarlayan tahsilat ise ANINDA durdurulur — iptal eden müşteriden bir kez
    daha para çekmek, erken durdurmanın maliyetiyle kıyaslanamaz.

    Ücretsiz planda iptal edilecek bir şey yoktur; çağıran bunu çakışma olarak
    bildirir. Bekleyen bir düşürme varsa iptal onu geçersiz kılar (abonelik
    tümden bitiyorsa hangi plana düşüleceği anlamsızdır).
    """
    now = now or datetime.now(UTC)
    subscription = await quota.get_or_create_subscription(session, tenant_id)

    if subscription.plan == DEFAULT_PLAN_TIER and not subscription.cancel_at_period_end:
        raise SubscriptionStateError("Ücretsiz planda iptal edilecek bir abonelik yok.")
    if subscription.cancel_at_period_end:
        raise SubscriptionStateError("Abonelik zaten dönem sonunda bitecek şekilde iptal edildi.")

    if subscription.provider_subscription_id:
        # Sağlayıcı hatası iptali ENGELLEMEZ diye düşünmek cazip ama yanlış
        # olurdu: yerelde iptal edilmiş, sağlayıcıda tahsilatı sürer bir abonelik
        # müşteriden erişimsiz para çeker. Hata yukarı verilir; kullanıcı tekrar
        # dener ve bu arada hiçbir şey değişmemiştir (işlem henüz commit edilmedi).
        await provider.cancel_subscription(
            provider_subscription_id=subscription.provider_subscription_id
        )

    subscription.cancel_at_period_end = True
    subscription.current_period_end = _period_end(subscription, now)
    subscription.pending_plan = None
    logger.info(
        "abonelik_iptal_planlandi",
        tenant_id=str(tenant_id),
        plan=subscription.plan.value,
        period_end=subscription.current_period_end.isoformat(),
    )
    return subscription


async def resume_subscription(
    session: AsyncSession,
    provider: BillingProvider,
    *,
    tenant_id: uuid.UUID,
    now: datetime | None = None,
) -> Subscription:
    """İptali geri alır — YALNIZCA dönem sonu henüz geçmemişken.

    Dönem sonu geçtikten sonra abonelik gerçekten bitmiştir ve geri alma bir
    "devam" değil yeni bir satın almadır; o hâlde çağıran checkout'a yönlendirir.
    """
    now = now or datetime.now(UTC)
    subscription = await quota.get_or_create_subscription(session, tenant_id)

    if not subscription.cancel_at_period_end:
        raise SubscriptionStateError("İptal edilmiş bir abonelik yok; geri alınacak bir şey de.")
    if subscription.current_period_end is not None and subscription.current_period_end <= now:
        raise SubscriptionStateError(
            "Dönem sona erdi; devam etmek için yeni bir abonelik başlatmanız gerekiyor."
        )

    if subscription.provider_subscription_id:
        await provider.resume_subscription(
            provider_subscription_id=subscription.provider_subscription_id
        )

    subscription.cancel_at_period_end = False
    logger.info("abonelik_iptali_geri_alindi", tenant_id=str(tenant_id))
    return subscription


@dataclass(frozen=True)
class PlanChangeResult:
    """Bir plan değişimi talebinin sonucu.

    ``effective_at`` ``None`` ise değişim ANINDA uygulandı (yükseltme); doluysa
    o tarihte uygulanacak (düşürme). ``checkout`` doluysa ödeme henüz alınmamıştır
    ve kullanıcı ağ geçidine yönlendirilir — plan bu yolda ASLA anında açılmaz.
    """

    plan: PlanTier
    effective_at: datetime | None = None
    checkout: CheckoutResult | None = None
    subscription: Subscription | None = None
    previous_plan: PlanTier | None = None


async def request_plan_change(
    session: AsyncSession,
    provider: BillingProvider,
    *,
    tenant_id: uuid.UUID,
    target_tier: PlanTier,
    now: datetime | None = None,
) -> PlanChangeResult:
    """Plan değişimi talebini `/sartlar` §3'e göre yönlendirir.

    Üç yol vardır ve ayrım, kiracının sağlayıcıda bir aboneliği olup olmamasıdır:

    * **Abonelik yok** (ücretsiz kiracı) → yeni satın alma: ``start_checkout``.
    * **Abonelik var, hedef yukarıda** → sağlayıcıda anında yükseltilir ve ayna
      hemen güncellenir; müşteri parasını ödemeden önce yeni kotayı kullanır
      (ADR-0014: ters yönüne tercih edilir).
    * **Abonelik var, hedef aşağıda** → ``pending_plan`` olarak dönem sonuna
      yazılır; kota bu dönem boyunca DEĞİŞMEZ.

    Ücretsiz plana düşmek bir plan değişimi değil iptaldir (tahsilat tümden
    durur) — o yüzden ``schedule_cancellation``a yönlendirilir; iki ayrı yolun
    aynı sonucu farklı üretmesi, ikisinin zamanla ayrışması demektir.
    """
    now = now or datetime.now(UTC)
    subscription = await quota.get_or_create_subscription(session, tenant_id)

    # Bekleyen iptalin üstüne plan değişimi yazılmaz. İki niyet çakışıyor
    # ("bitsin" ve "şu plana geçsin") ve birini diğerinden sessizce çıkarmak —
    # ör. plan seçimini örtük "iptali geri al" saymak — kullanıcının beklemediği
    # bir tahsilat üretebilir. Geri alma tek tık uzakta ve açıkça sunuluyor.
    if subscription.cancel_at_period_end:
        raise SubscriptionStateError(
            "Abonelik dönem sonunda bitecek. Plan değiştirmek için önce iptali geri alın."
        )
    if subscription.pending_plan is not None and target_tier == subscription.plan:
        # Planlanmış düşürmeyi geri alma. İptalin geri alınabilmesi gibi bunun da
        # geri alınabilmesi gerekir: kullanıcı dönem sonunda kotasının düşeceğini
        # görüp fikrini değiştirebilir ve o ana kadar hiçbir şey uygulanmamıştır.
        # "Mevcut planını seç" bu niyetin doğal ifadesidir; aksi hâlde kullanıcı
        # düşürmeyi geri almak için önce yükseltip sonra geri dönmek zorunda kalır.
        if subscription.provider_subscription_id:
            await provider.change_plan(
                provider_subscription_id=subscription.provider_subscription_id,
                target_tier=target_tier,
                immediate=False,
            )
        reverted = subscription.pending_plan
        subscription.pending_plan = None
        logger.info(
            "abonelik_dusurmesi_geri_alindi",
            tenant_id=str(tenant_id),
            reverted_plan=reverted.value,
        )
        return PlanChangeResult(
            plan=subscription.plan, subscription=subscription, previous_plan=subscription.plan
        )
    if target_tier == subscription.plan:
        raise SubscriptionStateError("Zaten bu plandasınız.")

    if target_tier == DEFAULT_PLAN_TIER:
        canceled = await schedule_cancellation(session, provider, tenant_id=tenant_id, now=now)
        return PlanChangeResult(
            plan=canceled.plan,
            effective_at=canceled.current_period_end,
            subscription=canceled,
            previous_plan=canceled.plan,
        )

    if not subscription.provider_subscription_id:
        result, updated, old_plan = await start_checkout(
            session, provider, tenant_id=tenant_id, target_tier=target_tier
        )
        return PlanChangeResult(
            plan=target_tier,
            checkout=None if result.activated else result,
            subscription=updated,
            previous_plan=old_plan,
        )

    upgrading = is_upgrade(subscription.plan, target_tier)
    await provider.change_plan(
        provider_subscription_id=subscription.provider_subscription_id,
        target_tier=target_tier,
        immediate=upgrading,
    )

    if upgrading:
        _, old_plan = await apply_plan_change(
            session,
            tenant_id=tenant_id,
            plan=target_tier,
            status=SubscriptionStatus.ACTIVE,
            provider=getattr(provider, "name", None),
        )
        # Yükseltme bekleyen bir düşürmeyi de iptal eder: kullanıcı fikrini
        # değiştirmiştir, eski talebi dönem sonunda sessizce uygulamak sürpriz olur.
        subscription.pending_plan = None
        logger.info(
            "abonelik_plani_yukseltildi",
            tenant_id=str(tenant_id),
            old_plan=old_plan.value,
            new_plan=target_tier.value,
        )
        return PlanChangeResult(plan=target_tier, subscription=subscription, previous_plan=old_plan)

    subscription.pending_plan = target_tier
    subscription.current_period_end = _period_end(subscription, now)
    logger.info(
        "abonelik_dusurmesi_planlandi",
        tenant_id=str(tenant_id),
        current_plan=subscription.plan.value,
        pending_plan=target_tier.value,
        effective_at=subscription.current_period_end.isoformat(),
    )
    return PlanChangeResult(
        plan=subscription.plan,
        effective_at=subscription.current_period_end,
        subscription=subscription,
        previous_plan=subscription.plan,
    )


@dataclass(frozen=True)
class DueChangesReport:
    """Dönem sonu gelmiş değişikliklerin uygulanma sonucu."""

    #: Dönem sonu geçmiş ve gerçekten bitirilen abonelik sayısı.
    ended: int = 0
    #: Dönem sonunda uygulanan düşürme sayısı.
    downgraded: int = 0

    @property
    def applied(self) -> int:
        return self.ended + self.downgraded


async def apply_due_subscription_changes(
    session: AsyncSession, *, tenant_ids: Sequence[uuid.UUID], now: datetime | None = None
) -> DueChangesReport:
    """Dönem sonu GELMİŞ iptalleri ve düşürmeleri uygular.

    Bu iş, `/sartlar` §3'ün "dönem sonunda" kısmının gerçekten olmasını sağlar.
    Sağlayıcı normalde dönem bitişini bir olayla bildirir ve yetkilendirmeyi
    webhook değiştirir (ADR-0014); bu görev onun **yedeğidir** — tıpkı
    ``reconcile_subscriptions`` gibi. Olay hiç gelmezse iptal etmiş bir müşteri
    ücretsiz plana hiç düşmez ve ödemediği kotayı kullanmaya devam eder.

    Yön güvenlidir: yalnızca KULLANICININ KENDİ talep ettiği (``cancel_at_period_end``
    / ``pending_plan``) değişiklikler ve yalnızca vakti geldiğinde uygulanır.
    Sağlayıcıdan gelen bir bilgiye dayanmaz, dolayısıyla sağlayıcı kesintisinde
    yanlış kapatma üretemez.
    """
    now = now or datetime.now(UTC)
    ended = downgraded = 0

    for tenant_id in tenant_ids:
        await set_tenant_context(session, tenant_id)
        subscription = await quota.get_or_create_subscription(session, tenant_id)
        period_end = subscription.current_period_end
        if period_end is None or period_end > now:
            continue
        if not (subscription.cancel_at_period_end or subscription.pending_plan):
            continue

        if subscription.cancel_at_period_end:
            subscription.plan = DEFAULT_PLAN_TIER
            subscription.status = SubscriptionStatus.CANCELED
            subscription.cancel_at_period_end = False
            subscription.pending_plan = None
            subscription.current_period_end = None
            ended += 1
            logger.info("abonelik_donem_sonunda_bitti", tenant_id=str(tenant_id))
        else:
            target = subscription.pending_plan
            assert target is not None  # noqa: S101 - yukarıdaki koşul garanti eder
            previous = subscription.plan
            subscription.plan = target
            subscription.pending_plan = None
            # Yeni dönem başladı: sınırı ileri taşı, yoksa aynı düşürme her
            # koşuda "vakti gelmiş" görünürdü.
            subscription.current_period_end = quota.current_period_bounds(now)[1]
            downgraded += 1
            logger.info(
                "abonelik_dusurmesi_uygulandi",
                tenant_id=str(tenant_id),
                old_plan=previous.value,
                new_plan=target.value,
            )

    report = DueChangesReport(ended=ended, downgraded=downgraded)
    logger.info("donem_sonu_degisiklikleri", ended=report.ended, downgraded=report.downgraded)
    return report


@dataclass(frozen=True)
class _WebhookTarget:
    """Bir olayın aynaya yazacağı hedef durum."""

    plan: PlanTier
    status: SubscriptionStatus
    #: ``None`` ⇒ bayrağa DOKUNMA (olay bu konuda bir şey söylemiyor).
    cancel_at_period_end: bool | None = None


def _resolve_target(event: WebhookEvent, current_plan: PlanTier) -> _WebhookTarget:
    """Olay türüne göre hedef plan + durum + iptal bayrağı belirler."""
    if event.event_type == "subscription.canceled":
        # İPTAL ERİŞİMİ ANINDA KESMEZ. Sağlayıcı "iptal edildi" dediğinde
        # müşteri içinde bulunduğu dönemin ücretini ödemiştir; planı hemen
        # FREE'ye çekmek, satın alınmış hizmeti geri almak olur ve `/sartlar`
        # §3'ün "iptal, içinde bulunulan dönemin sonunda geçerli olur"
        # taahhüdünü çiğner. Dönem gerçekten bittiğinde ya `subscription.expired`
        # gelir ya da ``apply_due_subscription_changes`` bitirir.
        return _WebhookTarget(current_plan, SubscriptionStatus.ACTIVE, cancel_at_period_end=True)
    if event.event_type in {"subscription.expired", "subscription.ended"}:
        # Dönem BİTTİ: erişim burada kesilir.
        return _WebhookTarget(
            DEFAULT_PLAN_TIER, SubscriptionStatus.CANCELED, cancel_at_period_end=False
        )
    if event.event_type == "subscription.past_due":
        # Plan korunur; yalnız durum düşer (kota dondurma kararı ayrıca alınır).
        return _WebhookTarget(current_plan, SubscriptionStatus.PAST_DUE)
    if event.event_type == "subscription.resumed":
        return _WebhookTarget(
            event.plan_tier or current_plan, event.status, cancel_at_period_end=False
        )
    # activated / updated / renewed: olaydaki plan uygulanır (yoksa mevcut korunur).
    # Bekleyen iptal bayrağına DOKUNULMAZ: sağlayıcının "hâlâ aktif" demesi,
    # kullanıcının iptal talebini geri aldığı anlamına gelmez — henüz işlememiş
    # olabilir. Bayrağı burada temizlemek, iptal etmiş müşteriyi sessizce
    # aboneliğe geri döndürürdü.
    return _WebhookTarget(event.plan_tier or current_plan, event.status)


def event_from_stored_payload(
    provider: BillingProvider, *, payload: dict[str, Any], event_id: str
) -> WebhookEvent:
    """Kuyrukta saklanan (redakte) gövdeden olayı yeniden kurar.

    İmza **doğrulanmaz** ve doğrulanamaz: gövde saklanırken redakte edildiği
    için baytları artık orijinaliyle aynı değil. Bu bir boşluk değil, yolun
    tanımı — bu fonksiyona yalnız kimliği doğrulanmış bir kiracı yöneticisinin
    açık talebiyle gelinir; güven sınırı imza değil, oturumdur.

    ``event_id`` gövdeden TÜRETİLMEZ, saklanan sütundan gelir: bazı
    sağlayıcılarda kimlik redakte edilen bir alandan (``token``) türer ve
    türetilseydi idempotency anahtarı kayardı — yani daha önce uygulanmış bir
    olay "yeni" görünüp ikinci kez uygulanırdı.
    """
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    parsed = provider.parse_webhook_payload(raw_body=raw)
    return replace(parsed, event_id=event_id)


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
        # Kalıcı: imzalı gövde kiracıyı taşımak ZORUNDA. Yeniden denemek aynı
        # gövdeyi aynı eksikle geri getirir.
        raise PermanentEventError("Webhook olayında kiracı kimliği (tenant_id) yok.")

    # Yalnız OKUMA: damga başarılı uygulamadan sonra yazılır (bkz. docstring).
    try:
        if await redis.get(_dedup_key(provider, event.event_id)) is not None:
            return "duplicate"
    except RedisError as exc:
        # Tekilleştirme yumuşak: uygulama idempotent olduğundan çift-işlem zararsız.
        logger.warning("webhook_dedup_atlandi", error=str(exc))

    # Kiracı GERÇEKTEN var mı. Gövde imzalıdır ama imza "bu kiracı bizde var"
    # demez: sağlayıcıdaki eski bir abonelik, silinmiş bir organizasyonu
    # gösterebilir ya da metadata yanlış doldurulmuş olabilir. Kontrol edilmezse
    # abonelik INSERT'i yabancı anahtar kısıtına takılır ve uç HTTP 500 döner —
    # sağlayıcı bunu GEÇİCİ hata sayıp asla başarılı olamayacak bir olayı saatlerce
    # yeniden dener. Kalıcı bir reddetme doğru cevaptır.
    if not await _tenant_exists(session, event.tenant_id):
        # Kiracı kimliği loglanır: bu, gerçek bir müşterinin ödemesinin
        # karşılıksız kalması anlamına GELEBİLİR ve sessiz kalmamalıdır.
        # Olay kuyruğa düşer (çağıran yazar) — kaybolmaz.
        logger.error(
            "webhook_bilinmeyen_kiraci",
            provider=provider,
            event_type=event.event_type,
            tenant_id=str(event.tenant_id),
        )
        raise PermanentEventError("Webhook olayındaki kiracı bulunamadı.")

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

    target = _resolve_target(event, subscription.plan)
    await apply_plan_change(
        session,
        tenant_id=event.tenant_id,
        plan=target.plan,
        status=target.status,
        provider=provider,
        provider_customer_id=event.provider_customer_id,
        provider_subscription_id=event.provider_subscription_id,
    )
    if target.cancel_at_period_end is not None:
        subscription.cancel_at_period_end = target.cancel_at_period_end
    if event.current_period_end is not None:
        # Sağlayıcının kendi tarihi her zaman kazanır: yenilemeyi o yapıyor.
        subscription.current_period_end = event.current_period_end
    if target.plan == DEFAULT_PLAN_TIER and target.status is SubscriptionStatus.CANCELED:
        # Abonelik GERÇEKTEN bitti (dönem sonu olayı): bekleyen bir düşürme ya da
        # bitiş tarihi taşımak, biten bir abonelik hakkında yanlış bilgi olurdu.
        # (``apply_plan_change`` de aynı temizliği yapar; burada niyet açık dursun.)
        subscription.current_period_end = None
        subscription.pending_plan = None
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


# ── Mutabakat (kritik yol) ───────────────────────────────────────────────────
#
# Checkout erişimi AÇMAZ (`activated=False`): yetkilendirmeyi açan tek mekanizma
# webhook. Webhook hiç gelmezse — sağlayıcı kesintisi, yanlış yapılandırılmış
# bildirim adresi, bizim tarafta bir dağıtım penceresi — "ödeme alındı ama
# erişim açılmadı" hâli SESSİZCE kalıcı olur. Müşteri parasını ödemiştir ve
# ürünü kullanamaz; bunu ancak destek talebiyle öğreniriz.
#
# Mutabakat bunun tek yedeğidir: sağlayıcıdaki durumu çeker, bizimkiyle
# karşılaştırır ve **tek yönlü** düzeltir.


@dataclass(frozen=True)
class ReconcileReport:
    """Bir mutabakat koşusunun sonucu."""

    checked: int = 0
    #: Erişim AÇMA yönünde sapma — otomatik onarıldı.
    repaired: int = 0
    #: Erişim KAPATMA yönünde sapma — otomatik yapılmadı, incelenmeli.
    needs_review: int = 0
    #: Sağlayıcıda bulunamayan veya durumu çözülemeyen abonelikler.
    unresolved: int = 0

    @property
    def drift(self) -> int:
        """Toplam sapma; sıfırdan farklıysa görünür olmalı."""
        return self.repaired + self.needs_review + self.unresolved


#: Erişim "açık" sayılan durumlar. Sağlayıcı bunlardan birini söylüyorsa ve biz
#: söylemiyorsak, müşteri ödediği hizmete erişemiyor demektir.
_ENTITLED_STATUSES = frozenset({SubscriptionStatus.ACTIVE})


async def reconcile_subscriptions(
    session: AsyncSession, provider: BillingProvider, *, tenant_ids: Sequence[uuid.UUID]
) -> ReconcileReport:
    """Sağlayıcıdaki durumla bizdeki yetkilendirmeyi karşılaştırır ve düzeltir.

    **Düzeltme tek yönlü güvenlidir.** Erişim AÇMA yönündeki sapma otomatik
    onarılır: müşteri ödemiş ama erişemiyor — bekletmenin bir savunması yok.
    Erişim KAPATMA yönündeki sapma otomatik uygulanmaz, yalnız raporlanır:
    yanlış kapatma müşteriye DOĞRUDAN zarar verir ve sebebi (henüz işlenmemiş
    bir yenileme olayı, sağlayıcıdaki geçici tutarsızlık) çoğu zaman bizde
    değildir. İnsan bakışı ucuz, yanlış kapatma pahalıdır.
    """
    checked = repaired = needs_review = unresolved = 0

    for tenant_id in tenant_ids:
        await set_tenant_context(session, tenant_id)
        subscription = await quota.get_or_create_subscription(session, tenant_id)
        if not subscription.provider_subscription_id:
            continue  # sağlayıcıda karşılığı yok (ücretsiz plan)
        if subscription.cancel_at_period_end:
            # Kullanıcı iptal etti; erişimi dönem sonuna kadar BİZ sürdürüyoruz ve
            # tahsilat sağlayıcıda çoktan durduruldu. İki taraf bu pencerede
            # BİLEREK ayrışır ve bu ayrışma bir sapma DEĞİLDİR:
            #   · sağlayıcı "canceled" + biz "active" ⇒ onarılırsa kullanıcının
            #     iptali sessizce geri alınır ve bir sonraki dönem tahsil edilir —
            #     mutabakat, müşterinin kararını ezer;
            #   · ters yön "incelenmeli" olarak raporlanırsa her koşuda gürültü
            #     üretir ve gerçek sapmaları görünmez kılar.
            # Vakti gelince ``apply_due_subscription_changes`` bitirir.
            continue
        checked += 1

        try:
            remote = await provider.fetch_subscription(
                provider_subscription_id=subscription.provider_subscription_id
            )
        except BillingProviderError as exc:
            unresolved += 1
            logger.warning("mutabakat_durum_alinamadi", tenant_id=str(tenant_id), error=str(exc))
            continue

        if remote is None:
            unresolved += 1
            logger.warning("mutabakat_abonelik_bulunamadi", tenant_id=str(tenant_id))
            continue

        remote_entitled = remote.status in _ENTITLED_STATUSES
        local_entitled = subscription.status in _ENTITLED_STATUSES
        plan_matches = remote.plan_tier is None or remote.plan_tier == subscription.plan

        if remote_entitled and (not local_entitled or not plan_matches):
            # Erişim AÇMA yönü — otomatik onar.
            await apply_plan_change(
                session,
                tenant_id=tenant_id,
                plan=remote.plan_tier or subscription.plan,
                status=remote.status,
                provider=getattr(provider, "name", "unknown"),
                provider_subscription_id=subscription.provider_subscription_id,
            )
            repaired += 1
            logger.warning(
                "mutabakat_erisim_onarildi",
                tenant_id=str(tenant_id),
                plan=(remote.plan_tier or subscription.plan).value,
            )
        elif local_entitled and not remote_entitled:
            # Erişim KAPATMA yönü — YALNIZ raporla.
            needs_review += 1
            logger.warning(
                "mutabakat_kapatma_sapmasi_incelenmeli",
                tenant_id=str(tenant_id),
                local_status=subscription.status.value,
                remote_status=remote.status.value,
            )

    report = ReconcileReport(
        checked=checked, repaired=repaired, needs_review=needs_review, unresolved=unresolved
    )
    logger.info(
        "mutabakat_tamamlandi",
        checked=report.checked,
        repaired=report.repaired,
        needs_review=report.needs_review,
        unresolved=report.unresolved,
        drift=report.drift,
    )
    return report
