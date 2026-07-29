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


def test_resolve_target_iptal_erisimi_hemen_kesmez() -> None:
    """`/sartlar` §3: iptal, içinde bulunulan dönemin SONUNDA geçerli olur.

    Olay geldiği anda planı FREE'ye çekmek, müşterinin ödediği dönemi geri almak
    olurdu. Plan korunur, durum ACTIVE kalır; yalnız bitiş işaretlenir.
    """
    target = _resolve_target(
        _event("subscription.canceled", PlanTier.PRO, SubscriptionStatus.CANCELED), PlanTier.PRO
    )
    assert target.plan is PlanTier.PRO
    assert target.status is SubscriptionStatus.ACTIVE
    assert target.cancel_at_period_end is True


def test_resolve_target_donem_bitisi_erisimi_keser() -> None:
    target = _resolve_target(
        _event("subscription.expired", PlanTier.PRO, SubscriptionStatus.CANCELED), PlanTier.PRO
    )
    assert target.plan is PlanTier.FREE
    assert target.status is SubscriptionStatus.CANCELED
    assert target.cancel_at_period_end is False


def test_resolve_target_past_due_plani_korur() -> None:
    target = _resolve_target(
        _event("subscription.past_due", None, SubscriptionStatus.PAST_DUE), PlanTier.PRO
    )
    assert target.plan is PlanTier.PRO  # plan korunur; yalnız durum düşer
    assert target.status is SubscriptionStatus.PAST_DUE
    assert target.cancel_at_period_end is None  # bayrağa dokunulmaz


def test_resolve_target_etkinlestir_plani_uygular() -> None:
    target = _resolve_target(
        _event("subscription.activated", PlanTier.PRO, SubscriptionStatus.ACTIVE), PlanTier.FREE
    )
    assert target.plan is PlanTier.PRO
    assert target.status is SubscriptionStatus.ACTIVE


def test_resolve_target_aktif_olayi_bekleyen_iptali_temizlemez() -> None:
    """Sağlayıcının "hâlâ aktif" demesi, kullanıcının iptalini geri almaz.

    Sağlayıcı iptali henüz işlememiş olabilir; bayrağı burada temizlemek iptal
    etmiş müşteriyi sessizce aboneliğe geri döndürür ve bir dönem daha tahsil eder.
    """
    target = _resolve_target(
        _event("subscription.activated", PlanTier.PRO, SubscriptionStatus.ACTIVE), PlanTier.PRO
    )
    assert target.cancel_at_period_end is None


# ── iyzico adaptörü (Tur 4) ──────────────────────────────────────────────────

import base64  # noqa: E402
import hashlib as _hashlib  # noqa: E402
import hmac as _hmac  # noqa: E402
from typing import Any as _Any  # noqa: E402

import httpx as _httpx  # noqa: E402

from tenderiq_core.billing.fake import FakeBillingProvider  # noqa: E402
from tenderiq_core.billing.iyzico import (  # noqa: E402
    IYZICO_SIGNATURE_HEADER,
    IyzicoBillingProvider,
    build_authorization,
)
from tenderiq_core.billing.provider import BillingError  # noqa: E402


def _iyzico(client: _httpx.AsyncClient | None = None, **kwargs: _Any) -> IyzicoBillingProvider:
    defaults: dict[str, _Any] = {
        "api_key": "api-key",
        "secret_key": "secret-key",
        "webhook_secret": "webhook-secret",
        "plan_reference_codes": {PlanTier.PRO: "plan-pro", PlanTier.ENTERPRISE: "plan-ent"},
        "callback_url": "https://app.local/usage",
        "sandbox": True,
        "client": client,
    }
    defaults.update(kwargs)
    return IyzicoBillingProvider(**defaults)


def test_yetkilendirme_basligi_rastgele_anahtari_imzaya_katar() -> None:
    """Aynı gövdenin farklı bir uca tekrar oynatılması imzayı geçersiz kılmalı."""
    first = build_authorization(
        api_key="k", secret_key="s", uri_path="/a", payload="{}", random_key="r1"
    )
    same_body_other_path = build_authorization(
        api_key="k", secret_key="s", uri_path="/b", payload="{}", random_key="r1"
    )
    other_random = build_authorization(
        api_key="k", secret_key="s", uri_path="/a", payload="{}", random_key="r2"
    )

    assert first.startswith("IYZWSv2 ")
    assert first != same_body_other_path
    assert first != other_random


def test_yetkilendirme_basligi_gizli_anahtari_tasimaz() -> None:
    header = build_authorization(
        api_key="k", secret_key="cok-gizli", uri_path="/a", payload="{}", random_key="r"
    )

    decoded = base64.b64decode(header.removeprefix("IYZWSv2 ")).decode()

    assert "cok-gizli" not in decoded


async def test_checkout_plani_aninda_acmaz() -> None:
    """Gerçek sağlayıcıda etkinleşme ödeme sonrası webhook'la gelir."""
    transport = _httpx.MockTransport(
        lambda _r: _httpx.Response(200, json={"status": "success", "data": {"token": "tok"}})
    )
    async with _httpx.AsyncClient(transport=transport) as client:
        result = await _iyzico(client).create_checkout(
            tenant_id=uuid.uuid4(), target_tier=PlanTier.PRO
        )

    assert result.activated is False
    assert result.checkout_url == "tok"


async def test_plan_kodu_yapilandirilmamissa_reddedilir() -> None:
    """Kademe adı sağlayıcıya doğrudan gönderilmez; eşleme eksikse hata verir."""
    provider = _iyzico(plan_reference_codes={})

    with pytest.raises(BillingError, match="referans kodu"):
        await provider.create_checkout(tenant_id=uuid.uuid4(), target_tier=PlanTier.PRO)


async def test_saglayici_hatasi_billing_error_olur() -> None:
    transport = _httpx.MockTransport(
        lambda _r: _httpx.Response(
            200, json={"status": "failure", "errorCode": "5001", "errorMessage": "invalid"}
        )
    )
    async with _httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(BillingError, match="5001"):
            await _iyzico(client).create_checkout(tenant_id=uuid.uuid4(), target_tier=PlanTier.PRO)


@pytest.mark.parametrize(("immediate", "expected"), [(True, "NOW"), (False, "NEXT_PERIOD")])
async def test_yukseltme_aninda_dusurme_donem_sonunda(immediate: bool, expected: str) -> None:
    """/sartlar §3'teki kuralın koddaki karşılığı."""
    captured: dict[str, _Any] = {}

    def handler(request: _httpx.Request) -> _httpx.Response:
        captured["body"] = json.loads(request.content)
        return _httpx.Response(200, json={"status": "success"})

    async with _httpx.AsyncClient(transport=_httpx.MockTransport(handler)) as client:
        await _iyzico(client).change_plan(
            provider_subscription_id="sub-1", target_tier=PlanTier.PRO, immediate=immediate
        )

    assert captured["body"]["upgradePeriod"] == expected


def _sign_iyzico(secret: str, raw: bytes) -> str:
    return base64.b64encode(_hmac.new(secret.encode(), raw, _hashlib.sha256).digest()).decode()


def test_webhook_imzasi_dogrulanir_ve_kiraci_govdeden_gelir() -> None:
    tenant = uuid.uuid4()
    raw = json.dumps(
        {
            "iyziEventType": "subscription.activated",
            "token": "tok-1",
            "conversationId": str(tenant),
            "subscriptionStatus": "ACTIVE",
            "pricingPlanReferenceCode": "plan-pro",
            "subscriptionReferenceCode": "sub-9",
        }
    ).encode()
    headers = {IYZICO_SIGNATURE_HEADER: _sign_iyzico("webhook-secret", raw)}

    event = _iyzico().parse_webhook(headers=headers, raw_body=raw)

    assert event.tenant_id == tenant
    assert event.plan_tier is PlanTier.PRO
    assert event.status is SubscriptionStatus.ACTIVE
    assert event.provider_subscription_id == "sub-9"


def test_iyzico_webhook_gecersiz_imza_reddedilir() -> None:
    raw = b'{"iyziEventType":"x","subscriptionStatus":"ACTIVE"}'

    with pytest.raises(WebhookVerificationError):
        _iyzico().parse_webhook(headers={IYZICO_SIGNATURE_HEADER: "yanlis"}, raw_body=raw)


def test_eslenmemis_durum_sessizce_aktif_sayilmaz() -> None:
    """Tanınmayan bir sağlayıcı durumu, yetkilendirmeyi yanlışlıkla AÇMAMALI."""
    raw = json.dumps(
        {"iyziEventType": "x", "token": "t", "subscriptionStatus": "SOMETHING_NEW"}
    ).encode()
    headers = {IYZICO_SIGNATURE_HEADER: _sign_iyzico("webhook-secret", raw)}

    with pytest.raises(WebhookVerificationError, match="Eşlenmemiş"):
        _iyzico().parse_webhook(headers=headers, raw_body=raw)


# ── Sahte sağlayıcı sözleşmesi ───────────────────────────────────────────────


async def test_sahte_saglayici_gercek_semantigi_taklit_eder() -> None:
    """`manual`den farkı: plan checkout'ta AÇILMAZ, webhook bekler."""
    provider = FakeBillingProvider(webhook_secret="s")

    result = await provider.create_checkout(tenant_id=uuid.uuid4(), target_tier=PlanTier.PRO)

    assert result.activated is False
    assert result.checkout_url is not None
    assert len(provider.calls_for("create_checkout")) == 1


async def test_sahte_saglayici_operasyonlari_kaydeder() -> None:
    provider = FakeBillingProvider(webhook_secret="s")

    await provider.cancel_subscription(provider_subscription_id="sub-1")
    await provider.change_plan(
        provider_subscription_id="sub-1", target_tier=PlanTier.ENTERPRISE, immediate=True
    )

    assert provider.calls_for("cancel_subscription")[0].arguments["subscription_id"] == "sub-1"
    assert provider.calls_for("change_plan")[0].arguments["immediate"] is True
