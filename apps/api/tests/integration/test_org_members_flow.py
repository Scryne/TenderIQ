"""Sprint 3.3-E: çoklu-org (switch-org + üyelikler) + üye yönetimi (liste/rol/çıkarma).

Gerçek DB (RLS/RBAC) ile. ``Membership`` RLS'siz kimlik tablosu olduğundan test,
ikinci üyeliği doğrudan ORM ile ekler (davet akışı 3.3-E'nin ikinci parçası).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tenderiq_core.models import Membership, Role

pytestmark = pytest.mark.integration


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, *, slug: str, email: str) -> tuple[str, str]:
    """Kayıt yapar; (organizasyon_id, kullanıcı_id) döndürür."""
    resp = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["tenant_id"], body["id"]


def _login(client: TestClient, *, email: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _add_membership(url: str, *, user_id: str, org_id: str, role: Role) -> None:
    """İkinci bir üyeliği doğrudan ekler (Membership RLS'siz; davet henüz yok)."""
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


def test_switch_org_ve_membership_listesi(api_client: TestClient, app_database_url: str) -> None:
    org_a, user_a = _register(api_client, slug="ms-a", email="a@ms.com")
    org_b, _user_b = _register(api_client, slug="ms-b", email="b@ms.com")
    # Kullanıcı A'yı B org'una ÜYE olarak ekle (çoklu-org).
    _add_membership(app_database_url, user_id=user_a, org_id=org_b, role=Role.MEMBER)

    token_a = _login(api_client, email="a@ms.com")
    # Giriş deterministik: en erken üyelik = A org'u (A önce kaydoldu).
    me = api_client.get("/api/v1/auth/me", headers=_auth(token_a)).json()
    assert me["tenant_id"] == org_a
    assert me["role"] == "admin"

    # Üyelikler: iki org, A aktif.
    memberships = api_client.get("/api/v1/auth/memberships", headers=_auth(token_a)).json()
    by_org = {m["organization_id"]: m for m in memberships}
    assert set(by_org) == {org_a, org_b}
    assert by_org[org_a]["is_active"] is True
    assert by_org[org_a]["role"] == "admin"
    assert by_org[org_b]["is_active"] is False
    assert by_org[org_b]["role"] == "member"

    # B'ye geç → yeni token B org'u için (rol member).
    switched = api_client.post(
        "/api/v1/auth/switch-org", json={"organization_id": org_b}, headers=_auth(token_a)
    )
    assert switched.status_code == 200, switched.text
    token_b = switched.json()["access_token"]
    me_b = api_client.get("/api/v1/auth/me", headers=_auth(token_b)).json()
    assert me_b["tenant_id"] == org_b
    assert me_b["role"] == "member"

    # Üye olunmayan org'a geçiş → 403.
    org_c, _ = _register(api_client, slug="ms-c", email="c@ms.com")
    forbidden = api_client.post(
        "/api/v1/auth/switch-org", json={"organization_id": org_c}, headers=_auth(token_a)
    )
    assert forbidden.status_code == 403


def test_uye_yonetimi_liste_rol_cikarma(api_client: TestClient, app_database_url: str) -> None:
    org_a, _user_a = _register(api_client, slug="mm-a", email="admin@mm.com")
    _org_b, user_b = _register(api_client, slug="mm-b", email="member@mm.com")
    # B kullanıcısını A org'una ÜYE ekle.
    _add_membership(app_database_url, user_id=user_b, org_id=org_a, role=Role.MEMBER)

    admin_token = _login(api_client, email="admin@mm.com")
    member_token = _login(api_client, email="member@mm.com")  # varsayılan org: B (kendi)

    # A org üye listesi: admin + member (2).
    members = api_client.get("/api/v1/members", headers=_auth(admin_token)).json()
    roles = {m["email"]: m["role"] for m in members}
    assert roles == {"admin@mm.com": "admin", "member@mm.com": "member"}

    # RBAC: member A org'unda yönetim yapamaz — ama member'ın aktif org'u B (kendi,
    # tek admin kendisi). A org'u yönetimi için A üyesi olarak token'ı B org'una ait;
    # bu yüzden member_token A org üyelerini göremez (kendi org'unu görür = 1 üye).
    member_view = api_client.get("/api/v1/members", headers=_auth(member_token)).json()
    assert [m["email"] for m in member_view] == ["member@mm.com"]

    # Admin, B'nin rolünü admin yapar → 200.
    promote = api_client.patch(
        f"/api/v1/members/{user_b}", json={"role": "admin"}, headers=_auth(admin_token)
    )
    assert promote.status_code == 200, promote.text
    assert promote.json()["role"] == "admin"

    # Admin, B'yi tekrar member yapar (artık iki admin var, son-admin koruması tetiklenmez).
    demote = api_client.patch(
        f"/api/v1/members/{user_b}", json={"role": "member"}, headers=_auth(admin_token)
    )
    assert demote.status_code == 200
    assert demote.json()["role"] == "member"

    # Admin, B'yi çıkarır → 204; liste tek üyeye iner.
    removed = api_client.delete(f"/api/v1/members/{user_b}", headers=_auth(admin_token))
    assert removed.status_code == 204
    after = api_client.get("/api/v1/members", headers=_auth(admin_token)).json()
    assert [m["email"] for m in after] == ["admin@mm.com"]

    # Son yönetici korumaları: tek admin kendini düşüremez / çıkaramaz.
    admin_id = next(m["user_id"] for m in after)
    self_demote = api_client.patch(
        f"/api/v1/members/{admin_id}", json={"role": "member"}, headers=_auth(admin_token)
    )
    assert self_demote.status_code == 409
    self_remove = api_client.delete(f"/api/v1/members/{admin_id}", headers=_auth(admin_token))
    assert self_remove.status_code == 409


def test_uye_yonetimi_rbac_ve_bulunamayan(api_client: TestClient, app_database_url: str) -> None:
    org_a, _user_a = _register(api_client, slug="rb-a", email="admin@rb.com")
    _org_b, user_b = _register(api_client, slug="rb-b", email="member@rb.com")
    _add_membership(app_database_url, user_id=user_b, org_id=org_a, role=Role.MEMBER)

    # B, A org'unda member olsa da aktif org'u B; A org üyesini yönetmek için A
    # bağlamında token gerekir. B'nin A'ya geçip (member) yönetim denemesi → 403.
    member_token = _login(api_client, email="member@rb.com")
    switched = api_client.post(
        "/api/v1/auth/switch-org", json={"organization_id": org_a}, headers=_auth(member_token)
    )
    assert switched.status_code == 200
    member_in_a = switched.json()["access_token"]
    # Member rolüyle rol değiştirme/çıkarma yasak (403).
    forbidden_patch = api_client.patch(
        f"/api/v1/members/{user_b}", json={"role": "admin"}, headers=_auth(member_in_a)
    )
    assert forbidden_patch.status_code == 403
    forbidden_delete = api_client.delete(f"/api/v1/members/{user_b}", headers=_auth(member_in_a))
    assert forbidden_delete.status_code == 403

    # Admin, org'da olmayan bir kullanıcıyı yönetmeye çalışır → 404.
    admin_token = _login(api_client, email="admin@rb.com")
    missing = api_client.patch(
        f"/api/v1/members/{uuid.uuid4()}", json={"role": "member"}, headers=_auth(admin_token)
    )
    assert missing.status_code == 404
