"""Ödeme sağlayıcı seam'i (Sprint 3.3-B).

Sağlayıcıdan bağımsız iki yüzey: **checkout başlatma** ve **webhook doğrulama/ayrıştırma**.
Abonelik durumu (``Subscription``) yalnız plan kademesini saklar; limitler her zaman
``tenderiq_core.billing.plans``'tan okunur (bkz. ``services.billing``).

Varsayılan ``ManualBillingProvider`` (dev/test) harici ağ geçidi kullanmaz: yükseltme
ANINDA etkinleşir. Ancak webhook yolu **gerçektir** — gövde HMAC-SHA256 ile imzalanır ve
``parse_webhook`` imzayı doğrular; böylece gerçek sağlayıcı (iyzico/PayTR/Stripe)
entegrasyonunun imza + idempotency mantığı anahtarsız uçtan uca test edilir. Gerçek
sağlayıcılar aynı ``BillingProvider`` protokolüne takılır (checkout'ta kiracı kimliği
sağlayıcı metadata'sına yazılır ve webhook'ta geri gelir — RLS'siz cross-tenant sorgu
gerekmez).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.billing.signature import get_scheme
from tenderiq_core.config import Settings
from tenderiq_core.models import SubscriptionStatus

#: Manual sağlayıcının imza biçimi — tanım ``billing/signature.py``dedir, burada
#: kopyalanmaz (gerçek sağlayıcı biçimi doğrulandığında tek yer düzeltilsin).
MANUAL_SCHEME = get_scheme("manual")

# Webhook imzasının taşındığı HTTP başlığı (manual sağlayıcı; gerçek sağlayıcılar
# kendi başlıklarını kullanır ve adaptörlerinde eşlenir).
SIGNATURE_HEADER = MANUAL_SCHEME.header


class BillingError(Exception):
    """Ödeme işlemi genel hatası."""


class BillingNotConfiguredError(BillingError):
    """Sağlayıcı seçildi ama anahtarları/uygulaması bağlanmadı."""


class WebhookVerificationError(BillingError):
    """Webhook imzası geçersiz veya sır yapılandırılmamış."""


@dataclass(frozen=True)
class CheckoutResult:
    """Checkout başlatma sonucu.

    ``activated=True`` (manual/test): plan çağıran tarafından anında uygulanır,
    ``checkout_url`` yoktur. Gerçek sağlayıcıda ``activated=False`` + ``checkout_url``
    döner (kullanıcı ağ geçidine yönlendirilir; etkinleşme webhook'la gelir).
    """

    provider: str
    activated: bool
    checkout_url: str | None = None
    provider_customer_id: str | None = None
    provider_subscription_id: str | None = None


@dataclass(frozen=True)
class WebhookEvent:
    """Doğrulanmış + ayrıştırılmış bir sağlayıcı webhook olayı.

    ``event_id`` sağlayıcı genelinde tekildir (idempotency anahtarı). ``tenant_id``
    checkout'ta sağlayıcı metadata'sına yazılıp geri gelir (imzalı gövdede güvenilir).
    """

    event_id: str
    event_type: str
    tenant_id: uuid.UUID | None
    plan_tier: PlanTier | None
    status: SubscriptionStatus
    #: Olayın SAĞLAYICIDA gerçekleştiği an. Webhook'lar sırasız gelebilir
    #: (yeniden deneme, kuyruk gecikmesi); bu damga olmadan geç gelen eski bir
    #: "iptal edildi" olayı, sonradan gelen "yeniden etkinleşti"yi EZER ve
    #: müşterinin ödediği erişimi kapatır.
    occurred_at: datetime | None = None
    provider_subscription_id: str | None = None
    provider_customer_id: str | None = None
    #: Ödenmiş dönemin bittiği (ve iptal edilmemişse sıradaki tahsilatın
    #: yapılacağı) an. Kullanıcıya "erişiminiz şu tarihe kadar sürüyor" ve
    #: "sıradaki tahsilat" olarak gösterilir; sağlayıcı göndermezse
    #: ``services.billing`` kota dönemi sonuna düşer.
    current_period_end: datetime | None = None


def compute_signature(secret: str, raw_body: bytes) -> str:
    """Ham gövde için HMAC-SHA256 onaltılık imza (manual sağlayıcı imzalar/doğrular)."""
    return MANUAL_SCHEME.compute(secret=secret, raw_body=raw_body)


def _verify_signature(secret: str | None, headers: Mapping[str, str], raw_body: bytes) -> None:
    """Webhook imzasını sabit-zamanlı karşılaştırır; başarısızsa hata fırlatır."""
    if not secret:
        raise WebhookVerificationError("Webhook sırrı (BILLING_WEBHOOK_SECRET) yapılandırılmamış.")
    if not MANUAL_SCHEME.matches(secret=secret, raw_body=raw_body, headers=headers):
        raise WebhookVerificationError("Webhook imzası geçersiz.")


@dataclass(frozen=True)
class ProviderSubscriptionState:
    """Sağlayıcıdaki abonelik durumunun anlık görüntüsü (mutabakat için)."""

    status: SubscriptionStatus
    plan_tier: PlanTier | None


class BillingProvider(Protocol):
    """Ödeme sağlayıcı sözleşmesi (checkout + webhook)."""

    name: str

    async def create_checkout(
        self, *, tenant_id: uuid.UUID, target_tier: PlanTier
    ) -> CheckoutResult:
        """Bir plan yükseltmesi için ödeme akışı başlatır."""
        ...

    def parse_webhook(self, *, headers: Mapping[str, str], raw_body: bytes) -> WebhookEvent:
        """Webhook imzasını doğrular ve olayı ayrıştırır (geçersizse hata)."""
        ...

    async def fetch_subscription(
        self, *, provider_subscription_id: str
    ) -> ProviderSubscriptionState | None:
        """Sağlayıcıdaki güncel durumu çeker (mutabakat). Bulunamazsa ``None``.

        Webhook'un HİÇ gelmediği hâlin tek yedeği budur: checkout erişimi
        açmadığı için, kayıp bir olay "ödeme alındı ama erişim açılmadı"
        durumunu sessizce kalıcı kılar.
        """
        ...

    # ── Yaşam döngüsü operasyonları (`/sartlar` §3) ──────────────────────────
    #
    # Bu üçü seam'in parçasıdır çünkü `/sartlar` bunları KULLANICIYA taahhüt
    # eder; sağlayıcı değişse de taahhüt değişmez. Sağlayıcıda karşılığı olmayan
    # bir operasyon sessizce yutulmaz — ilgili adaptör açıkça hata verir.

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        """Sağlayıcıdaki tekrarlayan tahsilatı durdurur.

        **Erişim kesme İŞİ DEĞİLDİR.** Erişim, ödenmiş dönemin sonuna kadar
        bizim aynamızda sürer (``Subscription.cancel_at_period_end``); sağlayıcı
        çağrısı yalnız bir daha para çekilmemesini garanti eder.
        """
        ...

    async def resume_subscription(self, *, provider_subscription_id: str) -> None:
        """İptal edilmiş bir aboneliği dönem sonundan ÖNCE geri alır.

        Dönem sonu geçtikten sonra geri alma yoktur; o hâlde yeni bir checkout
        gerekir (``create_checkout``).
        """
        ...

    async def change_plan(
        self, *, provider_subscription_id: str, target_tier: PlanTier, immediate: bool
    ) -> None:
        """Plan kademesini değiştirir.

        ``immediate=True`` yükseltme (anında), ``False`` düşürme (dönem sonunda)
        — `/sartlar` §3.
        """
        ...


class ManualBillingProvider:
    """Test-modu sağlayıcı: harici ağ geçidi yok (bkz. modül docstring'i)."""

    name = "manual"

    def __init__(self, webhook_secret: str | None) -> None:
        self._secret = webhook_secret

    async def create_checkout(
        self, *, tenant_id: uuid.UUID, target_tier: PlanTier
    ) -> CheckoutResult:
        # Test modu: yükseltme anında etkinleşir; sağlayıcı abonelik kimliği kiracıya
        # deterministik olarak türetilir (gerçek sağlayıcıda ağ geçidinden gelir).
        return CheckoutResult(
            provider=self.name,
            activated=True,
            checkout_url=None,
            provider_customer_id=None,
            provider_subscription_id=f"manual_{tenant_id}",
        )

    async def fetch_subscription(
        self, *, provider_subscription_id: str
    ) -> ProviderSubscriptionState | None:
        """Test-modu sağlayıcıda uzak durum yoktur; mutabakat uygulanmaz."""
        return None

    # Test modunda tahsilat yoktur; yaşam döngüsünün TAMAMI bizim aynamızda
    # tutulur. Bu üç operasyon bilerek boştur — hata vermeleri, ödeme ağ geçidi
    # bağlı değilken iptal yolunu kapatırdı ve `/sartlar`ın cayma taahhüdü
    # test-modunda sınanamaz hâle gelirdi.

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        return None

    async def resume_subscription(self, *, provider_subscription_id: str) -> None:
        return None

    async def change_plan(
        self, *, provider_subscription_id: str, target_tier: PlanTier, immediate: bool
    ) -> None:
        return None

    def parse_webhook(self, *, headers: Mapping[str, str], raw_body: bytes) -> WebhookEvent:
        _verify_signature(self._secret, headers, raw_body)
        try:
            data = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise WebhookVerificationError("Webhook gövdesi ayrıştırılamadı.") from exc
        return _event_from_manual_payload(data)


def _parse_timestamp(raw: object, *, field: str) -> datetime | None:
    """ISO-8601 bir damgayı **UTC-farkındalıklı** ``datetime``e çevirir.

    Farksız (naive) gelen damga UTC sayılır: karşılaştırmada bir tarafın naive
    olması ``TypeError`` üretir ve bu, sırasız-olay korumasını çalıştığını
    sanarken çökerten türden bir hatadır.
    """
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError as exc:
        raise WebhookVerificationError(f"{field} ISO-8601 olmalı.") from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _event_from_manual_payload(data: object) -> WebhookEvent:
    """Manual sağlayıcının imzalı JSON gövdesini ``WebhookEvent``'e çevirir."""
    if not isinstance(data, dict):
        raise WebhookVerificationError("Webhook gövdesi bir nesne olmalı.")
    try:
        event_id = str(data["event_id"])
        event_type = str(data["event_type"])
    except KeyError as exc:
        raise WebhookVerificationError(f"Webhook gövdesinde eksik alan: {exc}.") from exc

    raw_tenant = data.get("tenant_id")
    raw_plan = data.get("plan")
    raw_status = data.get("status", SubscriptionStatus.ACTIVE.value)
    try:
        tenant_id = uuid.UUID(str(raw_tenant)) if raw_tenant else None
        plan_tier = PlanTier(str(raw_plan)) if raw_plan else None
        status = SubscriptionStatus(str(raw_status))
    except ValueError as exc:
        raise WebhookVerificationError(f"Webhook gövdesinde geçersiz değer: {exc}.") from exc

    occurred_at = _parse_timestamp(data.get("occurred_at"), field="occurred_at")
    current_period_end = _parse_timestamp(
        data.get("current_period_end"), field="current_period_end"
    )

    return WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        occurred_at=occurred_at,
        current_period_end=current_period_end,
        tenant_id=tenant_id,
        plan_tier=plan_tier,
        status=status,
        provider_subscription_id=(
            str(data["provider_subscription_id"]) if data.get("provider_subscription_id") else None
        ),
        provider_customer_id=(
            str(data["provider_customer_id"]) if data.get("provider_customer_id") else None
        ),
    )


def create_billing_provider(
    provider: str, *, webhook_secret: str | None, settings: Settings | None = None
) -> BillingProvider:
    """Yapılandırmaya göre ödeme sağlayıcısı üretir (fabrika).

    ``manual`` (varsayılan) test-modu sağlayıcısını döndürür. Gerçek sağlayıcılar
    (iyzico/paytr/stripe) aynı seam'e takılır; sandbox/canlı anahtarları ve
    adaptörleri bağlandığında bu fabrikaya eklenir. Şimdilik seçilirse yapılandırma
    hatası verir (yanlışlıkla ödemesiz çalışmayı önler).
    """
    if provider == "manual":
        return ManualBillingProvider(webhook_secret=webhook_secret)
    if provider == "fake":
        # Testler için: sözleşmeyi uygular, ağa çıkmaz (bkz. billing.fake).
        from tenderiq_core.billing.fake import FakeBillingProvider

        return FakeBillingProvider(webhook_secret=webhook_secret)
    if provider == "iyzico":
        from tenderiq_core.billing.iyzico import IyzicoBillingProvider

        if settings is None or not settings.iyzico_api_key or not settings.iyzico_secret_key:
            raise BillingNotConfiguredError(
                "BILLING_PROVIDER=iyzico için IYZICO_API_KEY ve IYZICO_SECRET_KEY zorunludur."
            )
        return IyzicoBillingProvider(
            api_key=settings.iyzico_api_key,
            secret_key=settings.iyzico_secret_key,
            webhook_secret=webhook_secret,
            plan_reference_codes={
                PlanTier(tier): code
                for tier, code in settings.iyzico_plan_codes.items()
                if tier in PlanTier.__members__.values() or tier in {t.value for t in PlanTier}
            },
            callback_url=settings.iyzico_callback_url,
            sandbox=not settings.billing_is_live,
        )
    raise BillingNotConfiguredError(
        f"Ödeme sağlayıcısı '{provider}' henüz bağlanmadı. Aynı BillingProvider "
        "seam'ine adaptör ve sandbox anahtarları eklenmelidir (bkz. billing/provider.py)."
    )
