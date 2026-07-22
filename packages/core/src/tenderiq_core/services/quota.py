"""Kota servisi — abonelik + dönemsel kullanım sayımı ve enforcement (Sprint 3.3).

Kota dönemi takvim ayıdır (UTC): her ayın 1'inde kullanım sıfırlanır. Sayım
``UsageRecord`` satırları üzerinden yapılır (dönem içindeki satır sayısı =
kullanılan doküman; ``pages`` toplamı = kullanılan sayfa). Tüm sorgular RLS'ye
tabidir; kiracı bağlamı ayarlı bir oturumda çağrılmalıdır.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from tenderiq_core.billing.plans import DEFAULT_PLAN_TIER, Plan, get_plan
from tenderiq_core.models import Subscription, SubscriptionStatus, UsageRecord

# Kota boyutunun kullanıcıya-okur Türkçe etiketi (mesajlar için; anahtar İngilizce).
LIMIT_LABELS_TR: dict[str, str] = {"documents": "doküman", "pages": "sayfa"}


def current_period_bounds(now: datetime) -> tuple[datetime, datetime]:
    """İçinde bulunulan takvim ayının ``[başlangıç, bitiş)`` sınırları (UTC).

    Kullanım bu yarı-açık aralıkta ``recorded_at`` taşıyan satırlardan sayılır.
    Ödeme entegrasyonu (3.3-B) ileride sağlayıcı dönemine geçebilir.
    """
    now = now.astimezone(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


@dataclass(frozen=True)
class UsageSnapshot:
    """Kiracının bir dönemdeki kullanımı + plan limitleri."""

    plan: Plan
    status: SubscriptionStatus
    documents_used: int
    pages_used: int
    period_start: datetime
    period_end: datetime


class QuotaExceededError(Exception):
    """Kota aşıldı: yeni doküman işleme reddedilmeli.

    ``limit_kind`` ``"documents"`` veya ``"pages"``; API katmanı bunu 402'ye
    ve kullanıcıya-okur mesaja çevirir.
    """

    def __init__(self, limit_kind: str, used: int, limit: int) -> None:
        super().__init__(f"{limit_kind} kotası aşıldı ({used}/{limit}).")
        self.limit_kind = limit_kind
        self.used = used
        self.limit = limit


async def get_or_create_subscription(session: AsyncSession, tenant_id: uuid.UUID) -> Subscription:
    """Kiracının aboneliğini döndürür; yoksa varsayılan FREE olarak oluşturur.

    Kiracı bağlamı (RLS) ayarlı bir oturumda çağrılmalıdır. Eşzamanlı ilk
    erişimde iki INSERT yarışırsa unique kısıt devreye girer; çakışma bir
    savepoint (``begin_nested``) içinde yutulur ve mevcut satır yeniden okunur —
    böylece dıştaki transaction (ve kiracı bağlamı) bozulmaz.
    """
    sub = await session.scalar(select(Subscription).where(Subscription.tenant_id == tenant_id))
    if sub is not None:
        return sub

    new_sub = Subscription(
        tenant_id=tenant_id,
        plan=DEFAULT_PLAN_TIER,
        status=SubscriptionStatus.ACTIVE,
    )
    try:
        async with session.begin_nested():
            session.add(new_sub)
            await session.flush()
    except IntegrityError:
        existing = await session.scalar(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        )
        assert existing is not None  # noqa: S101 - unique çakışması ⇒ satır kesin var
        return existing
    return new_sub


async def compute_usage(
    session: AsyncSession, tenant_id: uuid.UUID, *, now: datetime | None = None
) -> UsageSnapshot:
    """Kiracının içinde bulunulan dönemdeki kullanımını ve plan limitlerini döndürür."""
    now = now or datetime.now(UTC)
    subscription = await get_or_create_subscription(session, tenant_id)
    period_start, period_end = current_period_bounds(now)
    documents_used, pages_used = (
        await session.execute(
            select(
                func.count(UsageRecord.id),
                func.coalesce(func.sum(UsageRecord.pages), 0),
            ).where(
                UsageRecord.recorded_at >= period_start,
                UsageRecord.recorded_at < period_end,
            )
        )
    ).one()
    return UsageSnapshot(
        plan=get_plan(subscription.plan),
        status=subscription.status,
        documents_used=int(documents_used),
        pages_used=int(pages_used),
        period_start=period_start,
        period_end=period_end,
    )


async def enforce_document_quota(
    session: AsyncSession, tenant_id: uuid.UUID, *, now: datetime | None = None
) -> UsageSnapshot:
    """Yeni bir doküman işlenmeden önce kotayı denetler.

    Doküman **veya** sayfa kotası dolmuşsa ``QuotaExceededError`` fırlatır;
    aksi hâlde güncel kullanım anlık görüntüsünü döndürür (çağıran raporlayabilir).
    Sınırsız (``None``) boyutlar denetlenmez.
    """
    usage = await compute_usage(session, tenant_id, now=now)
    plan = usage.plan
    if plan.documents_per_month is not None and usage.documents_used >= plan.documents_per_month:
        raise QuotaExceededError("documents", usage.documents_used, plan.documents_per_month)
    if plan.pages_per_month is not None and usage.pages_used >= plan.pages_per_month:
        raise QuotaExceededError("pages", usage.pages_used, plan.pages_per_month)
    return usage


async def record_document_usage(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    *,
    pages: int = 0,
) -> UsageRecord:
    """Bir doküman için kullanım kaydı ekler (yükleme tamamlandığında; ``pages=0``).

    Flush/commit çağıranın sorumluluğundadır. Sayfa sayısı parsing sonrası
    ``set_document_usage_pages_sync`` ile güncellenir.
    """
    record = UsageRecord(tenant_id=tenant_id, document_id=document_id, pages=pages)
    session.add(record)
    return record


def set_document_usage_pages_sync(session: Session, document_id: uuid.UUID, pages: int) -> None:
    """Bir dokümanın kullanım kaydındaki sayfa sayısını günceller (worker, senkron).

    Parsing bitince gerçek sayfa sayısı yazılır (sayfa kotası). Kayıt yoksa
    (ör. bu migration'dan önce yüklenmiş doküman) sessizce geçilir. Kiracı
    bağlamı ayarlı bir oturumda çağrılmalıdır (RLS).
    """
    session.execute(
        update(UsageRecord).where(UsageRecord.document_id == document_id).values(pages=pages)
    )
