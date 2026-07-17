"""Sentry entegrasyonu (C.6): DSN-kapılı init + kiracı bağlamı + PII maskeleme.

- ``init_sentry``: ``SENTRY_DSN`` boşsa tamamen no-op — dev/test kurulumu Sentry
  hesabı gerektirmez. FastAPI/Starlette ve Celery entegrasyonları, ilgili paket
  import edilebilir olduğunda sentry-sdk tarafından otomatik etkinleştirilir.
- **PII maskeleme:** ``send_default_pii=False`` + ``before_send`` scrub'ı —
  istek gövdesi, cookie'ler, hassas başlıklar ve sorgu dizesi hiç gönderilmez;
  kullanıcı bağlamı yalnızca ID taşır. Loglar zaten PII yerine korelasyon
  kimlikleri taşır (tenant_id/job_id/request_id).
- ``bind_sentry_tags``: tenant_id/job_id gibi korelasyon tag'lerini mevcut
  scope'a bağlar; Sentry başlatılmamışsa güvenli no-op (SDK istemcisizken
  ``set_tag`` hiçbir şey göndermez).
"""

from __future__ import annotations

import uuid

import sentry_sdk
from sentry_sdk.types import Event, Hint

from tenderiq_core.config import Settings

# İzin verilen istek başlıkları (küçük harf) — geri kalanı (Authorization,
# Cookie, X-Forwarded-For...) maskelenir.
_SAFE_REQUEST_HEADERS = frozenset(
    {"accept", "content-length", "content-type", "user-agent", "x-request-id"}
)


def init_sentry(settings: Settings) -> bool:
    """Sentry'yi başlatır; DSN yapılandırılmamışsa ``False`` döner (no-op)."""
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment.value,
        send_default_pii=False,
        before_send=scrub_event,
        # Şimdilik yalnızca hata izleme; performans izleme (APM) maliyetiyle
        # birlikte Faz 4 gözden geçirmesinde değerlendirilir.
        traces_sample_rate=0.0,
    )
    return True


def scrub_event(event: Event, _hint: Hint | None = None) -> Event:
    """Sentry olayından PII sızabilecek alanları temizler (before_send)."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("cookies", None)
        request.pop("data", None)  # istek gövdesi (yüklenen içerik/parola) asla gitmez
        request.pop("env", None)
        request.pop("query_string", None)
        url = request.get("url")
        if isinstance(url, str) and "?" in url:
            request["url"] = url.split("?", 1)[0]
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                key: value for key, value in headers.items() if key.lower() in _SAFE_REQUEST_HEADERS
            }
    user = event.get("user")
    if isinstance(user, dict):
        # Yalnızca kimlik korelasyonu kalır; e-posta/IP/kullanıcı adı maskelenir.
        event["user"] = {"id": user["id"]} if "id" in user else {}
    return event


def bind_sentry_tags(**tags: uuid.UUID | str | None) -> None:
    """Korelasyon tag'lerini (tenant_id, job_id, ...) mevcut Sentry scope'una bağlar."""
    for key, value in tags.items():
        if value is not None:
            sentry_sdk.set_tag(key, str(value))
