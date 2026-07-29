"""iyzico SANDBOX'ına karşı canlı doğrulama (`-m live_sandbox`).

Varsayılan koşumdan HARİÇTİR ve anahtar yoksa atlanır: hiçbir otomatik test dış
servise çıkmamalı. Amacı, adaptörün dokümantasyondan yazılan varsayımlarını
gerçek API'yle karşılaştırmak.

    uv run pytest -m live_sandbox

**Yalnız sandbox.** `BILLING_ENV=live` iken testler atlanır — canlı ortama
çağrı bir durma koşuludur.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

from tenderiq_core.billing.iyzico import SANDBOX_BASE_URL, build_authorization
from tenderiq_core.config import get_settings

_settings = get_settings()
_HAS_KEYS = bool(_settings.iyzico_api_key and _settings.iyzico_secret_key)

pytestmark = [
    pytest.mark.live_sandbox,
    pytest.mark.skipif(not _HAS_KEYS, reason="IYZICO_* anahtarları yok"),
    pytest.mark.skipif(_settings.billing_is_live, reason="Yalnız sandbox'a çağrı yapılır"),
]


async def _post(path: str, body: dict[str, object], *, secret: str | None = None) -> httpx.Response:
    payload = json.dumps(body, separators=(",", ":"))
    random_key = uuid.uuid4().hex[:24]
    auth = build_authorization(
        api_key=_settings.iyzico_api_key or "",
        secret_key=secret or (_settings.iyzico_secret_key or ""),
        uri_path=path,
        payload=payload,
        random_key=random_key,
    )
    async with httpx.AsyncClient(timeout=30) as client:
        return await client.post(
            f"{SANDBOX_BASE_URL}{path}",
            content=payload,
            headers={
                "Authorization": auth,
                "x-iyzi-rnd": random_key,
                "content-type": "application/json",
            },
        )


_BIN_CHECK = "/payment/bin/check"
_BIN_BODY: dict[str, object] = {"locale": "tr", "conversationId": "t", "binNumber": "554960"}


async def test_imza_semasi_gercek_apide_gecerli() -> None:
    """`randomKey + uriPath + payload` üzerinden HMAC-SHA256 — gerçekle doğrulanır."""
    response = await _post(_BIN_CHECK, _BIN_BODY)

    assert response.json()["status"] == "success"


async def test_yanlis_sir_reddedilir() -> None:
    """İmzanın gerçekten doğrulandığının kanıtı (aksi hâlde yukarıdaki test boş geçerdi)."""
    response = await _post(_BIN_CHECK, _BIN_BODY, secret="yanlis-gizli-anahtar")

    assert response.json()["status"] == "failure"


async def test_gecersiz_imza_http_200_ile_gelebilir() -> None:
    """En önemli bulgu: başarı kontrolü HTTP durumuna GÜVENEMEZ.

    `/payment/bin/check` geçersiz imzada **HTTP 200** döndürüp gövdede
    `"Geçersiz imza"` diyor. Yalnız HTTP durumuna bakan bir adaptör bunu
    başarı sayardı.
    """
    response = await _post(_BIN_CHECK, _BIN_BODY, secret="yanlis-gizli-anahtar")

    assert response.status_code == 200
    assert response.json()["status"] == "failure"


async def test_abonelik_modulunun_durumu_raporlanir() -> None:
    """Abonelik uçları çalışıyor mu — çalışmıyorsa neden çalışmadığını sabitler.

    Bu test bir "geçmeli" iddia DEĞİL, bir durum tespitidir: modül etkinleşince
    kırılır ve bizi adaptörün şemasını gerçeğe göre doğrulamaya çağırır.
    """
    response = await _post("/v2/subscription/products", {"locale": "tr", "conversationId": "t"})
    body = response.json()

    if body.get("status") == "success":
        pytest.fail(
            "Abonelik modülü artık ETKİN — adaptörün istek/yanıt şeması gerçek "
            "yanıta göre doğrulanmalı (bkz. docs/ops/billing-setup.md)."
        )
    assert body.get("errorCode") == "100001"
