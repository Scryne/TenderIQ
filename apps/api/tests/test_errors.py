"""Tutarlı hata modeli testleri (§9.1)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_unknown_route_returns_structured_error(client: TestClient) -> None:
    response = client.get("/api/v1/bilinmeyen-uc")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert isinstance(body["error"]["message"], str)
