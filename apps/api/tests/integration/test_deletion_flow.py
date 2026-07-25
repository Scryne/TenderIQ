"""KVKK iki fazlı silme akışı: yumuşak silme → görünmezlik → geri alma → kalıcı silme.

Gerçek DB (testcontainers) + RLS. Sınananlar:
- Yumuşak silinen ihale TÜM okuma yollarından düşüyor mu (liste, detay, panel,
  bulgular, export) — tek bir yolun kaçması KVKK açısından ihlaldir.
- Geri alma pencere içinde çalışıyor mu.
- Kalıcı süpürme CASCADE ile alt tabloları da götürüyor mu.
- Nesne depolama silinemezse DB satırı KORUNUYOR mu (yetim dosya bırakmama).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import tenderiq_worker.db as worker_db
from tenderiq_core.db.soft_delete import INCLUDE_DELETED
from tenderiq_core.findings import GroundingResolution, RiskCategory, RiskSeverity
from tenderiq_core.models import (
    Chunk,
    Document,
    DocumentKind,
    DocumentStatus,
    RiskFlag,
    Tender,
)
from tenderiq_core.models import ParsedElement as ParsedElementRow
from tenderiq_core.parsing.types import ElementKind, ParseSource
from tenderiq_core.services.deletion import purge_cutoff, purge_tenant_sync

pytestmark = pytest.mark.integration

QUOTE = "Yüklenici tüm maddeleri karşılamak zorundadır."


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


class DeletionEnv:
    """Tohumlanmış ortam: 1 ihale + 1 doküman + kaynak öğe + chunk + 1 risk bulgusu."""

    def __init__(self, client: TestClient) -> None:
        suffix = uuid.uuid4().hex[:8]
        self.client = client
        self.tenant_id, self.token = _register_and_login(
            client, slug=f"org-del-{suffix}", email=f"del-{suffix}@org.com"
        )
        tender = client.post(
            "/api/v1/tenders", json={"title": "Silinecek İhale"}, headers=_auth(self.token)
        )
        assert tender.status_code == 201
        self.tender_id = tender.json()["id"]

        self.tenant_uuid = uuid.UUID(self.tenant_id)
        tender_uuid = uuid.UUID(self.tender_id)
        self.document_id = uuid.uuid4()
        self.element_id = uuid.uuid4()
        self.chunk_id = uuid.uuid4()
        self.risk_id = uuid.uuid4()
        self.storage_key = f"{self.tenant_id}/{self.tender_id}/{self.document_id}/sartname.pdf"

        worker_db._engine = None
        worker_db._factory = None
        with worker_db.tenant_session(self.tenant_uuid) as session:
            session.add(
                Document(
                    id=self.document_id,
                    tenant_id=self.tenant_uuid,
                    tender_id=tender_uuid,
                    filename="şartname.pdf",
                    content_type="application/pdf",
                    storage_key=self.storage_key,
                    kind=DocumentKind.ADMINISTRATIVE,
                    status=DocumentStatus.UPLOADED,
                    size_bytes=1234,
                )
            )
            session.add(
                ParsedElementRow(
                    id=self.element_id,
                    tenant_id=self.tenant_uuid,
                    document_id=self.document_id,
                    seq=0,
                    page=4,
                    kind=ElementKind.PARAGRAPH,
                    source=ParseSource.DIGITAL,
                    text=QUOTE,
                    section="Madde 7.2",
                )
            )
            session.flush()
            session.add(
                Chunk(
                    id=self.chunk_id,
                    tenant_id=self.tenant_uuid,
                    document_id=self.document_id,
                    seq=0,
                    text=QUOTE,
                    page_start=4,
                    page_end=4,
                    element_seq_start=0,
                    element_seq_end=0,
                )
            )
            session.add(
                RiskFlag(
                    id=self.risk_id,
                    tenant_id=self.tenant_uuid,
                    tender_id=tender_uuid,
                    document_id=self.document_id,
                    source_element_id=self.element_id,
                    grounding_resolution=GroundingResolution.ELEMENT,
                    source_quote=QUOTE,
                    seq=0,
                    text="Gecikme cezası oranı yüksektir.",
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.PENALTY,
                )
            )


@pytest.fixture
def env(api_client: TestClient) -> DeletionEnv:
    return DeletionEnv(api_client)


def test_yumusak_silme_tum_okuma_yollarindan_dusurur(env: DeletionEnv) -> None:
    """Tek bir yolun silinmiş ihaleyi göstermesi KVKK açısından ihlaldir."""
    headers = _auth(env.token)

    # Silmeden önce her yol görüyor.
    assert env.client.get("/api/v1/tenders", headers=headers).json() != []
    assert env.client.get(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 200

    delete = env.client.delete(f"/api/v1/tenders/{env.tender_id}", headers=headers)
    assert delete.status_code == 204, delete.text

    # Liste
    assert env.client.get("/api/v1/tenders", headers=headers).json() == []
    # Detay
    assert env.client.get(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 404
    # Bulgu listesi (ihale join'i üzerinden)
    assert (
        env.client.get(f"/api/v1/tenders/{env.tender_id}/risks", headers=headers).status_code == 404
    )
    # Doküman listesi
    assert (
        env.client.get(f"/api/v1/tenders/{env.tender_id}/documents", headers=headers).status_code
        == 404
    )
    # Dosya indirme: silinmiş ihalenin PDF'ine imzalı URL VERİLMEMELİ.
    # (Bu yol dokümanı ihalesine join etmez; işaretin dokümanlara yayılmasının
    # sebebi tam olarak budur.)
    assert (
        env.client.get(f"/api/v1/documents/{env.document_id}/file", headers=headers).status_code
        == 404
    )
    # Panel: sayımda ve maruziyette görünmemeli
    panel = env.client.get("/api/v1/panel", headers=headers).json()
    assert panel["tenders"]["total"] == 0
    assert panel["exposures"] == []
    # Export
    export = env.client.post(
        f"/api/v1/tenders/{env.tender_id}/export",
        json={"format": "docx", "include_pending": False},
        headers=headers,
    )
    assert export.status_code == 404


def test_geri_alma_pencere_icinde_calisir(env: DeletionEnv) -> None:
    headers = _auth(env.token)
    assert env.client.delete(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 204
    assert env.client.get(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 404

    restore = env.client.post(f"/api/v1/tenders/{env.tender_id}/restore", headers=headers)
    assert restore.status_code == 200, restore.text
    assert restore.json()["title"] == "Silinecek İhale"

    # Geri geldi; bulguları ve dokümanları da geri açıldı.
    assert env.client.get(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 200
    risks = env.client.get(f"/api/v1/tenders/{env.tender_id}/risks", headers=headers).json()
    assert len(risks) == 1
    assert (
        len(env.client.get(f"/api/v1/tenders/{env.tender_id}/documents", headers=headers).json())
        == 1
    )

    # İkinci geri alma anlamsız → 409.
    assert (
        env.client.post(f"/api/v1/tenders/{env.tender_id}/restore", headers=headers).status_code
        == 409
    )


def test_geri_alma_tek_tek_silinen_dokumani_diriltmez(env: DeletionEnv) -> None:
    """Kullanıcı önce dokümanı, sonra ihaleyi sildiyse geri alma dokümanı geri getirmemeli.

    Aksi hâlde "şu yanlış dosyayı kaldır" eylemi, ilgisiz bir geri alma sırasında
    sessizce iptal edilmiş olurdu.
    """
    headers = _auth(env.token)
    assert (
        env.client.delete(f"/api/v1/documents/{env.document_id}", headers=headers).status_code
        == 204
    )
    assert env.client.delete(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 204
    assert (
        env.client.post(f"/api/v1/tenders/{env.tender_id}/restore", headers=headers).status_code
        == 200
    )

    # İhale geri geldi ama doküman silinmiş kalmalı.
    assert env.client.get(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 200
    assert (
        env.client.get(f"/api/v1/tenders/{env.tender_id}/documents", headers=headers).json() == []
    )


def test_dokuman_silme_ihaleyi_etkilemez(env: DeletionEnv) -> None:
    headers = _auth(env.token)
    assert (
        env.client.delete(f"/api/v1/documents/{env.document_id}", headers=headers).status_code
        == 204
    )
    # İhale ayakta, doküman listesinden düştü.
    assert env.client.get(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 200
    assert (
        env.client.get(f"/api/v1/tenders/{env.tender_id}/documents", headers=headers).json() == []
    )


def test_kalici_silme_cascade_ile_alt_tablolari_da_goturur(env: DeletionEnv) -> None:
    headers = _auth(env.token)
    assert env.client.delete(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 204

    deleted_keys: list[str] = []

    def _delete_object(key: str) -> bool:
        deleted_keys.append(key)
        return True

    # Saklama penceresi dolmuş gibi davran: cutoff'u geleceğe al.
    cutoff = datetime.now(UTC) + timedelta(days=1)
    with worker_db.tenant_session(env.tenant_uuid) as session:
        result = purge_tenant_sync(session, cutoff=cutoff, delete_object=_delete_object)

    assert result.tenders == 1
    assert result.objects_deleted == 1
    assert deleted_keys == [env.storage_key]

    # DB: ihale, doküman, öğe, chunk ve bulgu — hepsi gitmeli (CASCADE).
    with worker_db.tenant_session(env.tenant_uuid) as session:
        opts = {INCLUDE_DELETED: True}
        for model, name in (
            (Tender, "tender"),
            (Document, "document"),
            (ParsedElementRow, "parsed_element"),
            (Chunk, "chunk"),
            (RiskFlag, "risk_flag"),
        ):
            count = session.execute(
                select(func.count()).select_from(model).execution_options(**opts)
            ).scalar_one()
            assert count == 0, f"{name} tablosunda satır kaldı"


def test_nesne_silinemezse_db_satiri_korunur(env: DeletionEnv) -> None:
    """Yetim dosya bırakmaktansa silmeyi ertele: satır dururken tekrar denenebilir."""
    headers = _auth(env.token)
    assert env.client.delete(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 204

    def _failing_delete(key: str) -> bool:
        return False

    cutoff = datetime.now(UTC) + timedelta(days=1)
    with worker_db.tenant_session(env.tenant_uuid) as session:
        result = purge_tenant_sync(session, cutoff=cutoff, delete_object=_failing_delete)

    assert result.tenders == 0
    assert result.objects_failed == 1

    with worker_db.tenant_session(env.tenant_uuid) as session:
        count = session.execute(
            select(func.count()).select_from(Tender).execution_options(**{INCLUDE_DELETED: True})
        ).scalar_one()
        assert count == 1, "nesne silinemediği hâlde ihale satırı silinmiş"


def test_pencere_dolmadan_supurulmez(env: DeletionEnv) -> None:
    """Yeni silinen kayıt saklama penceresi içindeyken kalıcı silinmemeli."""
    headers = _auth(env.token)
    assert env.client.delete(f"/api/v1/tenders/{env.tender_id}", headers=headers).status_code == 204

    cutoff = purge_cutoff(30)  # 30 gün önce; az önce silinen bunun gerisinde değil
    with worker_db.tenant_session(env.tenant_uuid) as session:
        result = purge_tenant_sync(session, cutoff=cutoff, delete_object=lambda key: True)

    assert result.anything is False
    with worker_db.tenant_session(env.tenant_uuid) as session:
        count = session.execute(
            select(func.count()).select_from(Tender).execution_options(**{INCLUDE_DELETED: True})
        ).scalar_one()
        assert count == 1


def test_silme_kiracilar_arasi_izole(env: DeletionEnv, api_client: TestClient) -> None:
    """Başka kiracı bu ihaleyi silemez (RLS: yok sayılır → 404)."""
    suffix = uuid.uuid4().hex[:8]
    _other, other_token = _register_and_login(
        api_client, slug=f"org-oth-{suffix}", email=f"oth-{suffix}@org.com"
    )
    response = api_client.delete(f"/api/v1/tenders/{env.tender_id}", headers=_auth(other_token))
    assert response.status_code == 404

    # Sahibi için hâlâ etkin.
    assert (
        env.client.get(f"/api/v1/tenders/{env.tender_id}", headers=_auth(env.token)).status_code
        == 200
    )
