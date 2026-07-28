"""API güvenlik başlıkları (J.1) — her yanıtta bulunmalı."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_guvenlik_basliklari_her_yanitta(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_kiracı_verisi_onbellege_alinmaz(client: TestClient) -> None:
    """Kimlikli JSON yanıtları ara belleklerde kalmamalı."""
    response = client.get("/api/v1/system/version")

    assert response.headers["cache-control"] == "no-store"


def test_hata_yanitlari_da_basliklari_tasir(client: TestClient) -> None:
    """Başlıklar istisna yolunda da eklenmeli: 404/500 sayfaları da gömülebilir."""
    response = client.get("/api/v1/olmayan-uc")

    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
