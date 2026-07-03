"""Sağlık ve sürüm uçları testleri."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_sets_request_id_header(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.headers.get("X-Request-ID")


def test_version_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/system/version")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "TenderIQ"
