"""Kayıt modları (§4): open · invite_only · waitlist.

Üçü de çalışır durumda olmalı — ürünü kapalı betaya geri almak bir ortam
değişkeni değişikliğidir. Bu dosya, modun gerçekten davranışı değiştirdiğini ve
kapalı modlarda **davet akışının çalışmaya devam ettiğini** doğrular.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tenderiq_core.config import get_settings
from tenderiq_core.models import WaitlistEntry

pytestmark = pytest.mark.integration


@pytest.fixture
def signup_mode(api_client: TestClient) -> Iterator[callable]:
    """Kayıt modunu test içinde değiştirmeye izin verir; sonunda geri alır."""

    def _set(mode: str) -> TestClient:
        os.environ["SIGNUP_MODE"] = mode
        get_settings.cache_clear()
        return api_client

    yield _set
    os.environ.pop("SIGNUP_MODE", None)
    get_settings.cache_clear()


def _payload(slug: str) -> dict[str, str]:
    return {
        "org_name": slug,
        "org_slug": slug,
        "email": f"{slug}@org.com",
        "password": "sifre-12345",
    }


def _slug() -> str:
    return f"su-{uuid.uuid4().hex[:8]}"


def test_open_modda_hesap_acilir(signup_mode) -> None:
    client = signup_mode("open")

    response = client.post("/api/v1/auth/register", json=_payload(_slug()))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "created"
    assert body["user"]["role"] == "admin"


def test_invite_only_modda_kayit_reddedilir(signup_mode) -> None:
    client = signup_mode("invite_only")

    response = client.post("/api/v1/auth/register", json=_payload(_slug()))

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "forbidden"


def test_invite_only_modda_davet_akisi_calismaya_devam_eder(signup_mode) -> None:
    """Kapalı kayıt, davetli kullanıcıyı da kilitleseydi mod kullanılamaz olurdu."""
    client = signup_mode("open")
    slug = _slug()
    assert client.post("/api/v1/auth/register", json=_payload(slug)).status_code == 201
    login = client.post(
        "/api/v1/auth/login", json={"email": f"{slug}@org.com", "password": "sifre-12345"}
    )
    token = login.json()["access_token"]

    signup_mode("invite_only")
    invite = client.post(
        "/api/v1/invitations",
        json={"email": f"davetli-{slug}@org.com", "role": "member"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert invite.status_code == 201, invite.text


def test_waitlist_modda_talep_listeye_alinir(signup_mode, app_database_url: str) -> None:
    client = signup_mode("waitlist")
    slug = _slug()

    response = client.post("/api/v1/auth/register", json=_payload(slug))

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "waitlisted"
    assert response.json()["user"] is None

    # Hesap AÇILMAMIŞ olmalı: aynı bilgilerle giriş başarısız.
    login = client.post(
        "/api/v1/auth/login", json={"email": f"{slug}@org.com", "password": "sifre-12345"}
    )
    assert login.status_code == 401

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine(app_database_url)
    with Session(engine) as session:
        entry = session.scalar(
            select(WaitlistEntry).where(WaitlistEntry.email == f"{slug}@org.com")
        )
        assert entry is not None
        assert entry.organization_name == slug
    engine.dispose()


def test_waitlist_tekrar_basvuru_hata_uretmez(signup_mode) -> None:
    """Adresin listede olup olmadığını 4xx ile ayırmak numaralandırma yan kanalı olurdu."""
    client = signup_mode("waitlist")
    payload = _payload(_slug())

    first = client.post("/api/v1/auth/register", json=payload)
    second = client.post("/api/v1/auth/register", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["status"] == "waitlisted"


def test_tek_kullanimlik_eposta_reddedilir(signup_mode) -> None:
    client = signup_mode("open")
    slug = _slug()
    payload = {**_payload(slug), "email": f"{slug}@mailinator.com"}

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "validation_error"
