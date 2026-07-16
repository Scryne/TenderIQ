"""İstemci IP çözümü birim testleri — X-Forwarded-For / trusted-proxy davranışı.

Oran sınırlama gerçek istemci IP'sini görmelidir: web istekleri her zaman Next
proxy'sinden geldiği için XFF'e yalnızca ``TRUSTED_PROXY_COUNT`` > 0 iken ve
yalnızca listenin SONDAN (güvenilir altyapının eklediği) girdilerine güvenilir.
"""

from __future__ import annotations

from starlette.requests import Request

from tenderiq_api.routers.v1.auth import _client_ip


def _request(headers: dict[str, str] | None = None, client_host: str = "10.0.0.5") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": [
            (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
        ],
        "client": (client_host, 40000),
        "query_string": b"",
    }
    return Request(scope)


def test_xff_yoksa_soket_ipsi() -> None:
    assert _client_ip(_request(), trusted_proxy_count=1) == "10.0.0.5"


def test_guvenilir_proxy_sifirsa_xff_yok_sayilir() -> None:
    """Varsayılan (0): istemcinin gönderdiği sahte XFF başlığına asla güvenilmez."""
    request = _request({"x-forwarded-for": "6.6.6.6"})
    assert _client_ip(request, trusted_proxy_count=0) == "10.0.0.5"


def test_tek_proxy_tek_girdi() -> None:
    request = _request({"x-forwarded-for": "203.0.113.7"})
    assert _client_ip(request, trusted_proxy_count=1) == "203.0.113.7"


def test_sahte_one_ek_guvenilir_girdiyi_ezemez() -> None:
    """İstemci kendi XFF'ini gönderse bile güvenilir proxy'nin eklediği girdi kazanır."""
    request = _request({"x-forwarded-for": "6.6.6.6, 203.0.113.7"})
    assert _client_ip(request, trusted_proxy_count=1) == "203.0.113.7"


def test_proxy_sayisi_girdi_sayisini_asarsa_ilk_girdi() -> None:
    request = _request({"x-forwarded-for": "203.0.113.7"})
    assert _client_ip(request, trusted_proxy_count=2) == "203.0.113.7"


def test_bos_xff_soket_ipsine_duser() -> None:
    request = _request({"x-forwarded-for": "  "})
    assert _client_ip(request, trusted_proxy_count=1) == "10.0.0.5"
