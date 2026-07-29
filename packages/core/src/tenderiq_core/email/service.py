"""E-posta gönderim servisi: bastırma + tekrar koruması + gönderim.

Bu katman sağlayıcıdan bağımsız **kuralları** uygular; sağlayıcı yalnız taşır.

Üç kural:

1. **Bastırma.** Kalıcı bounce/şikâyet almış adrese gönderilmez — aksi hâlde
   gönderen alan adının itibarı düşer ve meşru e-postalar da spam'e düşer.
   İstisna: ``SUPPRESSION_BYPASS_KINDS`` (doğrulama, parola sıfırlama).
   Kullanıcıyı hesabından kalıcı kilitlemek bir bounce kaydından ağırdır.
2. **Tekrar koruması.** ``idempotency_key`` verilmişse aynı olay iki kez
   e-posta üretmez. Webhook'lar mükerrer teslim eder; kullanıcı aynı ödeme için
   iki "ödemeniz alındı" almamalıdır.
3. **Gönderim çağıranı düşürmez.** Sağlayıcı hatası loglanır; kayıt/davet gibi
   akışlar e-postaya bağlı değildir (kullanıcı yeniden gönderim isteyebilir).
   Çağıran isterse ``raise_on_error=True`` ile bu davranışı kapatır.
"""

from __future__ import annotations

from enum import StrEnum

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.config import Settings
from tenderiq_core.email.message import SUPPRESSION_BYPASS_KINDS, EmailMessage
from tenderiq_core.email.provider import EmailDeliveryError, EmailProvider
from tenderiq_core.logging import get_logger, mask_email
from tenderiq_core.models import EmailSuppression
from tenderiq_core.services.auth import normalize_email

logger = get_logger("tenderiq.core.email")

#: Tekrar koruması anahtarının yaşam süresi. Webhook mükerrer teslimleri
#: dakikalar içinde gelir; 7 gün fazlasıyla güvenli bir tavandır.
_IDEMPOTENCY_TTL_SECONDS = 7 * 86_400


class EmailOutcome(StrEnum):
    """Gönderim sonucu — çağıran akış buna göre karar verebilir."""

    SENT = "sent"
    #: Adres bastırma listesinde.
    SUPPRESSED = "suppressed"
    #: Aynı olay için daha önce gönderilmiş.
    DUPLICATE = "duplicate"
    #: Sağlayıcı kabul etmedi (loglandı).
    FAILED = "failed"


async def is_suppressed(session: AsyncSession, email: str) -> bool:
    """Adres bastırma listesinde mi."""
    found = await session.scalar(
        select(EmailSuppression.id).where(EmailSuppression.email == normalize_email(email))
    )
    return found is not None


async def _claim_idempotency(redis: Redis, key: str) -> bool:
    """Anahtarı ilk kez talep ediyorsak ``True``.

    Redis erişilemezse **gönderime izin verilir**: tekrar koruması bir
    kolaylıktır, e-postanın hiç gitmemesi ise gerçek bir arızadır.
    """
    try:
        claimed = await redis.set(f"email:sent:{key}", "1", nx=True, ex=_IDEMPOTENCY_TTL_SECONDS)
    except RedisError as exc:
        logger.warning("eposta_tekrar_korumasi_atlandi", error=str(exc))
        return True
    return bool(claimed)


async def send_email(
    message: EmailMessage,
    *,
    provider: EmailProvider,
    settings: Settings,
    session: AsyncSession | None = None,
    redis: Redis | None = None,
    raise_on_error: bool = False,
) -> EmailOutcome:
    """Kuralları uygulayarak mesajı gönderir; sonucu (``SENT``/…) döndürür."""
    bypasses = message.kind in SUPPRESSION_BYPASS_KINDS
    if session is not None and not bypasses and await is_suppressed(session, message.to):
        logger.info(
            "eposta_bastirildi",
            kind=message.kind.value,
            recipient_masked=mask_email(message.to),
        )
        return EmailOutcome.SUPPRESSED

    key = message.idempotency_key
    if redis is not None and key is not None and not await _claim_idempotency(redis, key):
        logger.info("eposta_mukerrer_atlandi", kind=message.kind.value, idempotency_key=key)
        return EmailOutcome.DUPLICATE

    try:
        await provider.send(message, sender=settings.email_from)
    except EmailDeliveryError as exc:
        logger.warning(
            "eposta_gonderilemedi",
            kind=message.kind.value,
            recipient_masked=mask_email(message.to),
            error=str(exc),
        )
        if raise_on_error:
            raise
        return EmailOutcome.FAILED
    return EmailOutcome.SENT
