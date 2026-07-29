"""Ölü mektup kuyruğu servisi — uygulanamayan webhook olaylarını saklar.

**Ayrımın tamamı şu soruda:** bu olay yeniden denenirse düzelir mi?

* **Kalıcı** (``PERMANENT``) — düzelmez. Tanınmayan kiracı, eşlenmemiş abonelik
  durumu, ayrıştırılamayan gövde, geçersiz imza. Sağlayıcıyı yeniden denemeye
  çağırmak (5xx) sadece gürültü üretir; kalıcı bir reddetme (4xx) doğru
  cevaptır ve olay kuyruğa **doğrudan** yazılır.
* **Geçici** (``TRANSIENT``) — düzelebilir. Veritabanı/Redis kesintisi, kilit
  çakışması. Sağlayıcının kendi yeniden denemesi bunu çözer, o yüzden 5xx
  döneriz — ama **sınırsız değil**: ``MAX_TRANSIENT_ATTEMPTS``ten sonra 200
  döneriz. Gerekçe: sağlayıcının yeniden deneme fırtınası bizi ayağa kaldırmaz,
  yalnız log'u boğar ve gerçek arızayı görünmez kılar. O noktadan sonra olay
  kuyrukta insanı bekler.

Kuyruk satırı **olay başına tektir** (``provider`` + ``event_id`` tekil): aynı
olayın on teslimi tek satırın ``attempts``ını artırır. Aksi hâlde kuyruk aynı
arızanın kopyalarıyla dolar ve "kaç olay bekliyor" sorusu anlamını yitirir.

Bekleyen satırların sayısı ayrıca **Redis'te bir kümede** tutulur (metrik).
Küme, sayaç değil: aynı kimliği iki kez eklemek sayıyı şişirmez ve kaçırılan bir
silme yalnızca YUKARI yönde hata üretir — "kuyrukta iş var" derken boş olması,
"boş" derken iş olmasından iyidir.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.logging import get_logger
from tenderiq_core.models import DeadLetterKind, DeadLetterStatus, WebhookDeadLetter
from tenderiq_core.redaction import redact_raw_body

logger = get_logger("tenderiq.core.dead_letter")

#: Geçici hatada sağlayıcıya kaç kez "yeniden dene" (5xx) denir. Aşıldığında
#: 200 döner ve olay kuyrukta insanı bekler.
MAX_TRANSIENT_ATTEMPTS = 5

#: Bekleyen kuyruk kimliklerinin Redis kümesi (yalnız metrik).
PENDING_SET_KEY = "billing:dlq:pending"

#: İmzası GEÇERSİZ olaylardan kuyrukta tutulacak azami satır. Webhook ucu
#: kimliksizdir: imzasız gövdeleri sınırsız saklamak, herkese açık bir yazma
#: yüzeyi sunmak demektir. Tavan, imza biçimi teşhisi için yeterince örnek
#: bırakır ama depolamayı şişirmeye izin vermez.
MAX_UNSIGNED_ROWS = 100


class DeadLetterError(Exception):
    """Olay uygulanamadı ve kuyruğa alınmalı.

    ``kind`` yanıtın ne olacağını belirler (kalıcı ⇒ 4xx, geçici ⇒ 5xx);
    ``reason`` operatöre gösterilecek kullanıcı-okur sebeptir.
    """

    def __init__(self, reason: str, *, kind: DeadLetterKind) -> None:
        super().__init__(reason)
        self.reason = reason
        self.kind = kind


class PermanentEventError(DeadLetterError):
    """Yeniden deneme bu olayı ASLA düzeltmez."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason, kind=DeadLetterKind.PERMANENT)


class TransientEventError(DeadLetterError):
    """Yeniden deneme bu olayı düzeltebilir."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason, kind=DeadLetterKind.TRANSIENT)


async def _mark_pending(redis: Redis | None, dead_letter_id: uuid.UUID) -> None:
    if redis is None:
        return
    try:
        await redis.sadd(PENDING_SET_KEY, str(dead_letter_id))  # type: ignore[misc]
    except RedisError as exc:
        # Metrik bir kolaylıktır; kuyruğa yazmayı düşürmez.
        logger.warning("dlq_metrik_yazilamadi", error=str(exc))


async def _clear_pending(redis: Redis | None, dead_letter_id: uuid.UUID) -> None:
    if redis is None:
        return
    try:
        await redis.srem(PENDING_SET_KEY, str(dead_letter_id))  # type: ignore[misc]
    except RedisError as exc:
        logger.warning("dlq_metrik_temizlenemedi", error=str(exc))


async def pending_count(redis: Redis) -> int | None:
    """Bekleyen kuyruk boyutu (operatör metriği); ölçülemezse ``None``.

    Ölçülemediğinde **sıfır dönmez**. Sıfır "kuyruk boş" demektir ve bir panoda
    yeşil görünür; oysa gerçekte kuyrukta bekleyen ödemeler olabilir ve biz
    yalnızca sayamıyoruzdur. "Bilmiyorum" demek, yanlışlıkla "her şey yolunda"
    demekten iyidir — metriğin tek işi zaten insanı uyandırmak.
    """
    try:
        return int(await redis.scard(PENDING_SET_KEY))  # type: ignore[misc]
    except (RedisError, AttributeError, TypeError) as exc:
        # AttributeError/TypeError: Redis devre dışı bırakılmış kurulumlarda
        # yerine geçen boş nesne bu komutu tanımayabilir. Metrik yüzünden ops
        # ucunun 500 vermesi, ölçmeye çalıştığı arızadan daha büyük bir arızadır.
        logger.warning("dlq_metrik_okunamadi", error=str(exc))
        return None


async def _unsigned_row_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count(WebhookDeadLetter.id)).where(
                WebhookDeadLetter.signature_valid.is_(False),
                WebhookDeadLetter.status == DeadLetterStatus.PENDING,
            )
        )
        or 0
    )


async def enqueue(
    session: AsyncSession,
    *,
    provider: str,
    event_id: str,
    event_type: str,
    tenant_id: uuid.UUID | None,
    signature_valid: bool,
    kind: DeadLetterKind,
    error: str,
    raw_body: bytes,
    redis: Redis | None = None,
    now: datetime | None = None,
) -> WebhookDeadLetter | None:
    """Olayı kuyruğa yazar (aynı olay tekrar gelirse ``attempts`` artar).

    ``None`` döner: yalnızca imzasız olay tavanı dolduğunda (bkz.
    ``MAX_UNSIGNED_ROWS``). Kiracı bağlamı GEREKMEZ — bu yolun tamamı
    kimliksizdir ve kiracısı bilinmeyen olayları da yazabilmelidir.

    Gövde **redakte edilerek** saklanır: sağlayıcı gövdesini olduğu gibi
    saklamak, "kart verisi bize gelmez" varsayımı yanlışsa PCI kapsamına
    girmektir.
    """
    now = now or datetime.now(UTC)

    if not signature_valid and await _unsigned_row_count(session) >= MAX_UNSIGNED_ROWS:
        # Uç kimliksizdir: imzasız gövdeleri sınırsız saklamak herkese açık bir
        # yazma yüzeyi sunmak olur. Tavana ulaşıldıysa yalnız loglanır.
        logger.warning("dlq_imzasiz_tavan_doldu", provider=provider, event_type=event_type)
        return None

    payload, raw_text = redact_raw_body(raw_body)
    values: dict[str, Any] = {
        "tenant_id": tenant_id,
        "provider": provider,
        "event_id": event_id,
        "event_type": event_type,
        "signature_valid": signature_valid,
        "kind": kind,
        "status": DeadLetterStatus.PENDING,
        "error": error,
        "attempts": 1,
        "payload": payload,
        "raw_body_text": raw_text,
        "last_attempt_at": now,
    }
    # Tek deyimde upsert: önce SELECT edip sonra INSERT etmek, aynı olayın iki
    # eşzamanlı teslimi arasında yarışa açıktır ve tekil kısıt ihlaliyle patlar.
    statement = (
        pg_insert(WebhookDeadLetter)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_webhook_dead_letter_event",
            set_={
                "attempts": WebhookDeadLetter.__table__.c.attempts + 1,
                "last_attempt_at": now,
                "error": error,
                "kind": kind,
                # Daha önce çözülmüş bir olay yeniden başarısız oluyorsa tekrar
                # bekleyene döner: "çözüldü" damgası gerçeği yansıtmalı.
                "status": DeadLetterStatus.PENDING,
                "resolved_at": None,
            },
        )
        .returning(WebhookDeadLetter.id)
    )
    dead_letter_id = await session.scalar(statement)
    assert dead_letter_id is not None  # noqa: S101 - RETURNING her zaman satır verir
    await _mark_pending(redis, dead_letter_id)
    logger.warning(
        "webhook_olayi_kuyruga_alindi",
        provider=provider,
        event_type=event_type,
        kind=kind.value,
        signature_valid=signature_valid,
        tenant_id=str(tenant_id) if tenant_id else None,
    )
    return await session.get(WebhookDeadLetter, dead_letter_id)


async def resolve_for_event(
    session: AsyncSession,
    *,
    provider: str,
    event_id: str,
    redis: Redis | None = None,
    now: datetime | None = None,
) -> None:
    """Bir olay SONUNDA uygulanabildiyse kuyruktaki satırını çözer.

    Geçici hatada sağlayıcı yeniden dener ve genelde başarılı olur; kuyrukta
    kalan satır o zaman yanlış bilgidir. Kiracı bağlamı gerekmez (servis
    politikası UPDATE'e izin verir).
    """
    row = await session.scalar(
        select(WebhookDeadLetter).where(
            WebhookDeadLetter.provider == provider,
            WebhookDeadLetter.event_id == event_id,
            WebhookDeadLetter.status == DeadLetterStatus.PENDING,
        )
    )
    if row is None:
        return
    row.status = DeadLetterStatus.RESOLVED
    row.resolved_at = now or datetime.now(UTC)
    await _clear_pending(redis, row.id)
    logger.info("dlq_kaydi_cozuldu", provider=provider, event_type=row.event_type)


async def list_for_tenant(
    session: AsyncSession,
    *,
    status: DeadLetterStatus | None = None,
    limit: int = 50,
) -> Sequence[WebhookDeadLetter]:
    """Kiracının kuyruk kayıtları (RLS kiracıyı zaten sınırlar).

    Kiracı bağlamı ayarlı bir oturumda çağrılmalıdır; aksi hâlde SELECT
    politikası hiçbir satır döndürmez (ve bu doğru davranıştır).
    """
    query = select(WebhookDeadLetter).order_by(WebhookDeadLetter.last_attempt_at.desc())
    if status is not None:
        query = query.where(WebhookDeadLetter.status == status)
    return (await session.scalars(query.limit(limit))).all()


async def mark_resolved(
    session: AsyncSession,
    row: WebhookDeadLetter,
    *,
    redis: Redis | None = None,
    now: datetime | None = None,
) -> None:
    """Tek bir satırı çözülmüş işaretler (yeniden işleme başarılı oldu)."""
    row.status = DeadLetterStatus.RESOLVED
    row.resolved_at = now or datetime.now(UTC)
    await _clear_pending(redis, row.id)
