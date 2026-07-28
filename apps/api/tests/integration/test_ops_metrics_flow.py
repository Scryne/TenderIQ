"""Ops metrik zinciri uçtan uca: middleware → GERÇEK Redis → /ops/metrics.

Birim testleri bu zinciri sahte istemcilerle sınar; burada asıl doğrulanan şey
kovaların gerçek Redis'te beklenen adlarla oluştuğu ve okuma tarafının onları
bulduğudur — yazan ile okuyan arasındaki anahtar sözleşmesi sessizce kayabilir.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tenderiq_core.config import get_settings

pytestmark = pytest.mark.integration

OPS_TOKEN = "entegrasyon-ops-token-0123456789"


@pytest.fixture
def ops_client(api_client: TestClient) -> Iterator[TestClient]:
    """Ops ucu açık, metrikleri GERÇEK Redis'e yazan istemci."""
    os.environ["OPS_METRICS_TOKEN"] = OPS_TOKEN
    get_settings.cache_clear()
    yield api_client
    os.environ.pop("OPS_METRICS_TOKEN", None)
    get_settings.cache_clear()


def _metrics(client: TestClient, **params: int) -> dict:
    response = client.get(
        "/ops/metrics",
        headers={"Authorization": f"Bearer {OPS_TOKEN}"},
        params=params,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_istekler_gercek_redis_uzerinden_panoya_yansir(ops_client: TestClient) -> None:
    baseline = _metrics(ops_client)["api"]["requests"]

    for _ in range(5):
        ops_client.get("/api/v1/system/version")
    # Kimliksiz istek 401 üretir: hata sınıfı sayacı da gerçek yolda doğrulanır.
    ops_client.get("/api/v1/tenders")

    body = _metrics(ops_client)
    assert body["api"]["requests"] >= baseline + 6
    assert body["api"]["client_errors"] >= 1
    assert body["api"]["p95_ms"] is not None
    # 4xx bir sunucu hatası DEĞİLDİR: erişilebilirliği düşürmemeli.
    assert body["api"]["server_errors"] == 0
    assert body["api"]["availability"] == 1.0


def test_probe_ve_ops_istekleri_olculmez(ops_client: TestClient) -> None:
    """Saniyede bir gelen ve daima hızlı olan istekler p95'i yapay olarak iyileştirirdi."""
    before = _metrics(ops_client)["api"]["requests"]

    for _ in range(10):
        ops_client.get("/healthz")
        _metrics(ops_client)

    assert _metrics(ops_client)["api"]["requests"] == before


def test_slo_yargisi_ve_kuyruk_derinligi_dondurulur(ops_client: TestClient) -> None:
    ops_client.get("/api/v1/system/version")

    body = _metrics(ops_client, window=5)

    assert body["window_minutes"] == 5
    assert body["queue_depth"] >= 0
    verdicts = {verdict["key"]: verdict for verdict in body["slos"]}
    # Hızlı ve hatasız istekler → gecikme/erişilebilirlik SLO'ları tutmalı.
    assert verdicts["api_latency_p95"]["ok"] is True
    assert verdicts["api_availability"]["ok"] is True
    # İş üretilmediği için işleme SLO'ları ölçülemez; bu ihlal DEĞİLDİR.
    assert verdicts["processing_duration_p95"]["ok"] is None
    assert body["healthy"] is True
