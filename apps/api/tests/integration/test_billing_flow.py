"""Sprint 3.3-B uçtan uca: planlar + checkout (test modu) + webhook (imza + idempotency).

Gerçek HTTP (TestClient) + gerçek DB (testcontainers) + RLS + gerçek Redis (idempotency).
Manual (test-modu) sağlayıcı: checkout planı anında etkinleştirir → /usage yeni limitleri
yansıtır; webhook HMAC imzayla doğrulanır ve tekrarlanan olay durumu bir kez uygular.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

WEBHOOK_SECRET = "test-webhook-secret"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient, *, slug: str, email: str) -> tuple[str, str]:
    register = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert register.status_code == 201, register.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert login.status_code == 200
    return register.json()["tenant_id"], login.json()["access_token"]


@pytest.fixture
def billing_client(api_client: TestClient) -> Iterator[TestClient]:
    """api_client + webhook sırrı (per-request SettingsDep bunu okur)."""
    from tenderiq_core.config import get_settings

    os.environ["BILLING_WEBHOOK_SECRET"] = WEBHOOK_SECRET
    get_settings.cache_clear()
    try:
        yield api_client
    finally:
        os.environ.pop("BILLING_WEBHOOK_SECRET", None)
        get_settings.cache_clear()


def _sign(payload: dict[str, object]) -> tuple[str, dict[str, str]]:
    raw = json.dumps(payload)
    sig = hmac.new(WEBHOOK_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw, {"x-tenderiq-signature": sig, "content-type": "application/json"}


def test_planlar_listelenir_free_gecerli(billing_client: TestClient) -> None:
    _tenant, token = _register_and_login(billing_client, slug="bil-1", email="b1@org.com")
    resp = billing_client.get("/api/v1/billing/plans", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    plans = {p["tier"]: p for p in resp.json()}
    assert set(plans) == {"free", "pro", "enterprise"}
    assert plans["free"]["is_current"] is True
    assert plans["pro"]["is_current"] is False
    assert plans["pro"]["monthly_price_try"] == 1500


def test_checkout_test_modu_plani_aninda_yukseltir(billing_client: TestClient) -> None:
    _tenant, token = _register_and_login(billing_client, slug="bil-2", email="b2@org.com")

    # Yükseltmeden önce FREE limitleri.
    before = billing_client.get("/api/v1/usage", headers=_auth(token)).json()
    assert before["plan"] == "free"
    assert before["documents"]["limit"] == 5

    checkout = billing_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token)
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["activated"] is True
    assert body["checkout_url"] is None
    assert body["plan"] == "pro"

    # /usage artık PRO limitlerini yansıtır.
    after = billing_client.get("/api/v1/usage", headers=_auth(token)).json()
    assert after["plan"] == "pro"
    assert after["documents"]["limit"] == 100
    assert after["pages"]["limit"] == 5000


def test_webhook_imza_dogrular_ve_idempotent(billing_client: TestClient) -> None:
    tenant_id, token = _register_and_login(billing_client, slug="bil-4", email="b4@org.com")
    event_id = f"evt_{uuid.uuid4()}"  # her koşuda benzersiz (Redis dedup anahtarı kalıcı)

    raw, headers = _sign(
        {
            "event_id": event_id,
            "event_type": "subscription.activated",
            "tenant_id": tenant_id,
            "plan": "pro",
            "status": "active",
        }
    )

    # İlk teslim: uygulanır.
    first = billing_client.post("/api/v1/billing/webhook", content=raw, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "applied"
    assert billing_client.get("/api/v1/usage", headers=_auth(token)).json()["plan"] == "pro"

    # Tekrar teslim (aynı olay): idempotent — durum bir kez uygulanır.
    second = billing_client.post("/api/v1/billing/webhook", content=raw, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "duplicate"
    assert billing_client.get("/api/v1/usage", headers=_auth(token)).json()["plan"] == "pro"


def test_webhook_gecersiz_imza_reddedilir(billing_client: TestClient) -> None:
    tenant_id, _token = _register_and_login(billing_client, slug="bil-5", email="b5@org.com")
    raw = json.dumps(
        {
            "event_id": f"evt_{uuid.uuid4()}",
            "event_type": "subscription.activated",
            "tenant_id": tenant_id,
            "plan": "pro",
        }
    )
    resp = billing_client.post(
        "/api/v1/billing/webhook",
        content=raw,
        headers={"x-tenderiq-signature": "deadbeef", "content-type": "application/json"},
    )
    assert resp.status_code == 400, resp.text
