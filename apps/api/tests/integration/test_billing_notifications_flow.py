"""Abonelik olaylarında e-posta bildirimi (Tur 8 / madde 2).

En kritik davranış **e-postanın gitmesi değil, gidememesinin bir şeyi
bozmaması**: gönderim hatası isteği düşürseydi sağlayıcı 5xx görüp aynı olayı
yeniden gönderir ve durum ikinci kez uygulanırdı. Yani "e-posta gidemedi"
arızası bir "abonelik iki kez işlendi" arızasına dönüşürdü.

Bellek sağlayıcısıyla; dış servise çıkılmaz.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from tenderiq_core.config import get_settings
from tenderiq_core.email.message import EmailMessage
from tenderiq_core.email.provider import EmailDeliveryError, MemoryEmailProvider

pytestmark = pytest.mark.integration

WEBHOOK_SECRET = "test-notify-secret"


@pytest.fixture
def notify_client(api_client: TestClient) -> Iterator[TestClient]:
    previous = os.environ.get("BILLING_PROVIDER")
    os.environ["BILLING_PROVIDER"] = "manual"
    os.environ["BILLING_WEBHOOK_SECRET"] = WEBHOOK_SECRET
    get_settings.cache_clear()
    try:
        yield api_client
    finally:
        os.environ.pop("BILLING_WEBHOOK_SECRET", None)
        if previous is None:
            os.environ.pop("BILLING_PROVIDER", None)
        else:
            os.environ["BILLING_PROVIDER"] = previous
        get_settings.cache_clear()


@pytest.fixture
def sent_emails(notify_client: TestClient) -> list[EmailMessage]:
    """Uygulamanın SAĞLAYICISINI bellek sağlayıcısıyla değiştirir (seam testi)."""
    provider = MemoryEmailProvider()
    notify_client.app.state.email_provider = provider
    return provider.sent


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


def _register_and_login(client: TestClient, *, slug: str) -> tuple[str, str, str]:
    email = f"{slug}@org.com"
    register = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert register.status_code == 201, register.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert login.status_code == 200, login.text
    return register.json()["user"]["tenant_id"], email, login.json()["access_token"]


def _sign(payload: dict[str, object]) -> tuple[str, dict[str, str]]:
    raw = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw, {"x-tenderiq-signature": signature, "content-type": "application/json"}


def _event(tenant_id: str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "event_id": f"ntf_{uuid.uuid4()}",
        "event_type": "subscription.activated",
        "tenant_id": tenant_id,
        "plan": "pro",
        "status": "active",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body.update(overrides)
    return body


#: Abonelik yaşam döngüsüne ait mesaj türleri. Kayıt sırasında gönderilen
#: doğrulama e-postası da aynı sağlayıcıya düşer; süzmeden yapılan bir
#: "hiç e-posta gitmedi" iddiası onu yakalar ve testi yanlış yerde kırar.
_SUBSCRIPTION_KINDS = frozenset(
    {
        "subscription_started",
        "subscription_renewed",
        "subscription_suspended",
        "subscription_canceled",
        "subscription_resumed",
        "payment_succeeded",
        "payment_failed",
    }
)


def _subscription_mail(messages: list[EmailMessage]) -> list[EmailMessage]:
    return [m for m in messages if m.kind.value in _SUBSCRIPTION_KINDS]


def _kinds(messages: list[EmailMessage]) -> list[str]:
    return [message.kind.value for message in _subscription_mail(messages)]


# ── Olay → e-posta ───────────────────────────────────────────────────────────


def test_abonelik_basladi_bildirimi_gider(
    notify_client: TestClient, sent_emails: list[EmailMessage]
) -> None:
    tenant, email, _token = _register_and_login(notify_client, slug=_slug("ntf-bas"))
    raw, headers = _sign(_event(tenant))

    response = notify_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert response.json()["status"] == "applied"
    assert "subscription_started" in _kinds(sent_emails)
    started = next(m for m in sent_emails if m.kind.value == "subscription_started")
    assert started.to == email
    assert "Pro" in started.subject


def test_yenileme_ve_askiya_alma_bildirimleri(
    notify_client: TestClient, sent_emails: list[EmailMessage]
) -> None:
    tenant, _email, _token = _register_and_login(notify_client, slug=_slug("ntf-yen"))

    for event_type in ("subscription.renewed", "subscription.past_due"):
        raw, headers = _sign(_event(tenant, event_type=event_type))
        notify_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    kinds = _kinds(sent_emails)
    assert "subscription_renewed" in kinds
    assert "payment_failed" in kinds


def test_iptal_bildirimi_erisim_tarihini_tasir(
    notify_client: TestClient, sent_emails: list[EmailMessage]
) -> None:
    """İptal e-postasının tek işi "erişimim ne zaman bitiyor" sorusunu
    cevaplamak; tarihsiz gitmesi onu değersiz kılar."""
    _tenant, _email, token = _register_and_login(notify_client, slug=_slug("ntf-ipt"))
    notify_client.post("/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token))
    sent_emails.clear()

    response = notify_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))
    assert response.status_code == 200, response.text

    canceled = next(m for m in sent_emails if m.kind.value == "subscription_canceled")
    period_end = response.json()["current_period_end"]
    day = datetime.fromisoformat(period_end).strftime("%d.%m.%Y")
    assert day in canceled.text
    assert "bilinmiyor" not in canceled.text


def test_iptal_geri_alma_bildirimi_gider(
    notify_client: TestClient, sent_emails: list[EmailMessage]
) -> None:
    _tenant, _email, token = _register_and_login(notify_client, slug=_slug("ntf-geri"))
    notify_client.post("/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token))
    notify_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))
    sent_emails.clear()

    notify_client.post("/api/v1/billing/subscription/resume", headers=_auth(token))

    assert "subscription_resumed" in _kinds(sent_emails)


def test_bildirim_gerektirmeyen_olay_eposta_uretmez(
    notify_client: TestClient, sent_emails: list[EmailMessage]
) -> None:
    """Her olaya e-posta çıkarsa gerçekten önemli olanlar okunmaz."""
    tenant, _email, _token = _register_and_login(notify_client, slug=_slug("ntf-sessiz"))
    raw, headers = _sign(_event(tenant, event_type="subscription.updated"))

    notify_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert _subscription_mail(sent_emails) == []


# ── Tekrar koruması ve izolasyon ─────────────────────────────────────────────


def test_mukerrer_teslim_ikinci_epostayi_uretmez(
    notify_client: TestClient, sent_emails: list[EmailMessage]
) -> None:
    """Sağlayıcı aynı olayı iki kez teslim eder; kullanıcı iki "ödemeniz alındı"
    almamalı. Tekrar koruması mevcut idempotency anahtarından gelir."""
    tenant, _email, _token = _register_and_login(notify_client, slug=_slug("ntf-tek"))
    raw, headers = _sign(_event(tenant))

    notify_client.post("/api/v1/billing/webhook", content=raw, headers=headers)
    notify_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert _kinds(sent_emails).count("subscription_started") == 1


def test_bildirim_yalnizca_kendi_kiracisinin_yoneticisine_gider(
    notify_client: TestClient, sent_emails: list[EmailMessage]
) -> None:
    """Ödeme bildirimi başka kiracının yöneticisine SIZMAMALI."""
    tenant_a, email_a, _token_a = _register_and_login(notify_client, slug=_slug("ntf-a"))
    _tenant_b, email_b, _token_b = _register_and_login(notify_client, slug=_slug("ntf-b"))
    raw, headers = _sign(_event(tenant_a))

    notify_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    recipients = {message.to for message in _subscription_mail(sent_emails)}
    assert email_a in recipients
    assert email_b not in recipients


# ── Gönderim hatası webhook'u DÜŞÜRMEZ ───────────────────────────────────────


class _BrokenEmailProvider:
    """Her gönderimde patlayan sağlayıcı."""

    name = "broken"

    async def send(self, message: EmailMessage, *, sender: str) -> str:
        raise EmailDeliveryError("sağlayıcı kapalı")


def test_eposta_hatasi_webhooku_dusurmez(notify_client: TestClient) -> None:
    """Bu testin sabitlediği şey maddenin çekirdeği.

    E-posta hatası isteği düşürseydi sağlayıcı 5xx görür, aynı olayı yeniden
    gönderir ve abonelik ikinci kez uygulanırdı — bildirim arızası bir
    yetkilendirme arızasına dönüşürdü.
    """
    notify_client.app.state.email_provider = _BrokenEmailProvider()
    tenant, _email, token = _register_and_login(notify_client, slug=_slug("ntf-kirik"))
    raw, headers = _sign(_event(tenant))

    response = notify_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "applied"
    # Olay GERÇEKTEN uygulandı.
    assert notify_client.get("/api/v1/usage", headers=_auth(token)).json()["plan"] == "pro"


def test_eposta_hatasi_iptali_dusurmez(notify_client: TestClient) -> None:
    """Aynı kural kendi uçlarımız için de geçerli: bildirim gidemedi diye
    kullanıcının iptali başarısız görünmemeli."""
    _tenant, _email, token = _register_and_login(notify_client, slug=_slug("ntf-kirik2"))
    notify_client.post("/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token))
    notify_client.app.state.email_provider = _BrokenEmailProvider()

    response = notify_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["cancel_at_period_end"] is True


# ── Bastırma ─────────────────────────────────────────────────────────────────


def test_bastirilmis_adrese_gonderilmez(
    notify_client: TestClient, sent_emails: list[EmailMessage], app_database_url: str
) -> None:
    """Kalıcı bounce almış adrese ödeme bildirimi de gitmez (Tur 4 kuralı)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from tenderiq_core.models import EmailSuppression, SuppressionReason

    tenant, email, _token = _register_and_login(notify_client, slug=_slug("ntf-bas2"))
    engine = create_engine(app_database_url)
    try:
        with Session(engine) as session, session.begin():
            session.add(EmailSuppression(email=email, reason=SuppressionReason.HARD_BOUNCE))
    finally:
        engine.dispose()

    raw, headers = _sign(_event(tenant))
    response = notify_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert response.json()["status"] == "applied"  # olay yine de uygulandı
    assert _subscription_mail(sent_emails) == []
