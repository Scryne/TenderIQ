"""Auth uçtan uca akış testi (kayıt → giriş → me), gerçek DB ile."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_register_login_me(api_client: TestClient) -> None:
    # Kayıt
    register = api_client.post(
        "/api/v1/auth/register",
        json={
            "org_name": "Acme A.Ş.",
            "org_slug": "acme",
            "email": "admin@acme.com",
            "password": "sifre-12345",
            "full_name": "Yönetici",
        },
    )
    assert register.status_code == 201, register.text
    user = register.json()
    assert user["email"] == "admin@acme.com"
    assert user["role"] == "admin"
    tenant_id = user["tenant_id"]

    # Aynı e-posta ile tekrar kayıt → 409 çakışma
    duplicate = api_client.post(
        "/api/v1/auth/register",
        json={
            "org_name": "Başka",
            "org_slug": "baska",
            "email": "admin@acme.com",
            "password": "sifre-12345",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"

    # Giriş → token
    login = api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@acme.com", "password": "sifre-12345"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    # me (token ile)
    me = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@acme.com"
    assert me.json()["tenant_id"] == tenant_id

    # me (token yok) → 401
    unauth = api_client.get("/api/v1/auth/me")
    assert unauth.status_code == 401
    assert unauth.json()["error"]["code"] == "unauthorized"

    # Yanlış parola → 401
    bad = api_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@acme.com", "password": "yanlis"},
    )
    assert bad.status_code == 401


def test_inactive_user_cannot_login(api_client: TestClient, app_database_url: str) -> None:
    """Pasifleştirilen (is_active=false) kullanıcı, parolası doğru olsa da giremez."""
    from sqlalchemy import create_engine, text

    register = api_client.post(
        "/api/v1/auth/register",
        json={
            "org_name": "Pasif Ltd.",
            "org_slug": "pasif-ltd",
            "email": "pasif@ornek.com",
            "password": "sifre-12345",
        },
    )
    assert register.status_code == 201, register.text

    engine = create_engine(app_database_url)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE user_account SET is_active = false WHERE email = :email"),
            {"email": "pasif@ornek.com"},
        )
    engine.dispose()

    login = api_client.post(
        "/api/v1/auth/login",
        json={"email": "pasif@ornek.com", "password": "sifre-12345"},
    )
    assert login.status_code == 401
    assert login.json()["error"]["code"] == "unauthorized"
