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

import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.models import SubscriptionStatus

# Webhook imzasının taşındığı HTTP başlığı (manual sağlayıcı; gerçek sağlayıcılar
# kendi başlıklarını kullanır ve adaptörlerinde eşlenir).
SIGNATURE_HEADER = "x-tenderiq-signature"


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
    provider_subscription_id: str | None = None
    provider_customer_id: str | None = None


def compute_signature(secret: str, raw_body: bytes) -> str:
    """Ham gövde için HMAC-SHA256 onaltılık imza (manual sağlayıcı imzalar/doğrular)."""
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def _verify_signature(secret: str | None, headers: Mapping[str, str], raw_body: bytes) -> None:
    """Webhook imzasını sabit-zamanlı karşılaştırır; başarısızsa hata fırlatır."""
    if not secret:
        raise WebhookVerificationError("Webhook sırrı (BILLING_WEBHOOK_SECRET) yapılandırılmamış.")
    provided = headers.get(SIGNATURE_HEADER) or headers.get(SIGNATURE_HEADER.title()) or ""
    expected = compute_signature(secret, raw_body)
    if not hmac.compare_digest(provided, expected):
        raise WebhookVerificationError("Webhook imzası geçersiz.")


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

    def parse_webhook(self, *, headers: Mapping[str, str], raw_body: bytes) -> WebhookEvent:
        _verify_signature(self._secret, headers, raw_body)
        try:
            data = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise WebhookVerificationError("Webhook gövdesi ayrıştırılamadı.") from exc
        return _event_from_manual_payload(data)


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

    return WebhookEvent(
        event_id=event_id,
        event_type=event_type,
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


def create_billing_provider(provider: str, *, webhook_secret: str | None) -> BillingProvider:
    """Yapılandırmaya göre ödeme sağlayıcısı üretir (fabrika).

    ``manual`` (varsayılan) test-modu sağlayıcısını döndürür. Gerçek sağlayıcılar
    (iyzico/paytr/stripe) aynı seam'e takılır; sandbox/canlı anahtarları ve
    adaptörleri bağlandığında bu fabrikaya eklenir. Şimdilik seçilirse yapılandırma
    hatası verir (yanlışlıkla ödemesiz çalışmayı önler).
    """
    if provider == "manual":
        return ManualBillingProvider(webhook_secret=webhook_secret)
    raise BillingNotConfiguredError(
        f"Ödeme sağlayıcısı '{provider}' henüz bağlanmadı. Aynı BillingProvider "
        "seam'ine adaptör ve sandbox anahtarları eklenmelidir (bkz. billing/provider.py)."
    )
