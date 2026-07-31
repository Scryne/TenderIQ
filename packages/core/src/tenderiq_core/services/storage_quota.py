"""Depolama kotası — `Plan.storage_bytes`ın zorlandığı yer (J.6 madde 3).

Alan Sprint 3.3'te eklendi ama hiçbir yerde zorlanmıyordu: kiracı sınırsız
yükleyebiliyordu. Bu modül üç soruyu yanıtlar — *ne sayılır*, *ne zaman
bakılır*, *eşzamanlı yüklemeler nasıl birlikte aşamaz*.

## Ne sayılır

Kotaya sayılan küme, kullanıcının **görebildiği** dosyalardır:

- ``UPLOADED`` dokümanlar → gerçek ``size_bytes``;
- **taze** ``PENDING_UPLOAD`` dokümanlar → *beyan edilen* boyut (rezervasyon,
  aşağıya bakın);
- ``FAILED`` **sayılmaz** — reddedilen nesne depodan zaten silinir;
- yumuşak silinmiş (``deleted_at``) **sayılmaz**.

**Yumuşak silmenin ödünü açıkça kaydedilmiştir.** Silinen dosya nesne
depolamada saklama penceresi dolana dek FİZİKSEL olarak durur (KVKK §8.3
temizlik işi siler). Kota yine de hemen serbest bırakılır: kullanıcı sildiği
dosyanın kotasını geri alamazsa kota "silinemeyen alan"a dönerdi. Bedeli,
yükle-sil-yükle döngüsüyle fiziksel kullanımın kotanın üstüne çıkabilmesidir;
bu, saklama penceresiyle SINIRLIDIR ve kota değil **maliyet** sorunudur.

## Ne zaman bakılır — iki kapı

1. **Yükleme BAŞLAMADAN** (imzalı URL verilmeden): istemcinin beyan ettiği
   boyutla erken red. Kullanıcı 90 MB'ı boşuna yüklemez.
2. **Tamamlanırken**: nesnenin GERÇEK boyutuyla yetkili denetim. Beyan edilen
   boyut istemciden gelir, yani GÜVENİLMEZDİR — tek kapı olsaydı 1 bayt beyan
   edip 90 MB yüklemek kotayı tamamen atlardı.

Doküman/sayfa kotasındaki kalıbın aynısı (erken red + yetkili denetim).

## Eşzamanlılık: rezervasyon + kiracı bazlı seri hâle getirme

Taze ``PENDING_UPLOAD`` satırının beyan edilen boyutu bir **rezervasyondur**:
henüz yüklenmemiş ama yer ayrılmış alan. Böylece aynı anda başlatılan on
yükleme birbirini görür. Ayrı bir rezervasyon deposu (Redis) GEREKMEZ — satır
zaten var.

"Topla, karşılaştır, ekle" üç ayrı adım olduğu için araya başka bir istek
girebilirdi (LLM tavanındaki yarışın aynısı). Burada kiracının ``subscription``
satırı ``FOR UPDATE`` ile kilitlenerek kota kararları kiracı bazında seri hâle
getirilir: farklı kiracılar birbirini BEKLEMEZ, aynı kiracının eşzamanlı
yüklemeleri sıraya girer.

Sızıntı yok: yarım kalan ``PENDING_UPLOAD`` satırları
``UPLOAD_PENDING_TTL_HOURS``tan sonra sayımdan düşer (zaten var olan temizlik
işi de onları ``failed`` yapar). Rezervasyon kiracıyı kalıcı kilitleyemez.

## Kurumsal "sınırsız" ucuz olmalı

``storage_bytes is None`` ise **toplam hiç hesaplanmaz**: sınırsız kademede
her yüklemede kiracının tüm dokümanlarını taramak, hiçbir karara girmeyen bir
maliyet olurdu.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.billing.plans import DEFAULT_PLAN_TIER, get_plan
from tenderiq_core.config import Settings, get_settings
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Document, DocumentStatus, Subscription

logger = get_logger("tenderiq.services.storage_quota")

__all__ = [
    "StorageQuotaExceededError",
    "StorageUsage",
    "compute_storage_usage",
    "enforce_storage_quota",
]


class StorageQuotaExceededError(Exception):
    """Depolama kotası dolu: yükleme REDDEDİLİR.

    ``used_bytes`` rezervasyonları İÇERİR (taze pending yüklemeler), yani
    kullanıcıya gösterilen sayı "şu an ayrılmış alan"dır.
    """

    def __init__(self, *, used_bytes: int, incoming_bytes: int, limit_bytes: int) -> None:
        super().__init__(
            f"Depolama kotası dolu ({used_bytes + incoming_bytes}/{limit_bytes} bayt)."
        )
        self.used_bytes = used_bytes
        self.incoming_bytes = incoming_bytes
        self.limit_bytes = limit_bytes


@dataclass(frozen=True, slots=True)
class StorageUsage:
    """Kiracının depolama kullanımı + plan kotası."""

    #: Kotaya sayılan toplam (yüklenmiş + taze rezervasyonlar), bayt.
    used_bytes: int
    #: Plan kotası; ``None`` = sınırsız (kurumsal).
    limit_bytes: int | None
    #: Yumuşak eşik aşıldı mı (uyarı; ret DEĞİL).
    soft_exceeded: bool

    @property
    def remaining_bytes(self) -> int | None:
        if self.limit_bytes is None:
            return None
        return max(0, self.limit_bytes - self.used_bytes)

    @property
    def ratio(self) -> float | None:
        """Kullanım oranı (0-1+); sınırsız kademede ``None``."""
        if self.limit_bytes is None or self.limit_bytes == 0:
            return None
        return self.used_bytes / self.limit_bytes


def _counted_bytes_query(cutoff: datetime):  # type: ignore[no-untyped-def]
    """Kotaya sayılan baytların toplamı (RLS'ye tabi — kiracı oturumu şart).

    Kiracı süzgeci BİLİNÇLİ olarak yok: RLS zaten kiracıya kapatıyor ve
    ``app_current_tenant()`` tek yerde tanımlı. Elle ``tenant_id ==`` yazmak
    o değişmezi ikinci bir yere kopyalardı.
    """
    return select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
        Document.deleted_at.is_(None),
        Document.size_bytes.is_not(None),
        # FAILED sayılmaz: reddedilen nesne depodan silinir.
        # Taze olmayan PENDING_UPLOAD da sayılmaz — yarım kalan yükleme
        # kiracıyı kalıcı kilitlemesin.
        Document.status.in_((DocumentStatus.UPLOADED, DocumentStatus.PENDING_UPLOAD)),
        (Document.status == DocumentStatus.UPLOADED) | (Document.created_at >= cutoff),
    )


async def compute_storage_usage(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
    lock: bool = False,
) -> StorageUsage:
    """Kiracının depolama kullanımını ve kotasını hesaplar.

    ``lock=True`` ise kiracının ``subscription`` satırı ``FOR UPDATE`` ile
    kilitlenir — kota kararı verecek çağıranlar bunu kullanmalıdır (eşzamanlı
    yüklemelerin kotayı birlikte aşmasını engeller).

    **Sınırsız kademede toplam HESAPLANMAZ**: karara girmeyen bir tarama.
    """
    settings = settings or get_settings()
    now = now or datetime.now(UTC)

    statement = select(Subscription).where(Subscription.tenant_id == tenant_id)
    if lock:
        statement = statement.with_for_update()
    subscription = await session.scalar(statement)
    plan = get_plan(subscription.plan if subscription is not None else DEFAULT_PLAN_TIER)

    if plan.storage_bytes is None:  # kurumsal: sayım maliyetini ödemeyelim
        return StorageUsage(used_bytes=0, limit_bytes=None, soft_exceeded=False)

    cutoff = now - timedelta(hours=settings.upload_pending_ttl_hours)
    used = await session.scalar(_counted_bytes_query(cutoff))
    used_bytes = int(used or 0)
    return StorageUsage(
        used_bytes=used_bytes,
        limit_bytes=plan.storage_bytes,
        soft_exceeded=used_bytes >= int(plan.storage_bytes * settings.storage_soft_threshold),
    )


async def enforce_storage_quota(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    incoming_bytes: int,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> StorageUsage:
    """Yükleme kabul edilebilir mi — aşımda ``StorageQuotaExceededError``.

    Kiracının abonelik satırını kilitler; çağıran bir transaction içinde
    olmalıdır ve kilidi commit'e kadar TUTMALIDIR (aksi hâlde iki eşzamanlı
    yükleme aynı boşluğu görür). Sınırsız kademede kilit de alınmaz.
    """
    usage = await compute_storage_usage(session, tenant_id, settings=settings, now=now, lock=True)
    if usage.limit_bytes is None:
        return usage
    if usage.used_bytes + max(0, incoming_bytes) > usage.limit_bytes:
        raise StorageQuotaExceededError(
            used_bytes=usage.used_bytes,
            incoming_bytes=max(0, incoming_bytes),
            limit_bytes=usage.limit_bytes,
        )
    return usage
