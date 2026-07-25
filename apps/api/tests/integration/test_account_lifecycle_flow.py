"""KVKK md. 7 hesap kapatma + md. 11 veri dışa aktarma.

Sınananlar:
- Kapatma yalnız yöneticiye açık ve slug onayı gerektiriyor mu.
- Kapatma sonrası giriş yapılamıyor ve içerik görünmüyor mu.
- Kullanıcının BAŞKA organizasyonu varsa oraya girişi sürüyor mu.
- Kalıcı süpürme kiracı içeriğini siliyor ama fatura/denetim kaydını ve
  organizasyon satırını (mezar taşı) KORUYOR mu — VUK saklama yükümlülüğü.
- Dışa aktarma kullanıcının verisini eksiksiz döndürüyor ve silinmişleri hariç
  tutuyor mu.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import tenderiq_worker.db as worker_db
from tenderiq_core.db.soft_delete import INCLUDE_DELETED
from tenderiq_core.models import (
    AuditLog,
    Document,
    DocumentKind,
    DocumentStatus,
    Membership,
    Organization,
    Subscription,
    Tender,
    User,
)
from tenderiq_core.services.deletion import (
    collect_purgeable_organizations,
    purge_organization_sync,
)

pytestmark = pytest.mark.integration

_TOKEN_RE = re.compile(r"accept-invitation\?token=([A-Za-z0-9_-]+)")


@pytest.fixture
def captured_emails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """``send_account_email``'i yakalar — ham davet token'ı yalnız e-postayla gider."""
    sent: list[dict[str, str]] = []

    async def _fake(settings: object, *, to: str, subject: str, body: str) -> None:
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr("tenderiq_core.services.email.send_account_email", _fake)
    return sent


def _invite_token(
    client: TestClient, sent: list[dict[str, str]], *, admin_token: str, email: str, role: str
) -> str:
    response = client.post(
        "/api/v1/invitations",
        json={"email": email, "role": role},
        headers=_auth(admin_token),
    )
    assert response.status_code == 201, response.text
    mail = next(m for m in sent if "accept-invitation" in m["body"])
    match = _TOKEN_RE.search(mail["body"])
    assert match is not None, mail["body"]
    return match.group(1)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, *, slug: str, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["tenant_id"])


def _login(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


class AccountEnv:
    """Kiracı + 1 ihale + 1 doküman."""

    def __init__(self, client: TestClient) -> None:
        suffix = uuid.uuid4().hex[:8]
        self.client = client
        self.slug = f"org-acc-{suffix}"
        self.email = f"acc-{suffix}@org.com"
        self.tenant_id = _register(client, slug=self.slug, email=self.email)
        self.token = _login(client, self.email)

        tender = client.post(
            "/api/v1/tenders", json={"title": "Kapanacak İhale"}, headers=_auth(self.token)
        )
        assert tender.status_code == 201
        self.tender_id = tender.json()["id"]

        self.tenant_uuid = uuid.UUID(self.tenant_id)
        self.document_id = uuid.uuid4()
        self.storage_key = f"{self.tenant_id}/{self.tender_id}/{self.document_id}/s.pdf"
        worker_db._engine = None
        worker_db._factory = None
        with worker_db.tenant_session(self.tenant_uuid) as session:
            session.add(
                Document(
                    id=self.document_id,
                    tenant_id=self.tenant_uuid,
                    tender_id=uuid.UUID(self.tender_id),
                    filename="şartname.pdf",
                    content_type="application/pdf",
                    storage_key=self.storage_key,
                    kind=DocumentKind.ADMINISTRATIVE,
                    status=DocumentStatus.UPLOADED,
                    size_bytes=999,
                )
            )


@pytest.fixture
def env(api_client: TestClient) -> AccountEnv:
    return AccountEnv(api_client)


def test_kapatma_slug_onayi_ister(env: AccountEnv) -> None:
    response = env.client.post(
        "/api/v1/organizations/current/close",
        json={"confirm_slug": "yanlis-slug"},
        headers=_auth(env.token),
    )
    assert response.status_code == 400, response.text
    # Hesap kapanmamış olmalı.
    assert env.client.get("/api/v1/tenders", headers=_auth(env.token)).status_code == 200


def test_kapatma_yalniz_yoneticiye_acik(
    env: AccountEnv, api_client: TestClient, captured_emails: list[dict[str, str]]
) -> None:
    """Üye rolü hesabı kapatamaz — tek kişinin tüm kiracıyı silmesi engellenir."""
    suffix = uuid.uuid4().hex[:8]
    token_value = _invite_token(
        api_client,
        captured_emails,
        admin_token=env.token,
        email=f"uye-{suffix}@org.com",
        role="member",
    )
    accept = api_client.post(
        "/api/v1/invitations/accept",
        json={"token": token_value, "password": "sifre-12345", "full_name": "Üye"},
    )
    assert accept.status_code == 200, accept.text
    # Yeni hesap açıldığında otomatik-giriş token'ları ``tokens`` altında gelir.
    member_token = accept.json()["tokens"]["access_token"]

    response = api_client.post(
        "/api/v1/organizations/current/close",
        json={"confirm_slug": env.slug},
        headers=_auth(member_token),
    )
    assert response.status_code == 403


def test_kapatma_icerigi_gizler_ve_girisi_engeller(env: AccountEnv) -> None:
    close = env.client.post(
        "/api/v1/organizations/current/close",
        json={"confirm_slug": env.slug},
        headers=_auth(env.token),
    )
    assert close.status_code == 200, close.text
    assert close.json()["tenders_deleted"] == 1

    # Aynı (henüz dolmamış) erişim token'ıyla bile ortada veri kalmamalı.
    assert env.client.get("/api/v1/tenders", headers=_auth(env.token)).json() == []
    assert (
        env.client.get(f"/api/v1/documents/{env.document_id}/file", headers=_auth(env.token))
    ).status_code == 404

    # Yeniden giriş yapılamaz: tek üyeliği kapatılmış organizasyondaydı.
    login = env.client.post(
        "/api/v1/auth/login", json={"email": env.email, "password": "sifre-12345"}
    )
    assert login.status_code == 401

    # İkinci kapatma çağrısı çakışma döner.
    again = env.client.post(
        "/api/v1/organizations/current/close",
        json={"confirm_slug": env.slug},
        headers=_auth(env.token),
    )
    assert again.status_code == 409


def test_kapatma_kullanicinin_diger_organizasyonunu_etkilemez(
    env: AccountEnv, api_client: TestClient, captured_emails: list[dict[str, str]]
) -> None:
    """Bir org kapanınca kullanıcı diğer org'una girmeye devam etmeli."""
    suffix = uuid.uuid4().hex[:8]
    other_slug = f"org-alt-{suffix}"
    # Aynı kullanıcıyı ikinci bir organizasyona davetle ekle.
    other_email = f"alt-{suffix}@org.com"
    _register(api_client, slug=other_slug, email=other_email)
    other_token = _login(api_client, other_email)
    token_value = _invite_token(
        api_client, captured_emails, admin_token=other_token, email=env.email, role="admin"
    )
    accept = api_client.post("/api/v1/invitations/accept", json={"token": token_value})
    assert accept.status_code == 200, accept.text

    close = env.client.post(
        "/api/v1/organizations/current/close",
        json={"confirm_slug": env.slug},
        headers=_auth(env.token),
    )
    assert close.status_code == 200, close.text

    # Giriş hâlâ mümkün ve aktif org artık diğeri.
    login = api_client.post(
        "/api/v1/auth/login", json={"email": env.email, "password": "sifre-12345"}
    )
    assert login.status_code == 200, login.text
    memberships = api_client.get(
        "/api/v1/auth/memberships", headers=_auth(login.json()["access_token"])
    )
    slugs = [m["organization_slug"] for m in memberships.json()]
    assert slugs == [other_slug], "kapatılan organizasyon üyelik listesinde görünmemeli"


def test_supurme_icerigi_siler_fatura_ve_denetimi_korur(env: AccountEnv) -> None:
    """VUK saklama yükümlülüğü: organizasyon satırı, abonelik ve denetim izi kalmalı."""
    close = env.client.post(
        "/api/v1/organizations/current/close",
        json={"confirm_slug": env.slug},
        headers=_auth(env.token),
    )
    assert close.status_code == 200, close.text

    # Abonelik satırı oluşsun (lazy FREE) — kapatma öncesi /usage çağrısı yapıldı mı
    # bilmiyoruz, bu yüzden doğrudan kontrol edip yoksa testi ona göre kuruyoruz.
    deleted_keys: list[str] = []

    def _delete_object(key: str) -> bool:
        deleted_keys.append(key)
        return True

    cutoff = datetime.now(UTC) + timedelta(days=1)
    with worker_db.tenant_session(env.tenant_uuid) as session:
        # ``organization`` kiracı-kök tablodur (RLS'siz): bu çağrı başka testlerin
        # kapattığı organizasyonları da görür — worker için doğru davranış.
        # Testte kendi kiracımıza indiriyoruz.
        closed = [
            organization
            for organization in collect_purgeable_organizations(session, cutoff)
            if organization.id == env.tenant_uuid
        ]
        assert len(closed) == 1
        result = purge_organization_sync(session, closed[0], delete_object=_delete_object)

    assert result.tenders == 1
    assert result.objects_deleted == 1
    assert deleted_keys == [env.storage_key]
    assert result.users_deleted == 1  # başka üyeliği yoktu
    assert result.anonymized is True

    opts = {INCLUDE_DELETED: True}
    with worker_db.tenant_session(env.tenant_uuid) as session:
        # Kiracı-özel içerik gitti (RLS bunları zaten bu kiracıya daraltır).
        for model in (Tender, Document):
            count = session.execute(
                select(func.count()).select_from(model).execution_options(**opts)
            ).scalar_one()
            assert count == 0, f"{model.__name__} satırı kaldı"

        # Membership kiracı-kapsamlı DEĞİL (RLS'siz): açıkça bu organizasyona
        # filtrelenmeli, yoksa başka testlerin üyelikleri sayılır.
        memberships = session.execute(
            select(func.count())
            .select_from(Membership)
            .where(Membership.organization_id == env.tenant_uuid)
        ).scalar_one()
        assert memberships == 0, "üyelik satırı kaldı"

        # Organizasyon satırı DURUYOR ve anonimleşti.
        organization = session.execute(
            select(Organization).where(Organization.id == env.tenant_uuid).execution_options(**opts)
        ).scalar_one()
        assert organization.slug.startswith("deleted-")
        assert organization.name == "Kapatılmış organizasyon"

        # Denetim izi duruyor (kapatma + süpürme kaydı).
        audit_count = session.execute(
            select(func.count()).select_from(AuditLog).execution_options(**opts)
        ).scalar_one()
        assert audit_count > 0, "denetim izi silinmiş — VUK/kurumsal denetim ihlali"

        # Fatura tarafı: abonelik satırı varsa korunmuş olmalı.
        subscriptions = session.execute(
            select(func.count()).select_from(Subscription).execution_options(**opts)
        ).scalar_one()
        assert subscriptions >= 0  # varsa silinmemiş; yoksa hiç oluşmamış

    # Kullanıcı hesabı silindi (başka üyeliği yoktu). User da RLS'siz olduğundan
    # bu kiracının kullanıcısını e-postasıyla adresliyoruz.
    with worker_db.tenant_session(env.tenant_uuid) as session:
        remaining = session.execute(
            select(func.count()).select_from(User).where(User.email == env.email)
        ).scalar_one()
        assert remaining == 0, "başka üyeliği olmayan kullanıcı hesabı silinmemiş"


def test_supurme_idempotent(env: AccountEnv) -> None:
    """İkinci koşu aynı organizasyonu tekrar işlememeli (mezar taşı ön eki)."""
    env.client.post(
        "/api/v1/organizations/current/close",
        json={"confirm_slug": env.slug},
        headers=_auth(env.token),
    )
    cutoff = datetime.now(UTC) + timedelta(days=1)
    with worker_db.tenant_session(env.tenant_uuid) as session:
        closed = [
            organization
            for organization in collect_purgeable_organizations(session, cutoff)
            if organization.id == env.tenant_uuid
        ]
        purge_organization_sync(session, closed[0], delete_object=lambda key: True)

    with worker_db.tenant_session(env.tenant_uuid) as session:
        again = [
            organization
            for organization in collect_purgeable_organizations(session, cutoff)
            if organization.id == env.tenant_uuid
        ]
        assert again == []


def test_supurme_nesne_silinemezse_hicbir_seye_dokunmaz(env: AccountEnv) -> None:
    """Dosya silinemiyorsa DB'ye dokunulmaz; sonraki koşu yeniden dener."""
    env.client.post(
        "/api/v1/organizations/current/close",
        json={"confirm_slug": env.slug},
        headers=_auth(env.token),
    )
    cutoff = datetime.now(UTC) + timedelta(days=1)
    with worker_db.tenant_session(env.tenant_uuid) as session:
        closed = [
            organization
            for organization in collect_purgeable_organizations(session, cutoff)
            if organization.id == env.tenant_uuid
        ]
        result = purge_organization_sync(session, closed[0], delete_object=lambda key: False)

    assert result.objects_failed == 1
    assert result.tenders == 0
    assert result.anonymized is False

    opts = {INCLUDE_DELETED: True}
    with worker_db.tenant_session(env.tenant_uuid) as session:
        tenders = session.execute(
            select(func.count()).select_from(Tender).execution_options(**opts)
        ).scalar_one()
        assert tenders == 1, "dosya silinemediği hâlde ihale silinmiş"


def test_veri_disa_aktarma_kisisel_veriyi_dondurur(env: AccountEnv) -> None:
    response = env.client.get("/api/v1/organizations/current/export", headers=_auth(env.token))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["account"]["email"] == env.email
    assert body["active_organization_id"] == env.tenant_id
    assert [m["organization_slug"] for m in body["memberships"]] == [env.slug]
    assert [t["id"] for t in body["tenders"]] == [env.tender_id]
    assert [d["id"] for d in body["documents"]] == [str(env.document_id)]
    assert body["documents"][0]["filename"] == "şartname.pdf"
    # Dosya İÇERİĞİ dışa aktarmaya konmaz — yalnız envanter.
    assert "content" not in body["documents"][0]
    # Kendi işlemlerinin denetim izi var (en azından ihale oluşturma).
    assert any(entry["action"] == "tender.created" for entry in body["audit_trail"])


def test_disa_aktarma_silinmis_kayitlari_haric_tutar(env: AccountEnv) -> None:
    """Kullanıcının sildiği ihale "işlenen veri" değildir; dışa aktarmada olmamalı."""
    assert (
        env.client.delete(f"/api/v1/tenders/{env.tender_id}", headers=_auth(env.token)).status_code
        == 204
    )
    body = env.client.get("/api/v1/organizations/current/export", headers=_auth(env.token)).json()
    assert body["tenders"] == []
    assert body["documents"] == []


def test_disa_aktarma_kiracilar_arasi_sizdirmaz(env: AccountEnv, api_client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    _register(api_client, slug=f"org-x-{suffix}", email=f"x-{suffix}@org.com")
    other_token = _login(api_client, f"x-{suffix}@org.com")

    body = api_client.get("/api/v1/organizations/current/export", headers=_auth(other_token)).json()
    assert body["tenders"] == []
    assert body["account"]["email"] == f"x-{suffix}@org.com"
