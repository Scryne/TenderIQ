"""Bütçe bildirimleri — yumuşak eşik ve tavan (J.6 madde 2).

Worker senkron koştuğu için burada senkron bir yol var; e-posta gönderimi
Tur 8'in yolunu (aynı `send_email` seam'i, bastırma + idempotency) kullanır.

**Dönem başına tek uyarı.** Eşik aşıldıktan sonra her iş için e-posta göndermek
gerçekten önemli olanın okunmamasına yol açar; şablonların
``idempotency_key``i dönem anahtarını taşıyor ve `send_email` tekrarını
`DUPLICATE` olarak eler.

Bildirim gönderilememesi işi BOZMAZ: tavanın kendisi zaten uygulanıyor, e-posta
yalnız kullanıcıya haber vermek için. Sessiz kalmamak adına hata loglanır.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tenderiq_core.config import Settings, get_settings
from tenderiq_core.email import EmailMessage, create_email_provider, send_email, templates
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Membership, Role, User

logger = get_logger("tenderiq.services.budget_notifications")


def admin_recipients_sync(session: Session, tenant_id: uuid.UUID) -> list[str]:
    """Kiracının aktif yönetici e-postaları (``Membership`` RLS'siz kimlik tablosu)."""
    rows = session.scalars(
        select(User.email)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.organization_id == tenant_id,
            Membership.role == Role.ADMIN,
            User.is_active.is_(True),
        )
    )
    return list(rows.all())


def _billing_link(settings: Settings) -> str:
    return f"{settings.app_base_url}/usage"


def _send(message: EmailMessage, settings: Settings) -> None:
    """Senkron sarmal: worker'da event loop yok."""

    async def _run() -> None:
        provider = create_email_provider(settings)
        await send_email(message, provider=provider, settings=settings)

    asyncio.run(_run())


def notify_budget_threshold(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    spent_micros: int,
    limit_micros: int,
    period_end: datetime,
    period_key: str,
    exceeded: bool,
    settings: Settings | None = None,
) -> int:
    """Yöneticilere bütçe bildirimi gönderir; gönderilen mesaj sayısını döndürür.

    ``exceeded`` doğruysa "bütçe doldu" (yeni analiz reddediliyor), değilse
    "çoğu kullanıldı" uyarısı. İkisi ayrı şablon çünkü kullanıcının yapması
    gereken şey farklı: biri bilgi, diğeri engel.
    """
    settings = settings or get_settings()
    micros = 1_000_000
    try:
        recipients = admin_recipients_sync(session, tenant_id)
    except Exception as exc:  # pragma: no cover - DB hatası
        logger.warning("butce_bildirimi_alicilari_okunamadi", error=str(exc))
        return 0

    builder = templates.budget_exceeded if exceeded else templates.budget_soft_threshold
    sent = 0
    for address in recipients:
        message = builder(
            to=address,
            spent_try=spent_micros / micros,
            limit_try=limit_micros / micros,
            reset_date=period_end.strftime("%d.%m.%Y"),
            period_key=period_key,
            link=_billing_link(settings),
        )
        try:
            _send(message, settings)
            sent += 1
        except Exception as exc:  # bildirim, tavanı uygulamayı bozmamalı
            logger.warning("butce_bildirimi_gonderilemedi", error=str(exc), exceeded=exceeded)
    return sent
