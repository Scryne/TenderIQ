"""İşlemsel e-posta: mesaj modeli, Türkçe şablonlar, sağlayıcı seam'i, servis."""

from tenderiq_core.email.message import EmailKind, EmailMessage
from tenderiq_core.email.provider import (
    EmailDeliveryError,
    EmailProvider,
    LoggingEmailProvider,
    MemoryEmailProvider,
    ResendEmailProvider,
    create_email_provider,
)
from tenderiq_core.email.service import EmailOutcome, is_suppressed, send_email

__all__ = [
    "EmailDeliveryError",
    "EmailKind",
    "EmailMessage",
    "EmailOutcome",
    "EmailProvider",
    "LoggingEmailProvider",
    "MemoryEmailProvider",
    "ResendEmailProvider",
    "create_email_provider",
    "is_suppressed",
    "send_email",
]
