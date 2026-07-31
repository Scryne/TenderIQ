"""Depolama kotası bildirimleri — yumuşak eşik ve aşım (J.6 madde 3).

Bütçe bildirimlerinin (Tur 14) kardeşi; fark, buradaki yolun **async** olması:
kota kararı API isteğinde verilir, worker'da değil.

Tur 8'in yolunu kullanır (aynı `send_email` seam'i, bastırma + idempotency).
**Dönem başına tek uyarı**: her yüklemede e-posta göndermek, gerçekten önemli
olanın okunmamasına yol açar; şablonların ``idempotency_key``i ay anahtarını
taşır ve `send_email` tekrarı `DUPLICATE` olarak eler.

Bildirim gönderilememesi isteği BOZMAZ: kotanın kendisi zaten uygulanıyor.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.config import Settings, get_settings
from tenderiq_core.email import create_email_provider, send_email, templates
from tenderiq_core.formatting import format_bytes_tr
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Membership, Role, User

logger = get_logger("tenderiq.services.storage_notifications")

__all__ = ["notify_storage_threshold"]


async def _admin_recipients(session: AsyncSession, tenant_id: uuid.UUID) -> list[str]:
    """Kiracının aktif yönetici e-postaları (``Membership`` RLS'siz kimlik tablosu)."""
    rows = await session.scalars(
        select(User.email)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.organization_id == tenant_id,
            Membership.role == Role.ADMIN,
            User.is_active.is_(True),
        )
    )
    return list(rows.all())


async def notify_storage_threshold(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    used_bytes: int,
    limit_bytes: int,
    exceeded: bool,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    """Yöneticilere depolama bildirimi gönderir; gönderilen mesaj sayısını döndürür.

    ``exceeded`` doğruysa "alan doldu" (yükleme reddediliyor), değilse "çoğu
    kullanıldı" uyarısı. İkisi ayrı şablon çünkü kullanıcının yapması gereken
    şey farklı: biri bilgi, diğeri engel.
    """
    settings = settings or get_settings()
    now = now or datetime.now(UTC)
    # Depolama kotası dönemsel DEĞİL (birikimli), ama uyarı tekrarını ay
    # bazında eliyoruz: kullanıcı ayda bir hatırlatılsın, her yüklemede değil.
    period_key = now.strftime("%Y-%m")

    try:
        recipients = await _admin_recipients(session, tenant_id)
    except Exception as exc:  # pragma: no cover - DB hatası
        logger.warning("depolama_bildirimi_alicilari_okunamadi", error=str(exc))
        return 0

    builder = templates.storage_exceeded if exceeded else templates.storage_soft_threshold
    provider = create_email_provider(settings)
    sent = 0
    for address in recipients:
        message = builder(
            to=address,
            used=format_bytes_tr(used_bytes),
            limit=format_bytes_tr(limit_bytes),
            period_key=period_key,
            link=f"{settings.app_base_url}/usage",
        )
        try:
            await send_email(message, provider=provider, settings=settings)
            sent += 1
        except Exception as exc:  # bildirim, kotayı uygulamayı bozmamalı
            logger.warning("depolama_bildirimi_gonderilemedi", error=str(exc), exceeded=exceeded)
    return sent
