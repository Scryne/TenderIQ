"""Sprint 3.3-D: e-posta doğrulama + parola sıfırlama (tek-kullanımlık token'lar).

Gerçek DB + gerçek Redis gerektirir (tek-kullanımlık token'lar Redis'te). Redis
yoksa testler atlanır — CI'da redis servisi mevcuttur. Doğrulama/sıfırlama
token'ları normalde e-postayla gider (dev'de loglanır); test, token'ı gerçek
servisle Redis'e yazıp uçları uçtan uca sürer (log ayrıştırmaya gerek yok).
"""

from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
import redis as redis_sync
from fastapi.testclient import TestClient
from redis.asyncio import Redis as AsyncRedis

from tenderiq_core.config import get_settings
from tenderiq_core.services import one_time_tokens

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _require_redis() -> None:
    """Redis erişilemezse bu modüldeki testleri atla (tek-kullanımlık token'lar Redis'te)."""
    try:
        client = redis_sync.Redis.from_url(get_settings().redis_url)
        client.ping()
        client.close()
    except redis_sync.RedisError:
        pytest.skip("Redis kullanılamıyor; hesap doğrulama/sıfırlama testleri redis gerektirir.")


def _issue_token(purpose: str, user_id: uuid.UUID) -> str:
    """Gerçek servisle bir tek-kullanımlık token üretir (uygulamayla aynı Redis'e)."""

    async def _run() -> str:
        client = AsyncRedis.from_url(get_settings().redis_url)
        try:
            return await one_time_tokens.issue(
                client, purpose=purpose, user_id=user_id, ttl_seconds=3600
            )
        finally:
            await client.aclose()

    return asyncio.run(_run())


def _register(client: TestClient, *, slug: str, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email_verified"] is False  # yeni kayıt doğrulanmamış
    user_id: str = body["id"]
    return user_id


def _login(
    client: TestClient,
    *,
    email: str,
    password: str = "sifre-12345",  # noqa: S107 - test parolası
) -> httpx.Response:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_email_dogrulama_akisi(api_client: TestClient) -> None:
    user_id = _register(api_client, slug="acc-verify", email="verify@org.com")
    token = _login(api_client, email="verify@org.com").json()["access_token"]

    # /me başlangıçta doğrulanmamış.
    me = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email_verified"] is False

    # Geçerli doğrulama token'ıyla → 204, ardından /me doğrulanmış.
    verify_token = _issue_token(one_time_tokens.EMAIL_VERIFY, uuid.UUID(user_id))
    verified = api_client.post("/api/v1/auth/verify-email", json={"token": verify_token})
    assert verified.status_code == 204, verified.text
    me2 = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me2.json()["email_verified"] is True

    # Token tek-kullanımlık: aynı token yeniden → 400.
    replay = api_client.post("/api/v1/auth/verify-email", json={"token": verify_token})
    assert replay.status_code == 400


def test_gecersiz_dogrulama_token_400(api_client: TestClient) -> None:
    _register(api_client, slug="acc-bad", email="bad-verify@org.com")
    bad = api_client.post("/api/v1/auth/verify-email", json={"token": "gecersiz-token"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "validation_error"


def test_forgot_password_numaralandirma_sizdirmaz(api_client: TestClient) -> None:
    _register(api_client, slug="acc-forgot", email="forgot@org.com")
    # Var olan kullanıcı → 204.
    known = api_client.post("/api/v1/auth/forgot-password", json={"email": "forgot@org.com"})
    assert known.status_code == 204
    # Var olmayan kullanıcı → yine 204 (varlık sızmaz).
    unknown = api_client.post("/api/v1/auth/forgot-password", json={"email": "yok@org.com"})
    assert unknown.status_code == 204


def test_parola_sifirlama_oturumlari_iptal_eder(api_client: TestClient) -> None:
    user_id = _register(api_client, slug="acc-reset", email="reset@org.com")
    login = _login(api_client, email="reset@org.com").json()
    old_refresh = login.get("refresh_token")
    if old_refresh is None:
        pytest.skip("Refresh token üretilemedi (Redis); sıfırlama-oturum testi redis gerektirir.")

    # Sıfırlama token'ıyla yeni parola belirle → 204.
    reset_token = _issue_token(one_time_tokens.PASSWORD_RESET, uuid.UUID(user_id))
    reset = api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "yeni-sifre-999"},
    )
    assert reset.status_code == 204, reset.text

    # Eski parola artık geçersiz, yeni parola geçerli.
    assert _login(api_client, email="reset@org.com", password="sifre-12345").status_code == 401
    assert _login(api_client, email="reset@org.com", password="yeni-sifre-999").status_code == 200

    # Sıfırlama mevcut oturumları iptal etti: eski refresh token artık çalışmaz.
    refreshed = api_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 401

    # Token tek-kullanımlık: aynı sıfırlama token'ı yeniden → 400.
    replay = api_client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "baska-sifre-000"},
    )
    assert replay.status_code == 400


def test_resend_verification_204(api_client: TestClient) -> None:
    _register(api_client, slug="acc-resend", email="resend@org.com")
    token = _login(api_client, email="resend@org.com").json()["access_token"]
    resp = api_client.post(
        "/api/v1/auth/resend-verification", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204
