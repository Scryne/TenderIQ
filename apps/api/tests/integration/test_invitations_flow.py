"""Sprint 3.3-E-2: üye daveti akışı (oluştur/listele/iptal + kimliksiz kabul).

Gerçek DB (RLS/RBAC) ile. Ham davet token'ı yalnız e-postayla gider; test, e-posta
seam'ini (``send_account_email``) monkeypatch ederek bağlantıdan token'ı yakalar —
böylece dev'de yapıldığı gibi log ayrıştırmaya gerek kalmaz. ``Invitation`` RLS'siz
kimlik tablosu olduğundan süre-aşımı senaryosu satırı doğrudan ORM ile güncelller.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tenderiq_core.models import Invitation, Membership, Role

pytestmark = pytest.mark.integration

_TOKEN_RE = re.compile(r"accept-invitation\?token=([A-Za-z0-9_-]+)")


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, *, slug: str, email: str) -> tuple[str, str]:
    resp = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["tenant_id"], body["id"]


def _login(client: TestClient, *, email: str, password: str = "sifre-12345") -> str:  # noqa: S107
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _add_membership(url: str, *, user_id: str, org_id: str, role: Role) -> None:
    """İkinci bir üyeliği doğrudan ekler (RBAC kurulumları için; Membership RLS'siz)."""
    engine = create_engine(url)
    try:
        with Session(engine) as session, session.begin():
            session.add(
                Membership(
                    user_id=uuid.UUID(user_id),
                    organization_id=uuid.UUID(org_id),
                    role=role,
                )
            )
    finally:
        engine.dispose()


@pytest.fixture
def captured_emails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """``send_account_email``'i yakalar; gönderilen e-postaları biriktirir."""
    sent: list[dict[str, str]] = []

    async def _fake(settings: object, *, to: str, subject: str, body: str) -> None:
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("tenderiq_core.services.email.send_account_email", _fake)
    return sent


def _invite(
    client: TestClient, sent: list[dict[str, str]], *, admin_token: str, email: str, role: str
) -> str:
    """Davet oluşturur ve yakalanan e-postadan ham token'ı döndürür."""
    resp = client.post(
        "/api/v1/invitations",
        json={"email": email, "role": role},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    invite_mail = next(m for m in sent if "accept-invitation" in m["body"])
    match = _TOKEN_RE.search(invite_mail["body"])
    assert match is not None, invite_mail["body"]
    return match.group(1)


def test_davet_olustur_listele_kabul_yeni_kullanici(
    api_client: TestClient, captured_emails: list[dict[str, str]]
) -> None:
    org_a, _admin_id = _register(api_client, slug="inv-a", email="admin@inv-a.com")
    admin_token = _login(api_client, email="admin@inv-a.com")

    token = _invite(
        api_client, captured_emails, admin_token=admin_token, email="yeni@dış.com", role="member"
    )

    # Listede bir bekleyen davet görünür.
    listed = api_client.get("/api/v1/invitations", headers=_auth(admin_token)).json()
    assert len(listed) == 1
    assert listed[0]["email"] == "yeni@dış.com"
    assert listed[0]["status"] == "pending"
    assert listed[0]["expired"] is False

    # Kimliksiz önizleme: davet edilen hesabı henüz yok.
    preview = api_client.get(f"/api/v1/invitations/lookup?token={token}")
    assert preview.status_code == 200, preview.text
    assert preview.json()["account_exists"] is False
    assert preview.json()["organization_id"] == org_a
    assert preview.json()["role"] == "member"

    # Yeni kullanıcı parola belirleyip kabul eder → otomatik giriş token'ı gelir.
    accepted = api_client.post(
        "/api/v1/invitations/accept",
        json={"token": token, "full_name": "Yeni Üye", "password": "yeni-sifre-999"},
    )
    assert accepted.status_code == 200, accepted.text
    payload = accepted.json()
    assert payload["account_created"] is True
    assert payload["organization_id"] == org_a
    new_access = payload["tokens"]["access_token"]

    # Otomatik giriş token'ı org A'da member kimliği verir.
    me = api_client.get("/api/v1/auth/me", headers=_auth(new_access)).json()
    assert me["tenant_id"] == org_a
    assert me["role"] == "member"
    assert me["email"] == "yeni@dış.com"
    assert me["email_verified"] is True  # davet linki e-posta sahipliğini kanıtlar

    # Belirlenen parolayla normal giriş de çalışır.
    assert _login(api_client, email="yeni@dış.com", password="yeni-sifre-999")

    # Davet tek-kullanımlık: aynı token yeniden → 400; liste boşalır.
    replay = api_client.post("/api/v1/invitations/accept", json={"token": token})
    assert replay.status_code == 400
    assert api_client.get("/api/v1/invitations", headers=_auth(admin_token)).json() == []


def test_davet_kabul_mevcut_kullanici_otomatik_giris_yapmaz(
    api_client: TestClient, app_database_url: str, captured_emails: list[dict[str, str]]
) -> None:
    org_a, _ = _register(api_client, slug="inv-ex-a", email="admin@ex-a.com")
    _org_b, _user_b = _register(api_client, slug="inv-ex-b", email="uye@ex-b.com")
    admin_token = _login(api_client, email="admin@ex-a.com")

    token = _invite(
        api_client, captured_emails, admin_token=admin_token, email="uye@ex-b.com", role="member"
    )

    # Önizleme mevcut hesabı bildirir.
    preview = api_client.get(f"/api/v1/invitations/lookup?token={token}").json()
    assert preview["account_exists"] is True

    # Mevcut kullanıcı kabul eder: parola gerekmez, otomatik giriş YAPILMAZ.
    accepted = api_client.post("/api/v1/invitations/accept", json={"token": token})
    assert accepted.status_code == 200, accepted.text
    payload = accepted.json()
    assert payload["account_created"] is False
    assert payload["tokens"] is None

    # Kullanıcı artık iki org'a üye (normal giriş + memberships ile doğrulanır).
    member_token = _login(api_client, email="uye@ex-b.com")
    memberships = api_client.get("/api/v1/auth/memberships", headers=_auth(member_token)).json()
    assert {m["organization_id"] for m in memberships} == {org_a, _org_b}


def test_davet_iptal_edilince_kabul_edilemez(
    api_client: TestClient, captured_emails: list[dict[str, str]]
) -> None:
    _org, _ = _register(api_client, slug="inv-rev", email="admin@rev.com")
    admin_token = _login(api_client, email="admin@rev.com")
    token = _invite(
        api_client, captured_emails, admin_token=admin_token, email="davetli@rev.com", role="viewer"
    )

    invite_id = api_client.get("/api/v1/invitations", headers=_auth(admin_token)).json()[0]["id"]
    revoked = api_client.delete(f"/api/v1/invitations/{invite_id}", headers=_auth(admin_token))
    assert revoked.status_code == 204
    # İkinci iptal idempotent (204).
    assert (
        api_client.delete(f"/api/v1/invitations/{invite_id}", headers=_auth(admin_token))
    ).status_code == 204

    # İptal edilmiş davet kabul edilemez.
    accepted = api_client.post(
        "/api/v1/invitations/accept", json={"token": token, "password": "olmaz-sifre-1"}
    )
    assert accepted.status_code == 400


def test_davet_suresi_dolmus_kabul_400(
    api_client: TestClient, app_database_url: str, captured_emails: list[dict[str, str]]
) -> None:
    _org, _ = _register(api_client, slug="inv-exp", email="admin@exp.com")
    admin_token = _login(api_client, email="admin@exp.com")
    token = _invite(
        api_client, captured_emails, admin_token=admin_token, email="gec@exp.com", role="member"
    )

    # Davet satırının süresini geçmişe çek (Invitation RLS'siz; doğrudan ORM).
    engine = create_engine(app_database_url)
    try:
        with Session(engine) as session, session.begin():
            invitation = session.scalar(select(Invitation).where(Invitation.email == "gec@exp.com"))
            assert invitation is not None
            invitation.expires_at = datetime.now(UTC) - timedelta(hours=1)
    finally:
        engine.dispose()

    accepted = api_client.post(
        "/api/v1/invitations/accept", json={"token": token, "password": "yeni-sifre-999"}
    )
    assert accepted.status_code == 400
    # Süresi dolmuş davet önizlemede de geçersiz.
    assert api_client.get(f"/api/v1/invitations/lookup?token={token}").status_code == 400


def test_davet_zaten_uye_409(api_client: TestClient, captured_emails: list[dict[str, str]]) -> None:
    _org, _ = _register(api_client, slug="inv-dup", email="admin@dup.com")
    admin_token = _login(api_client, email="admin@dup.com")
    # Admin kendi e-postasını davet eder → zaten üye → 409.
    resp = api_client.post(
        "/api/v1/invitations",
        json={"email": "admin@dup.com", "role": "member"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_davet_rbac_member_403(
    api_client: TestClient, app_database_url: str, captured_emails: list[dict[str, str]]
) -> None:
    org_a, _ = _register(api_client, slug="inv-rbac-a", email="admin@rbac.com")
    _org_b, user_b = _register(api_client, slug="inv-rbac-b", email="member@rbac.com")
    _add_membership(app_database_url, user_id=user_b, org_id=org_a, role=Role.MEMBER)

    # B, A org'una MEMBER olarak geçer.
    member_token = _login(api_client, email="member@rbac.com")
    switched = api_client.post(
        "/api/v1/auth/switch-org", json={"organization_id": org_a}, headers=_auth(member_token)
    )
    assert switched.status_code == 200
    member_in_a = switched.json()["access_token"]

    # Member davet oluşturamaz / listeleyemez / iptal edemez (403).
    assert (
        api_client.post(
            "/api/v1/invitations",
            json={"email": "x@y.com", "role": "member"},
            headers=_auth(member_in_a),
        ).status_code
        == 403
    )
    assert api_client.get("/api/v1/invitations", headers=_auth(member_in_a)).status_code == 403
    assert (
        api_client.delete(
            f"/api/v1/invitations/{uuid.uuid4()}", headers=_auth(member_in_a)
        ).status_code
        == 403
    )


def test_davet_gecersiz_token_400(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/v1/invitations/accept", json={"token": "gecersiz-token", "password": "sifre-12345"}
    )
    assert resp.status_code == 400
    assert api_client.get("/api/v1/invitations/lookup?token=gecersiz").status_code == 400
