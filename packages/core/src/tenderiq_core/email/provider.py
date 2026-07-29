"""E-posta sağlayıcı seam'i: arayüz + logging/memory/Resend implementasyonları.

Sözleşme tek bir soruya indirgenir: *bu mesajı gönder ve sağlayıcının verdiği
kimliği döndür*. Şablon üretimi, bastırma listesi ve tekrar koruması bu katmanın
**dışındadır** (``email.service``) — sağlayıcı değişince o kurallar değişmemeli.

Sağlayıcılar:
- ``logging`` (dev varsayılanı): göndermez, gövdeyi loglar. Geliştirici
  doğrulama/sıfırlama bağlantısını loglardan alır. Production'da yasaktır.
- ``memory``: testler için; gönderilenleri listede tutar.
- ``resend``: gerçek gönderim (HTTP API).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import httpx

from tenderiq_core.config import Settings
from tenderiq_core.email.message import EmailMessage
from tenderiq_core.logging import get_logger, mask_email

logger = get_logger("tenderiq.core.email")

RESEND_API_URL = "https://api.resend.com/emails"
_TIMEOUT_SECONDS = 15.0


class EmailDeliveryError(RuntimeError):
    """Sağlayıcı mesajı kabul etmedi (ağ hatası veya 4xx/5xx)."""


class EmailProvider(Protocol):
    """Bir e-posta sağlayıcısının sözleşmesi."""

    name: str

    async def send(self, message: EmailMessage, *, sender: str) -> str | None:
        """Mesajı gönderir ve sağlayıcı kimliğini döndürür (yoksa ``None``)."""
        ...


class LoggingEmailProvider:
    """Dev sağlayıcısı — göndermez, gövdeyi loglar.

    Gövde bilinçli olarak loglanır: tek-kullanımlık bağlantı geliştiricinin
    tek erişim yoludur. Bu yüzden production'da bu sağlayıcı açılışta reddedilir
    (``config.Settings._enforce_production_hardening``).
    """

    name = "logging"

    async def send(self, message: EmailMessage, *, sender: str) -> str | None:
        logger.info(
            "hesap_epostasi",
            provider=self.name,
            sender=sender,
            kind=message.kind.value,
            to=message.to,
            subject=message.subject,
            body=message.text,
        )
        return None


@dataclass
class MemoryEmailProvider:
    """Test sağlayıcısı — gönderilen mesajları bellekte tutar."""

    name: str = "memory"
    sent: list[EmailMessage] = field(default_factory=list)
    #: Ayarlanırsa her gönderim bu hatayla düşer (hata yolu testleri).
    fail_with: Exception | None = None

    async def send(self, message: EmailMessage, *, sender: str) -> str | None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(message)
        return f"memory-{len(self.sent)}"


class ResendEmailProvider:
    """Resend HTTP API adaptörü.

    Anahtar **asla loglanmaz**: hata kaydına yalnız durum kodu ve sağlayıcının
    mesajı girer, istek başlıkları girmez.
    """

    name = "resend"

    def __init__(self, api_key: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client

    async def send(self, message: EmailMessage, *, sender: str) -> str | None:
        payload = {
            "from": sender,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            if self._client is not None:
                response = await self._client.post(
                    RESEND_API_URL, json=payload, headers=headers, timeout=_TIMEOUT_SECONDS
                )
            else:
                async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                    response = await client.post(RESEND_API_URL, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise EmailDeliveryError(f"Resend'e ulaşılamadı: {type(exc).__name__}") from exc

        if response.status_code >= 400:
            # Gövde sağlayıcının hata açıklamasıdır; anahtar içermez.
            raise EmailDeliveryError(f"Resend {response.status_code}: {response.text[:200]}")
        data = response.json()
        identifier = data.get("id") if isinstance(data, dict) else None
        logger.info(
            "eposta_gonderildi",
            provider=self.name,
            kind=message.kind.value,
            recipient_masked=mask_email(message.to),
            provider_message_id=identifier,
        )
        return str(identifier) if identifier is not None else None


def create_email_provider(settings: Settings) -> EmailProvider:
    """Ayarlardaki sağlayıcıyı üretir; tanınmayan ad açılışta değil, ilk
    gönderimde fark edilmesin diye **burada** reddedilir."""
    provider = settings.email_provider
    if provider == "logging":
        return LoggingEmailProvider()
    if provider == "memory":
        return MemoryEmailProvider()
    if provider == "resend":
        if not settings.resend_api_key:
            raise EmailDeliveryError("EMAIL_PROVIDER=resend için RESEND_API_KEY zorunludur.")
        return ResendEmailProvider(settings.resend_api_key)
    raise EmailDeliveryError(f"Tanınmayan e-posta sağlayıcısı: {provider}")
