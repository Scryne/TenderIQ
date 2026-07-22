"""E-posta gönderim seam'i birim testleri (DB/Redis gerektirmez)."""

from __future__ import annotations

from tenderiq_core.config import Settings
from tenderiq_core.services.email import send_account_email


async def test_logging_saglayici_hata_vermez() -> None:
    """Varsayılan ``logging`` sağlayıcısı gönderim yapmaz, içeriği loglar (raise etmez)."""
    settings = Settings(email_provider="logging", email_from="no-reply@test.local")
    await send_account_email(settings, to="a@b.c", subject="Konu", body="Bağlantı: http://x/y")


async def test_bilinmeyen_saglayici_da_calisir() -> None:
    """Gerçek sağlayıcı henüz bağlanmadıysa akış kırılmaz (uyarı + içerik loglanır)."""
    settings = Settings(email_provider="resend", email_from="no-reply@test.local")
    await send_account_email(settings, to="a@b.c", subject="Konu", body="Gövde")
