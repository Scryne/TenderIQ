"""/api/v1/email/webhook — sağlayıcı bounce/şikâyet bildirimleri.

Kalıcı bounce alan bir adrese göndermeye devam etmek gönderen alan adının
itibarını düşürür ve bir süre sonra **meşru** e-postalar da spam'e düşer. Bu uç,
o adresleri bastırma listesine alarak teslimat oranını korur.

Güvenlik: imza doğrulanmadan hiçbir şey yapılmaz ve sır yapılandırılmamışsa uç
**404** döner — kapalı bir kurulumda varlığı bile sızmaz (ops ucuyla aynı kalıp).
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from tenderiq_api.dependencies import SessionDep, SettingsDep
from tenderiq_api.errors import NotFoundError, UnauthorizedError
from tenderiq_core.logging import get_logger, mask_email
from tenderiq_core.models import EmailSuppression, SuppressionReason
from tenderiq_core.services.auth import normalize_email

logger = get_logger("tenderiq.api.email")

router = APIRouter(prefix="/email", tags=["email"], include_in_schema=False)

SIGNATURE_HEADER = "x-tenderiq-email-signature"

#: Sağlayıcı olay adı → bastırma sebebi. Listede olmayan olay (ör. `email.sent`,
#: `email.delivered`) sessizce yok sayılır: webhook'a abone olmak ucuz, her olayı
#: işlemek gereksizdir.
_SUPPRESSING_EVENTS: dict[str, SuppressionReason] = {
    "email.bounced": SuppressionReason.HARD_BOUNCE,
    "email.complained": SuppressionReason.COMPLAINT,
}

#: Yumuşak bounce (kutu dolu, geçici hata) bastırılmaz — adres geçerlidir.
_SOFT_BOUNCE_TYPES = frozenset({"soft", "transient", "temporary"})


def _verify(secret: str | None, headers: dict[str, str], raw_body: bytes) -> None:
    """HMAC-SHA256 imzasını sabit zamanlı doğrular; sır yoksa uç yok sayılır."""
    if not secret:
        raise NotFoundError("Bulunamadı.")
    provided = headers.get(SIGNATURE_HEADER, "")
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided, expected):
        raise UnauthorizedError("Webhook imzası geçersiz.")


def _recipient(data: dict[str, Any]) -> str | None:
    """Olay gövdesinden alıcıyı çıkarır (``to`` liste veya string olabilir)."""
    to = data.get("to")
    if isinstance(to, list) and to:
        return str(to[0])
    if isinstance(to, str):
        return to
    return None


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def email_webhook(request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    """Bounce/şikâyet olaylarını işler ve adresi bastırma listesine alır."""
    raw_body = await request.body()
    _verify(settings.resend_webhook_secret, dict(request.headers), raw_body)

    payload = await request.json()
    if not isinstance(payload, dict):
        # Gövde bozuksa 4xx döndürmek sağlayıcıyı sonsuz yeniden denemeye sokar;
        # olay zaten işlenemez, sessizce kabul edilir.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    event_type = str(payload.get("type", ""))
    reason = _SUPPRESSING_EVENTS.get(event_type)
    if reason is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    data = payload.get("data")
    data = data if isinstance(data, dict) else {}
    if reason is SuppressionReason.HARD_BOUNCE:
        bounce_type = str(data.get("bounce_type", "")).lower()
        if bounce_type in _SOFT_BOUNCE_TYPES:
            # Kutu dolu / geçici hata: adres geçerlidir, bastırmak kullanıcıyı
            # kalıcı olarak iletişim dışına atardı.
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    recipient = _recipient(data)
    if recipient is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    email = normalize_email(recipient)
    async with session.begin():
        existing = await session.scalar(
            select(EmailSuppression).where(EmailSuppression.email == email)
        )
        if existing is None:
            session.add(
                EmailSuppression(
                    email=email,
                    reason=reason,
                    provider_event_id=str(payload.get("id")) if payload.get("id") else None,
                    detail=event_type,
                )
            )
    logger.info(
        "eposta_bastirma_kaydi",
        event_type=event_type,
        reason=reason.value,
        recipient_masked=mask_email(email),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
