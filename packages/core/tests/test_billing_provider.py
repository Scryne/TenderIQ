"""Ödeme sağlayıcı seam'i saf birim testleri (DB'siz): imza + webhook ayrıştırma.

Manual (test-modu) sağlayıcının HMAC imza doğrulaması ve olay ayrıştırması burada
uçtan uca doğrulanır; gerçek sağlayıcı entegrasyonu aynı sözleşmeye takılır.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.billing.provider import (
    SIGNATURE_HEADER,
    BillingNotConfiguredError,
    ManualBillingProvider,
    WebhookEvent,
    WebhookVerificationError,
    compute_signature,
    create_billing_provider,
)
from tenderiq_core.models import SubscriptionStatus
from tenderiq_core.services.billing import _resolve_target

SECRET = "test-webhook-secret"


def _signed(payload: dict[str, object]) -> tuple[dict[str, str], bytes]:
    raw = json.dumps(payload).encode("utf-8")
    return {SIGNATURE_HEADER: compute_signature(SECRET, raw)}, raw


def test_manual_checkout_aninda_etkinlesir() -> None:
    provider = ManualBillingProvider(webhook_secret=SECRET)
    tenant_id = uuid.uuid4()
    result = asyncio.run(provider.create_checkout(tenant_id=tenant_id, target_tier=PlanTier.PRO))
    assert result.activated is True
    assert result.checkout_url is None
    assert result.provider == "manual"
    assert result.provider_subscription_id == f"manual_{tenant_id}"


def test_webhook_gecerli_imza_ayristirilir() -> None:
    provider = ManualBillingProvider(webhook_secret=SECRET)
    tenant_id = uuid.uuid4()
    headers, raw = _signed(
        {
            "event_id": "evt_1",
            "event_type": "subscription.activated",
            "tenant_id": str(tenant_id),
            "plan": "pro",
            "status": "active",
        }
    )
    event = provider.parse_webhook(headers=headers, raw_body=raw)
    assert event.event_id == "evt_1"
    assert event.tenant_id == tenant_id
    assert event.plan_tier is PlanTier.PRO
    assert event.status is SubscriptionStatus.ACTIVE


def test_webhook_gecersiz_imza_reddedilir() -> None:
    provider = ManualBillingProvider(webhook_secret=SECRET)
    _headers, raw = _signed({"event_id": "e", "event_type": "subscription.activated"})
    with pytest.raises(WebhookVerificationError):
        provider.parse_webhook(headers={SIGNATURE_HEADER: "deadbeef"}, raw_body=raw)


def test_webhook_sir_yoksa_reddedilir() -> None:
    provider = ManualBillingProvider(webhook_secret=None)
    headers, raw = _signed({"event_id": "e", "event_type": "subscription.activated"})
    with pytest.raises(WebhookVerificationError):
        provider.parse_webhook(headers=headers, raw_body=raw)


def test_webhook_bozuk_govde_reddedilir() -> None:
    provider = ManualBillingProvider(webhook_secret=SECRET)
    raw = b"{ bozuk json"
    headers = {SIGNATURE_HEADER: compute_signature(SECRET, raw)}
    with pytest.raises(WebhookVerificationError):
        provider.parse_webhook(headers=headers, raw_body=raw)


def test_fabrika_manual_dondurur_gercek_saglayici_hata() -> None:
    provider = create_billing_provider("manual", webhook_secret=SECRET)
    assert isinstance(provider, ManualBillingProvider)
    with pytest.raises(BillingNotConfiguredError):
        create_billing_provider("iyzico", webhook_secret=SECRET)


def _event(event_type: str, plan: PlanTier | None, status: SubscriptionStatus) -> WebhookEvent:
    return WebhookEvent(
        event_id="e",
        event_type=event_type,
        tenant_id=uuid.uuid4(),
        plan_tier=plan,
        status=status,
    )


def test_resolve_target_iptal_free_yapar() -> None:
    plan, status = _resolve_target(
        _event("subscription.canceled", PlanTier.PRO, SubscriptionStatus.CANCELED), PlanTier.PRO
    )
    assert plan is PlanTier.FREE
    assert status is SubscriptionStatus.CANCELED


def test_resolve_target_past_due_plani_korur() -> None:
    plan, status = _resolve_target(
        _event("subscription.past_due", None, SubscriptionStatus.PAST_DUE), PlanTier.PRO
    )
    assert plan is PlanTier.PRO  # plan korunur; yalnız durum düşer
    assert status is SubscriptionStatus.PAST_DUE


def test_resolve_target_etkinlestir_plani_uygular() -> None:
    plan, status = _resolve_target(
        _event("subscription.activated", PlanTier.PRO, SubscriptionStatus.ACTIVE), PlanTier.FREE
    )
    assert plan is PlanTier.PRO
    assert status is SubscriptionStatus.ACTIVE
