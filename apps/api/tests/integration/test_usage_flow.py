"""Sprint 3.3-A uçtan uca: abonelik + kota + kullanım (GET /usage, enforcement, sayfa senkronu).

Gerçek HTTP (TestClient) + gerçek DB (testcontainers) + RLS + worker parse fazı.
Nesne depolama in-memory sahte servisle, hibrit parser sabit sonuçlu sahte
parser'la değiştirilir; kota mantığı (kayıt+tamamlamada enforcement, tamamlamada
kullanım kaydı, parse sonrası sayfa senkronu) uçtan uca doğrulanır.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import tenderiq_worker.db as worker_db
import tenderiq_worker.parsing as worker_parsing
from tenderiq_core.billing.plans import PLANS, PlanTier
from tenderiq_core.email import EmailMessage, MemoryEmailProvider
from tenderiq_core.parsing import (
    BoundingBox,
    ElementKind,
    ParsedDocument,
    ParsedElement,
    ParseSource,
)
from tenderiq_core.storage import ObjectInfo

pytestmark = pytest.mark.integration

PDF_BYTES = b"%PDF-1.7\n%TenderIQ kota testi\n"

# Sahte parser çıktısı: 3 sayfa (sayfa kotası, doküman kotasından ayrı doğrulansın).
FAKE_PARSED = ParsedDocument(
    elements=[
        ParsedElement(
            text="1. KAPSAM",
            page=1,
            kind=ElementKind.HEADING,
            bbox=BoundingBox(x0=72.0, y0=90.0, x1=200.0, y1=110.0),
        ),
    ],
    page_count=3,
    source=ParseSource.DIGITAL,
)


class FakeStorage:
    """StorageService arayüzünün in-memory eşleniği (kota testleri için yeterli alt küme)."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def presigned_put_url(self, key: str, *, content_type: str, expires_in: int = 3600) -> str:
        return f"https://fake-storage.local/{key}?put"

    def presigned_get_url(self, key: str, *, expires_in: int = 3600) -> str:
        return f"https://fake-storage.local/{key}?get"

    def head_object(self, key: str) -> ObjectInfo | None:
        data = self.objects.get(key)
        return None if data is None else ObjectInfo(size_bytes=len(data), content_type="")

    def read_prefix(self, key: str, *, length: int) -> bytes:
        return self.objects[key][:length]

    def download_file(self, key: str, destination: Path) -> None:
        destination.write_bytes(self.objects[key])

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)
        self.deleted.append(key)


class FakeDocumentParser:
    """Hibrit parser'ın sabit sonuçlu eşleniği (3 sayfa)."""

    def parse(self, path: Path) -> ParsedDocument:
        return FAKE_PARSED


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
    return register.json()["user"]["tenant_id"], login.json()["access_token"]


@pytest.fixture
def usage_client(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, FakeStorage]:
    """api_client + sahte depolama/parser; worker fabrikası test DB'sine sıfırlanır."""
    storage = FakeStorage()
    api_client.app.state.storage = storage  # type: ignore[attr-defined]
    api_client.app.state.enqueue_document_job = lambda job_id, tenant_id: None  # type: ignore[attr-defined]
    monkeypatch.setattr(worker_parsing, "_storage", storage)
    monkeypatch.setattr(worker_parsing, "_parser", FakeDocumentParser())
    worker_db._engine = None
    worker_db._factory = None
    return api_client, storage


def _create_and_complete(
    client: TestClient, storage: FakeStorage, *, tender_id: str, token: str, filename: str
) -> str:
    """Bir doküman kaydı açar, "yükler" ve tamamlar; job id döndürür."""
    created = client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": filename, "content_type": "application/pdf"},
        headers=_auth(token),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    storage.objects[body["storage_key"]] = PDF_BYTES
    complete = client.post(
        f"/api/v1/documents/{body['document']['id']}/complete", headers=_auth(token)
    )
    assert complete.status_code == 200, complete.text
    job_id: str = complete.json()["job"]["id"]
    return job_id


def test_usage_varsayilan_ucretsiz_plan(usage_client: tuple[TestClient, FakeStorage]) -> None:
    client, _storage = usage_client
    _tenant, token = _register_and_login(client, slug="org-u1", email="u1@org.com")

    resp = client.get("/api/v1/usage", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"] == "free"
    assert body["plan_name"] == "Ücretsiz"
    assert body["status"] == "active"
    # Limitler plan kaydından okunur; sayı burada TEKRARLANMAZ (Tur 16: kotalar
    # bütçeden türetiliyor, sabit sayı yazmak testi kalibrasyona düşman yapardı).
    free = PLANS[PlanTier.FREE]
    assert body["documents"] == {"used": 0, "limit": free.documents_per_month}
    assert body["pages"] == {"used": 0, "limit": free.pages_per_month}
    assert body["period_start"] < body["period_end"]

    # J.6 görünürlüğü: bütçe ve depolama da dönmeli.
    assert body["budget"]["limit_try"] == float(free.llm_budget_try_per_month or 0)
    assert body["budget"]["spent_try"] == 0
    assert body["budget"]["remaining_try"] == float(free.llm_budget_try_per_month or 0)
    # Rezerve tutar HARCANMIŞ değildir ve ayrı alandır.
    assert body["budget"]["reserved_try"] == 0
    assert body["budget"]["soft_exceeded"] is False
    assert body["storage"]["limit_bytes"] == free.storage_bytes
    assert body["storage"]["used_bytes"] == 0
    assert body["storage"]["remaining_bytes"] == free.storage_bytes


def test_dokuman_kotasi_enforce_edilir(usage_client: tuple[TestClient, FakeStorage]) -> None:
    client, storage = usage_client
    _tenant, token = _register_and_login(client, slug="org-u2", email="u2@org.com")
    tender_id = client.post(
        "/api/v1/tenders", json={"title": "Kota İhalesi"}, headers=_auth(token)
    ).json()["id"]

    limit = PLANS[PlanTier.FREE].documents_per_month
    assert limit is not None
    for i in range(limit):
        _create_and_complete(
            client, storage, tender_id=tender_id, token=token, filename=f"dok-{i}.pdf"
        )

    usage = client.get("/api/v1/usage", headers=_auth(token)).json()
    assert usage["documents"] == {"used": limit, "limit": limit}

    # Kotayı aşan kayıt denemesi 402 döner (yükleme başlatılmadan erken red).
    extra = client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": "dok-fazla.pdf", "content_type": "application/pdf"},
        headers=_auth(token),
    )
    assert extra.status_code == 402, extra.text
    error = extra.json()["error"]
    assert error["code"] == "quota_exceeded"
    assert error["details"][0] == {"limit_kind": "documents", "used": limit, "limit": limit}


def test_kullanim_kiracilar_arasi_izole(usage_client: tuple[TestClient, FakeStorage]) -> None:
    client, storage = usage_client
    _tenant_a, token_a = _register_and_login(client, slug="org-ua", email="ua@org.com")
    _tenant_b, token_b = _register_and_login(client, slug="org-ub", email="ub@org.com")

    tender_a = client.post("/api/v1/tenders", json={"title": "A"}, headers=_auth(token_a)).json()[
        "id"
    ]
    _create_and_complete(client, storage, tender_id=tender_a, token=token_a, filename="a.pdf")
    _create_and_complete(client, storage, tender_id=tender_a, token=token_a, filename="a2.pdf")

    # A iki doküman kullandı; B'nin kullanımı sıfır (RLS izolasyonu).
    assert client.get("/api/v1/usage", headers=_auth(token_a)).json()["documents"]["used"] == 2
    assert client.get("/api/v1/usage", headers=_auth(token_b)).json()["documents"]["used"] == 0


def test_sayfa_kotasi_parse_sonrasi_senkronlanir(
    usage_client: tuple[TestClient, FakeStorage],
) -> None:
    client, storage = usage_client
    tenant_id, token = _register_and_login(client, slug="org-u3", email="u3@org.com")
    tender_id = client.post(
        "/api/v1/tenders", json={"title": "Sayfa"}, headers=_auth(token)
    ).json()["id"]

    job_id = _create_and_complete(
        client, storage, tender_id=tender_id, token=token, filename="sayfa.pdf"
    )

    # Tamamlamada pages=0 kaydı açıldı: doküman 1, sayfa henüz 0.
    before = client.get("/api/v1/usage", headers=_auth(token)).json()
    assert before["documents"]["used"] == 1
    assert before["pages"]["used"] == 0

    # Worker parse fazı gerçek sayfa sayısını (3) kullanım kaydına yazar.
    worker_parsing.run_parsing_phase(uuid.UUID(job_id), uuid.UUID(tenant_id))

    after = client.get("/api/v1/usage", headers=_auth(token)).json()
    assert after["documents"]["used"] == 1
    assert after["pages"]["used"] == 3


# ── Yönetici teşhis ucu (J.6 görünürlük, Tur 16) ─────────────────────────────


_INVITE_TOKEN_RE = re.compile(r"accept-invitation\?token=([A-Za-z0-9_-]+)")


@pytest.fixture
def captured_emails(api_client: TestClient) -> list[EmailMessage]:
    """Davet token'ı e-postayla gidiyor; sağlayıcıyı bellek eşleniğiyle değiştir."""
    provider = MemoryEmailProvider()
    api_client.app.state.email_provider = provider  # type: ignore[attr-defined]
    return provider.sent


def _invite_member(
    client: TestClient, sent: list[EmailMessage], *, token: str, email: str, role: str
) -> str:
    """Kiracıya verilen rolde bir üye ekler; o üyenin access token'ını döndürür."""
    invite = client.post(
        "/api/v1/invitations",
        json={"email": email, "role": role},
        headers=_auth(token),
    )
    assert invite.status_code == 201, invite.text
    mail = next(m for m in sent if "accept-invitation" in m.text)
    match = _INVITE_TOKEN_RE.search(mail.text)
    assert match is not None, mail.text
    accepted = client.post(
        "/api/v1/invitations/accept",
        json={"token": match.group(1), "full_name": "Üye", "password": "yeni-sifre-999"},
    )
    assert accepted.status_code == 200, accepted.text
    sent.clear()  # sonraki davetin postasıyla karışmasın
    return str(accepted.json()["tokens"]["access_token"])


def test_yonetici_ucu_teshis_sayilarini_dondurur(
    usage_client: tuple[TestClient, FakeStorage],
) -> None:
    """ "Tavan neden gevşek davrandı" sorusunun yanıtı: unpriced_calls + kur durumu."""
    client, _storage = usage_client
    _tenant, token = _register_and_login(client, slug="org-adm", email="adm@org.com")

    resp = client.get("/api/v1/usage/admin", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["spent_try"] == 0
    assert body["calls"] == 0
    assert body["unpriced_calls"] == 0
    assert body["reserved_try"] == 0
    # Test ortamında LLM_USD_TRY_RATE tanımsız: tavanın FİİLEN yok olduğu hâl
    # yöneticiye görünmeli — sessiz kalması tam da kapatılan arızaydı.
    assert body["fx_rate_missing"] is True
    assert body["period_start"] < body["period_end"]


def test_yonetici_ucu_uye_ve_izleyiciye_kapali(
    usage_client: tuple[TestClient, FakeStorage],
    captured_emails: list[EmailMessage],
) -> None:
    """Teşhis verisi kiracı YÖNETİCİSİYLE sınırlı; üye/izleyici 403 almalı."""
    client, _storage = usage_client
    _tenant, admin_token = _register_and_login(client, slug="org-rol", email="rol@org.com")
    captured_emails.clear()

    for email, role in (("uye@org.com", "member"), ("izleyici@org.com", "viewer")):
        member_token = _invite_member(
            client, captured_emails, token=admin_token, email=email, role=role
        )
        # Normal /usage herkese açık…
        assert client.get("/api/v1/usage", headers=_auth(member_token)).status_code == 200
        # …teşhis ucu değil.
        forbidden = client.get("/api/v1/usage/admin", headers=_auth(member_token))
        assert forbidden.status_code == 403, f"{role}: {forbidden.text}"


def test_yonetici_ucu_baska_kiracinin_harcamasini_gostermez(
    usage_client: tuple[TestClient, FakeStorage],
) -> None:
    """Sızıntı testi: uç RLS kapsamındadır, çapraz-kiracı operatör ucu DEĞİLDİR."""
    client, storage = usage_client
    _a, token_a = _register_and_login(client, slug="org-sa", email="sa@org.com")
    _b, token_b = _register_and_login(client, slug="org-sb", email="sb@org.com")

    tender_a = client.post("/api/v1/tenders", json={"title": "A"}, headers=_auth(token_a)).json()[
        "id"
    ]
    _create_and_complete(client, storage, tender_id=tender_a, token=token_a, filename="a.pdf")

    a_view = client.get("/api/v1/usage/admin", headers=_auth(token_a)).json()
    b_view = client.get("/api/v1/usage/admin", headers=_auth(token_b)).json()
    assert a_view["calls"] == 0  # LLM çağrısı yok (parse fazı koşmadı)
    assert b_view["calls"] == 0
    # B'nin doküman kullanımı A'nınkinden bağımsız kalmalı.
    assert client.get("/api/v1/usage", headers=_auth(token_b)).json()["documents"]["used"] == 0
    assert client.get("/api/v1/usage", headers=_auth(token_a)).json()["documents"]["used"] == 1
