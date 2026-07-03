"""Tender/Document uçtan uca testi: API üzerinden RLS izolasyonu + RBAC + imzalı URL."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from tenderiq_core.security.tokens import create_access_token

pytestmark = pytest.mark.integration


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient, *, slug: str, email: str) -> tuple[str, str]:
    register = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert register.status_code == 201, register.text
    tenant_id: str = register.json()["tenant_id"]
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert login.status_code == 200
    token: str = login.json()["access_token"]
    return tenant_id, token


def test_tender_isolation_rbac_and_document(api_client: TestClient) -> None:
    tenant_a, token_a = _register_and_login(api_client, slug="org-a", email="a@orga.com")
    _tenant_b, token_b = _register_and_login(api_client, slug="org-b", email="b@orgb.com")

    # A ve B birer ihale oluşturur (yazma → admin rolü yeterli)
    created_a = api_client.post(
        "/api/v1/tenders", json={"title": "A İhalesi"}, headers=_auth(token_a)
    )
    assert created_a.status_code == 201, created_a.text
    tender_a_id = created_a.json()["id"]

    created_b = api_client.post(
        "/api/v1/tenders", json={"title": "B İhalesi"}, headers=_auth(token_b)
    )
    assert created_b.status_code == 201
    tender_b_id = created_b.json()["id"]

    # RLS (API üzerinden): A yalnızca kendi ihalesini listeler
    list_a = api_client.get("/api/v1/tenders", headers=_auth(token_a))
    assert list_a.status_code == 200
    assert [t["title"] for t in list_a.json()] == ["A İhalesi"]
    assert [
        t["title"] for t in api_client.get("/api/v1/tenders", headers=_auth(token_b)).json()
    ] == ["B İhalesi"]

    # A, B'nin ihalesine erişemez (RLS → 404)
    cross = api_client.post(
        f"/api/v1/tenders/{tender_b_id}/documents",
        json={"filename": "x.pdf", "content_type": "application/pdf"},
        headers=_auth(token_a),
    )
    assert cross.status_code == 404

    # RBAC: izleyici (viewer) rolüyle ihale oluşturmak yasak (403)
    secret = os.environ["AUTH_SECRET"]
    viewer_token = create_access_token(
        user_id=uuid.uuid4(), tenant_id=uuid.UUID(tenant_a), role="viewer", secret=secret
    )
    forbidden = api_client.post(
        "/api/v1/tenders", json={"title": "Yasak"}, headers=_auth(viewer_token)
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"

    # Doküman kaydı + imzalı yükleme URL'i
    doc = api_client.post(
        f"/api/v1/tenders/{tender_a_id}/documents",
        json={"filename": "sartname.pdf", "content_type": "application/pdf", "kind": "technical"},
        headers=_auth(token_a),
    )
    assert doc.status_code == 201, doc.text
    payload = doc.json()
    assert payload["document"]["status"] == "pending_upload"
    assert payload["document"]["kind"] == "technical"
    assert tenant_a in payload["storage_key"]
    assert payload["upload_url"].startswith("http")

    # Dokümanlar listelenir
    docs = api_client.get(f"/api/v1/tenders/{tender_a_id}/documents", headers=_auth(token_a))
    assert docs.status_code == 200
    assert len(docs.json()) == 1
