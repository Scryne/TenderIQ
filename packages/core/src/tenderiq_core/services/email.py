"""İşlemsel e-posta gönderim seam'i (3.3-D).

Sağlayıcıdan bağımsız tek giriş noktası: ``send_account_email``. Varsayılan
``logging`` sağlayıcısı (dev) e-postayı GERÇEKTEN göndermez; konu + gövdeyi
(doğrulama/sıfırlama bağlantısı dâhil) yapılandırılmış logla yazar — geliştirici
bağlantıyı loglardan alır. Gerçek sağlayıcı (Resend/Postmark/SES) prod'da bu
fonksiyona eklenir; token/bağlantı üretimi sağlayıcıdan bağımsızdır.
"""

from __future__ import annotations

from tenderiq_core.config import Settings
from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.core.email")


async def send_account_email(settings: Settings, *, to: str, subject: str, body: str) -> None:
    """Bir hesap e-postası gönderir (sağlayıcıya göre yönlendirir).

    ``logging`` (dev): gönderim yapılmaz, içerik loglanır. Bilinmeyen/gerçek
    sağlayıcı henüz bağlanmadıysa uyarı loglanır ve içerik yine loglanır (akış
    kırılmaz; bağlantı yakalanabilir).
    """
    if settings.email_provider != "logging":
        logger.warning(
            "email_saglayici_baglanmadi",
            provider=settings.email_provider,
            to=to,
            subject=subject,
        )
    logger.info(
        "hesap_epostasi",
        provider=settings.email_provider,
        sender=settings.email_from,
        to=to,
        subject=subject,
        body=body,
    )
