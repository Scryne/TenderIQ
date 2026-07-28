"""İstek bağlamı middleware'i: request_id üretimi + loglama bağlamı + SLO ölçümü.

Saf ASGI middleware'dir (BaseHTTPMiddleware değil): BaseHTTPMiddleware,
``http.disconnect`` mesajının iç uygulamaya akışını bozarak SSE gibi uzun ömürlü
stream'lerin istemci kopuşunu görmesini engeller.
"""

from __future__ import annotations

import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tenderiq_core.logging import get_logger, request_id_var
from tenderiq_core.ops import record_api_request

REQUEST_ID_HEADER = "X-Request-ID"

logger = get_logger("tenderiq.api.request")

# Ölçüm dışı yollar: sağlık probu ve operasyon ucunun kendisi. Probe'lar saniyede
# bir gelir ve hepsi hızlıdır — histograma karışsalardı p95'i yapay olarak
# aşağı çeker, yani SLO'yu gerçekte olduğundan iyi gösterirlerdi.
_UNMEASURED_PREFIXES = ("/healthz", "/readyz", "/ops")

# Yavaş istek eşiği: bunu aşan istek yapılandırılmış logda ADIYLA görünür.
# Redis'teki histogram "p95 kaçtı" sorusuna cevap verir ama "hangi uç yavaştı"
# sorusuna veremez (kardinaliteyi bilinçli olarak tutmuyoruz) — runbook'un
# teşhis adımı bu log kaydına dayanır.
_SLOW_REQUEST_MS = 1000.0


def _is_measured(path: str) -> bool:
    return not path.startswith(_UNMEASURED_PREFIXES)


def _route_label(scope: Scope) -> str:
    """Rota şablonu (``/api/v1/tenders/{tender_id}``); eşleşme yoksa ham yol."""
    route = scope.get("route")
    return str(getattr(route, "path", scope.get("path", "")))


class SecurityHeadersMiddleware:
    """API yanıtlarına güvenlik başlıkları ekler (J.1).

    API JSON döndürür, HTML değil — ama başlıklar yine de gerekir: ``nosniff``
    olmadan tarayıcı bir JSON yanıtını içeriğine bakıp HTML sanabilir (yansıyan
    XSS'in klasik yolu), ``X-Frame-Options`` ``/docs`` sayfasını clickjacking'e
    karşı korur ve ``no-store`` kiracı verisinin ara belleklerde kalmasını
    engeller.

    ``Cache-Control`` yalnız yanıt kendi değerini AYARLAMADIYSA yazılır: SSE
    akışı ve indirme yanıtları kendi önbellek sözleşmelerini taşır.
    """

    _HEADERS: tuple[tuple[bytes, bytes], ...] = (
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self._HEADERS:
                    headers[name.decode()] = value.decode()
                if "cache-control" not in headers:
                    headers["cache-control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RequestContextMiddleware:
    """Her istek için ``request_id`` üretir/yayar, log bağlamına bağlar ve süresini ölçer."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        streaming = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, streaming
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                # SSE/akış yanıtları saniyeler-dakikalar sürer ve bu süre
                # sunucunun yavaşlığı değil, sözleşmesidir (J.4: "LLM/akış uçları
                # hariç"). Histograma girse p95'i tek başına havaya uçururdu.
                streaming = headers.get("content-type", "").startswith("text/event-stream")
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            if _is_measured(scope.get("path", "")) and not streaming:
                await self._record(scope, duration_ms, status_code)
            request_id_var.reset(token)

    async def _record(self, scope: Scope, duration_ms: float, status_code: int) -> None:
        """Ölçümü Redis'e yazar ve yavaş isteği loglar (ikisi de hata-toleranslı)."""
        if duration_ms >= _SLOW_REQUEST_MS:
            logger.warning(
                "yavas_istek",
                route=_route_label(scope),
                method=scope.get("method", ""),
                duration_ms=round(duration_ms),
                status_code=status_code,
            )
        redis = getattr(getattr(scope.get("app"), "state", None), "redis", None)
        if redis is not None:
            await record_api_request(redis, duration_ms=duration_ms, status_code=status_code)
