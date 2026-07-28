"""E-posta doğrulama kapısı (güvenlik denetimi #18, ASVS V2).

Kapı KAPALIYKEN (dev/test varsayılanı) hiçbir şey değişmez; AÇIKKEN maliyet
doğuran tek işlem — doküman kaydı açmak, yani OCR + LLM hattını taahhüt etmek —
e-posta sahipliği kanıtı ister. Okuma yolları etkilenmez.

Neden bu kapı: kapı olmadan bir saldırgan BAŞKASININ adresiyle hesap açıp
ücretsiz kotayı harcatabilir; adresin sahibi olan biteni yalnızca istemediği bir
doğrulama e-postasından anlar.
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tenderiq_core.config import get_settings

pytestmark = pytest.mark.integration

_VERIFY_TOKEN_RE = re.compile(r"verify-email\?token=([A-Za-z0-9_-]+)")


@pytest.fixture
def captured_emails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """Doğrulama bağlantısı yalnız e-postayla gider; testte yakalanır."""
    sent: list[dict[str, str]] = []

    async def _fake(settings: object, *, to: str, subject: str, body: str) -> None:
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("tenderiq_core.services.email.send_account_email", _fake)
    return sent


@pytest.fixture
def gated_client(api_client: TestClient) -> Iterator[TestClient]:
    """Doğrulama kapısı AÇIK istemci (production davranışı)."""
    os.environ["REQUIRE_VERIFIED_EMAIL"] = "true"
    get_settings.cache_clear()
    yield api_client
    os.environ.pop("REQUIRE_VERIFIED_EMAIL", None)
    get_settings.cache_clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient) -> tuple[str, str]:
    """Yeni (DOĞRULANMAMIŞ) kiracı açar; (e-posta, access_token) döner."""
    slug = f"org-gate-{uuid.uuid4().hex[:8]}"
    email = f"{slug}@org.com"
    register = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert register.status_code == 201, register.text
    assert register.json()["email_verified"] is False
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert login.status_code == 200, login.text
    return email, str(login.json()["access_token"])


def _create_tender(client: TestClient, token: str) -> str:
    response = client.post("/api/v1/tenders", json={"title": "Kapı Testi"}, headers=_auth(token))
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _create_document(client: TestClient, token: str, tender_id: str) -> object:
    return client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": "sartname.pdf", "content_type": "application/pdf"},
        headers=_auth(token),
    )


def test_dogrulanmamis_hesap_dokuman_yukleyemez(
    gated_client: TestClient, captured_emails: list[dict[str, str]]
) -> None:
    _, token = _register_and_login(gated_client)
    tender_id = _create_tender(gated_client, token)

    response = _create_document(gated_client, token, tender_id)

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "forbidden"


def test_dogrulanmamis_hesap_okuma_yollarini_kullanabilir(gated_client: TestClient) -> None:
    """Kapı yalnız maliyet doğuran işlemi kapatır; ürünü tamamen kilitlemez."""
    _, token = _register_and_login(gated_client)
    tender_id = _create_tender(gated_client, token)

    detail = gated_client.get(f"/api/v1/tenders/{tender_id}", headers=_auth(token))
    listing = gated_client.get("/api/v1/tenders", headers=_auth(token))

    assert detail.status_code == 200
    assert listing.status_code == 200


def test_dogrulama_sonrasi_yukleme_acilir(
    gated_client: TestClient, captured_emails: list[dict[str, str]]
) -> None:
    """Doğrulama DB'den okunur: kullanıcı elindeki token'ın dolmasını beklemez."""
    _, token = _register_and_login(gated_client)
    tender_id = _create_tender(gated_client, token)
    assert _create_document(gated_client, token, tender_id).status_code == 403

    # Yeniden gönderme kimlikli uçtur: adres numaralandırmayı engeller.
    resend = gated_client.post("/api/v1/auth/resend-verification", headers=_auth(token))
    assert resend.status_code == 204, resend.text
    mail = next(m for m in captured_emails if "verify-email" in m["body"])
    match = _VERIFY_TOKEN_RE.search(mail["body"])
    assert match is not None, mail["body"]
    verify = gated_client.post("/api/v1/auth/verify-email", json={"token": match.group(1)})
    assert verify.status_code == 204, verify.text

    # AYNI access token'la — yeni giriş gerekmeden geçmeli.
    assert _create_document(gated_client, token, tender_id).status_code == 201


def test_kapi_kapaliyken_dogrulanmamis_hesap_yukleyebilir(api_client: TestClient) -> None:
    """Varsayılan (dev) davranış korunur — kapı bilinçli olarak opt-in'dir."""
    get_settings.cache_clear()
    _, token = _register_and_login(api_client)
    tender_id = _create_tender(api_client, token)

    assert _create_document(api_client, token, tender_id).status_code == 201
