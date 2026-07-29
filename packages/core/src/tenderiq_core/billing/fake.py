"""Sahte ödeme sağlayıcısı — testler ve sözleşme doğrulaması.

``manual`` sağlayıcıdan farkı: ``manual`` bir **ürün davranışıdır** (test-modu,
yükseltme anında etkinleşir), bu ise bir **test aracıdır** ve gerçek sağlayıcının
davranışını taklit eder: checkout ödeme formuna yönlendirir, plan **ancak
webhook'la** açılır. Böylece testler "gerçek sağlayıcıda ne olur" sorusunu
ağa çıkmadan sınar.

Çağrılar kaydedilir; test hangi operasyonun hangi argümanlarla çağrıldığını
doğrulayabilir.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field

from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.billing.provider import (
    SIGNATURE_HEADER,
    CheckoutResult,
    ProviderSubscriptionState,
    WebhookEvent,
    WebhookVerificationError,
    _event_from_manual_payload,
)


@dataclass
class RecordedCall:
    """Sağlayıcıya yapılan tek bir operasyon çağrısı."""

    operation: str
    arguments: dict[str, object] = field(default_factory=dict)


@dataclass
class FakeBillingProvider:
    """Ağa çıkmayan, gerçek sağlayıcı semantiğini taklit eden sağlayıcı."""

    webhook_secret: str | None = None
    name: str = "fake"
    calls: list[RecordedCall] = field(default_factory=list)
    checkout_url: str = "https://fake-gateway.local/checkout"
    #: Mutabakat testleri için: sağlayıcıdaki "gerçek" durumlar.
    remote_state: dict[str, ProviderSubscriptionState] = field(default_factory=dict)

    async def create_checkout(
        self, *, tenant_id: uuid.UUID, target_tier: PlanTier
    ) -> CheckoutResult:
        self.calls.append(
            RecordedCall("create_checkout", {"tenant_id": tenant_id, "target_tier": target_tier})
        )
        return CheckoutResult(
            provider=self.name,
            # Gerçek sağlayıcı gibi: plan ANINDA açılmaz, webhook bekler.
            activated=False,
            checkout_url=self.checkout_url,
            provider_subscription_id=None,
        )

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        self.calls.append(
            RecordedCall("cancel_subscription", {"subscription_id": provider_subscription_id})
        )

    async def change_plan(
        self, *, provider_subscription_id: str, target_tier: PlanTier, immediate: bool
    ) -> None:
        self.calls.append(
            RecordedCall(
                "change_plan",
                {
                    "subscription_id": provider_subscription_id,
                    "target_tier": target_tier,
                    "immediate": immediate,
                },
            )
        )

    async def fetch_subscription(
        self, *, provider_subscription_id: str
    ) -> ProviderSubscriptionState | None:
        self.calls.append(
            RecordedCall("fetch_subscription", {"subscription_id": provider_subscription_id})
        )
        return self.remote_state.get(provider_subscription_id)

    def parse_webhook(self, *, headers: Mapping[str, str], raw_body: bytes) -> WebhookEvent:
        if not self.webhook_secret:
            raise WebhookVerificationError("Webhook sırrı yapılandırılmamış.")
        provided = headers.get(SIGNATURE_HEADER) or headers.get(SIGNATURE_HEADER.title()) or ""
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(provided, expected):
            raise WebhookVerificationError("Webhook imzası geçersiz.")
        try:
            data = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise WebhookVerificationError("Webhook gövdesi ayrıştırılamadı.") from exc
        return _event_from_manual_payload(data)

    def calls_for(self, operation: str) -> list[RecordedCall]:
        """Belirli bir operasyonun çağrıları."""
        return [call for call in self.calls if call.operation == operation]
