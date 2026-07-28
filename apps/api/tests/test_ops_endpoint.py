"""/ops/metrics — erişim kapısı ve yanıt sözleşmesi."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tenderiq_core.config import get_settings

OPS_TOKEN = "test-ops-token-0123456789"


class _EmptyPipeline:
    """Boş pencere döndüren sahte pipeline — uç, Redis'siz de sınanabilsin."""

    def __init__(self) -> None:
        self._reads: list[str] = []

    def hgetall(self, key: str) -> None:
        self._reads.append("hash")

    def llen(self, key: str) -> None:
        self._reads.append("list")

    async def execute(self) -> list[Any]:
        return [{} if kind == "hash" else 0 for kind in self._reads]


class _EmptyRedis:
    def pipeline(self, transaction: bool = True) -> _EmptyPipeline:
        return _EmptyPipeline()

    async def aclose(self) -> None:
        """Lifespan kapanışının çağırdığı gerçek istemci sözleşmesi."""


@pytest.fixture
def ops_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Ops token'ı yapılandırılmış istemci (metrik kaynağı sahte, boş pencere)."""
    monkeypatch.setenv("OPS_METRICS_TOKEN", OPS_TOKEN)
    get_settings.cache_clear()
    client.app.state.redis = _EmptyRedis()
    yield client
    get_settings.cache_clear()


def test_token_yapilandirilmamissa_uc_yok_sayilir(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kapalı kurulumda ucun VARLIĞI bile sızmamalı — 401 değil, 404."""
    # Boş ortam değişkeni .env dosyasındaki olası değeri de ezer: test, çalıştıran
    # geliştiricinin yerel yapılandırmasına göre sonuç değiştirmemeli.
    monkeypatch.setenv("OPS_METRICS_TOKEN", "")
    get_settings.cache_clear()

    response = client.get("/ops/metrics")

    assert response.status_code == 404
    get_settings.cache_clear()


def test_token_gerekli(ops_client: TestClient) -> None:
    response = ops_client.get("/ops/metrics")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_yanlis_token_reddedilir(ops_client: TestClient) -> None:
    response = ops_client.get("/ops/metrics", headers={"Authorization": "Bearer yanlis"})

    assert response.status_code == 401


def test_dogru_token_slo_yargisi_dondurur(ops_client: TestClient) -> None:
    response = ops_client.get("/ops/metrics", headers={"Authorization": f"Bearer {OPS_TOKEN}"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert {verdict["key"] for verdict in body["slos"]} == {
        "api_availability",
        "api_latency_p95",
        "processing_duration_p95",
        "processing_success_rate",
    }
    # Veri yokken sistem "sağlıklı" sayılır; sessizlik ihlal değildir.
    assert body["healthy"] is True
    assert all(verdict["ok"] is None for verdict in body["slos"])


def test_pencere_ust_sinirla_dogrulanir(ops_client: TestClient) -> None:
    response = ops_client.get(
        "/ops/metrics",
        headers={"Authorization": f"Bearer {OPS_TOKEN}"},
        params={"window": 99999},
    )

    assert response.status_code == 422
