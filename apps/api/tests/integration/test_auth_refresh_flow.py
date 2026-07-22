"""Sprint 3.3-C: oturum yaşam döngüsü — refresh rotasyonu, reuse-detection, logout.

Gerçek DB + gerçek Redis gerektirir (refresh token durumu Redis'te yaşar). Redis
yoksa login ``refresh_token=None`` döner ve testler atlanır — CI'da redis servisi
mevcuttur (bkz. .github/workflows/ci.yml).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _register(client: TestClient, *, slug: str, email: str) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert resp.status_code == 201, resp.text


def _login_or_skip(client: TestClient, *, email: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert resp.status_code == 200, resp.text
    body: dict = resp.json()
    if body.get("refresh_token") is None:
        pytest.skip(
            "Refresh token üretilemedi (Redis kullanılamıyor); CI'da redis servisi gerekir."
        )
    return body


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_kisa_access_ve_refresh_dondurur(api_client: TestClient) -> None:
    _register(api_client, slug="rt-login", email="rt-login@org.com")
    body = _login_or_skip(api_client, email="rt-login@org.com")

    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600  # 60 dk (access_token_expire_minutes)
    assert isinstance(body["access_token"], str)
    assert isinstance(body["refresh_token"], str)

    me = api_client.get("/api/v1/auth/me", headers=_bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "rt-login@org.com"


def test_refresh_rotasyon_ve_reuse_detection(api_client: TestClient) -> None:
    _register(api_client, slug="rt-rot", email="rot@org.com")
    first = _login_or_skip(api_client, email="rot@org.com")
    rt1 = first["refresh_token"]

    # rt1 ile yenile → yeni access + yeni (farklı) refresh token.
    refreshed = api_client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert refreshed.status_code == 200, refreshed.text
    body2 = refreshed.json()
    rt2 = body2["refresh_token"]
    assert rt2 != rt1
    # Yenilenen access token da geçerlidir.
    assert (
        api_client.get("/api/v1/auth/me", headers=_bearer(body2["access_token"])).status_code == 200
    )

    # rt1 tek-kullanımlık: yeniden sunulması → 401 + tüm aile iptali.
    reuse = api_client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "unauthorized"

    # Aile iptal edildiğinden geçerli görünen rt2 de artık reddedilir (hırsızlık savunması).
    rt2_after = api_client.post("/api/v1/auth/refresh", json={"refresh_token": rt2})
    assert rt2_after.status_code == 401


def test_logout_oturumu_iptal_eder(api_client: TestClient) -> None:
    _register(api_client, slug="rt-out", email="out@org.com")
    body = _login_or_skip(api_client, email="out@org.com")
    rt = body["refresh_token"]

    out = api_client.post("/api/v1/auth/logout", json={"refresh_token": rt})
    assert out.status_code == 204

    # İptal sonrası yenileme reddedilir.
    after = api_client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert after.status_code == 401

    # Logout idempotenttir (aynı token yeniden) → yine 204.
    again = api_client.post("/api/v1/auth/logout", json={"refresh_token": rt})
    assert again.status_code == 204


def test_gecersiz_refresh_token_reddedilir(api_client: TestClient) -> None:
    _register(api_client, slug="rt-bad", email="bad@org.com")
    _login_or_skip(api_client, email="bad@org.com")  # Redis-varlık guard'ı
    bad = api_client.post("/api/v1/auth/refresh", json={"refresh_token": "gecersiz.token.xyz"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "unauthorized"
