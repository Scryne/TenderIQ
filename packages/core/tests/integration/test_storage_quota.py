"""Depolama kotası — sayımın doğruluğu, yarış, sızıntı ve kiracı izolasyonu.

`Plan.storage_bytes` Sprint 3.3'te eklendi ama hiçbir yerde zorlanmıyordu.
Bir depolama kotası dört ayrı yoldan sessizce işlevsizleşir ve dördü de burada
sınanır:

1. **Sayım yanlış** — silinen dosya sayılmaya devam ederse kota "silinemeyen
   alan"a döner; reddedilen yükleme sayılırsa kiracı hiç kullanmadığı alanı
   öder.
2. **Yarış** — eşzamanlı yüklemeler aynı boşluğu görüp kotayı birlikte aşar
   (LLM tavanındaki dersin aynısı).
3. **Sızıntı** — yarım kalan yükleme rezervasyonu kalıcı olursa kiracı kendi
   kotasına KİLİTLENİR (kota bu kez ters yönde arızalanır).
4. **Kiracı sızıntısı** — bir kiracının dosyaları diğerinin kotasını yer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.config import Settings
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.models import (
    Document,
    DocumentKind,
    DocumentStatus,
    Organization,
    Subscription,
    SubscriptionStatus,
    Tender,
    TenderStatus,
)
from tenderiq_core.services.storage_quota import (
    StorageQuotaExceededError,
    compute_storage_usage,
    enforce_storage_quota,
)

pytestmark = pytest.mark.integration

MB = 1024 * 1024
SETTINGS = Settings(upload_pending_ttl_hours=24, storage_soft_threshold=0.8)


async def _seed_tenant(factory, slug: str, tier: PlanTier):  # type: ignore[no-untyped-def]
    """Bir organizasyon + abonelik + ihale kurar; (tenant_id, tender_id) döner."""
    async with factory() as session, session.begin():
        org = Organization(name=slug, slug=slug)
        session.add(org)
    tenant_id = org.id
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        session.add(Subscription(tenant_id=tenant_id, plan=tier, status=SubscriptionStatus.ACTIVE))
        tender = Tender(tenant_id=tenant_id, title=f"{slug} ihale", status=TenderStatus.DRAFT)
        session.add(tender)
    return tenant_id, tender.id


async def _add_document(  # type: ignore[no-untyped-def]
    factory,
    tenant_id: uuid.UUID,
    tender_id: uuid.UUID,
    *,
    size_bytes: int | None,
    status: DocumentStatus = DocumentStatus.UPLOADED,
    created_at: datetime | None = None,
    deleted_at: datetime | None = None,
) -> uuid.UUID:
    document_id = uuid.uuid4()
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        document = Document(
            id=document_id,
            tenant_id=tenant_id,
            tender_id=tender_id,
            filename="a.pdf",
            content_type="application/pdf",
            storage_key=f"{tenant_id}/{tender_id}/{document_id}/a.pdf",
            kind=DocumentKind.OTHER,
            status=status,
            size_bytes=size_bytes,
            deleted_at=deleted_at,
        )
        session.add(document)
        await session.flush()
        if created_at is not None:
            document.created_at = created_at
    return document_id


@pytest.fixture
async def factory(app_database_url: str):  # type: ignore[no-untyped-def]
    engine = create_async_engine(app_database_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def test_yalnizca_gorunur_dosyalar_sayilir(factory) -> None:  # type: ignore[no-untyped-def]
    """Silinen, reddedilen ve bayat rezervasyonlar kotaya GİRMEZ."""
    tenant, tender = await _seed_tenant(factory, f"sq-say-{uuid.uuid4().hex[:8]}", PlanTier.FREE)
    eski = datetime.now(UTC) - timedelta(hours=48)

    await _add_document(factory, tenant, tender, size_bytes=10 * MB)  # sayılır
    await _add_document(  # yumuşak silinmiş → sayılmaz
        factory, tenant, tender, size_bytes=100 * MB, deleted_at=datetime.now(UTC)
    )
    await _add_document(  # reddedilmiş → sayılmaz (nesne depodan silindi)
        factory, tenant, tender, size_bytes=100 * MB, status=DocumentStatus.FAILED
    )
    await _add_document(  # taze rezervasyon → SAYILIR
        factory, tenant, tender, size_bytes=5 * MB, status=DocumentStatus.PENDING_UPLOAD
    )
    await _add_document(  # bayat rezervasyon → sayılmaz (sızıntı koruması)
        factory,
        tenant,
        tender,
        size_bytes=200 * MB,
        status=DocumentStatus.PENDING_UPLOAD,
        created_at=eski,
    )

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        usage = await compute_storage_usage(session, tenant, settings=SETTINGS)

    assert usage.used_bytes == 15 * MB, "yalnız taze yükleme + rezervasyon sayılmalı"
    assert usage.limit_bytes == 500 * MB
    assert usage.remaining_bytes == 485 * MB


async def test_silinen_dosya_kotayi_serbest_birakir(factory) -> None:  # type: ignore[no-untyped-def]
    """Kullanıcı sildiği dosyanın alanını GERİ ALMALI.

    Aksi hâlde kota "silinemeyen alan"a döner: kullanıcı kotasını boşaltmanın
    hiçbir yolu olmadan kalıcı olarak kilitlenir.
    """
    tenant, tender = await _seed_tenant(factory, f"sq-sil-{uuid.uuid4().hex[:8]}", PlanTier.FREE)
    document_id = await _add_document(factory, tenant, tender, size_bytes=400 * MB)

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        once = await compute_storage_usage(session, tenant, settings=SETTINGS)
        document = await session.get(Document, document_id)
        assert document is not None
        document.deleted_at = datetime.now(UTC)

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        sonra = await compute_storage_usage(session, tenant, settings=SETTINGS)

    assert once.used_bytes == 400 * MB
    assert sonra.used_bytes == 0


async def test_kota_asiminda_yukleme_reddedilir(factory) -> None:  # type: ignore[no-untyped-def]
    tenant, tender = await _seed_tenant(factory, f"sq-red-{uuid.uuid4().hex[:8]}", PlanTier.FREE)
    await _add_document(factory, tenant, tender, size_bytes=450 * MB)

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        with pytest.raises(StorageQuotaExceededError) as hata:
            await enforce_storage_quota(session, tenant, incoming_bytes=100 * MB, settings=SETTINGS)
    assert hata.value.limit_bytes == 500 * MB
    assert hata.value.used_bytes == 450 * MB

    # Sığan bir yükleme geçmeli — tavan yalnız aşımda kapanır.
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        usage = await enforce_storage_quota(
            session, tenant, incoming_bytes=40 * MB, settings=SETTINGS
        )
    assert usage.used_bytes == 450 * MB


async def test_yumusak_esik_reddetmez_ama_isaretler(factory) -> None:  # type: ignore[no-untyped-def]
    """Kullanıcı dolmadan ÖNCE haberdar olmalı; eşik ret üretmez."""
    tenant, tender = await _seed_tenant(factory, f"sq-esik-{uuid.uuid4().hex[:8]}", PlanTier.FREE)
    await _add_document(factory, tenant, tender, size_bytes=420 * MB)  # %84

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        usage = await enforce_storage_quota(
            session, tenant, incoming_bytes=10 * MB, settings=SETTINGS
        )
    assert usage.soft_exceeded, "%80 eşiği aşıldı ama işaretlenmedi"
    assert usage.ratio is not None
    assert usage.ratio > 0.8


async def test_bir_kiracinin_dosyalari_digerinin_kotasini_yemez(factory) -> None:  # type: ignore[no-untyped-def]
    """Kiracı sızıntısı: sayım RLS'ye tabi olmalı."""
    a, tender_a = await _seed_tenant(factory, f"sq-a-{uuid.uuid4().hex[:8]}", PlanTier.FREE)
    b, _ = await _seed_tenant(factory, f"sq-b-{uuid.uuid4().hex[:8]}", PlanTier.FREE)
    await _add_document(factory, a, tender_a, size_bytes=490 * MB)

    async with factory() as session, session.begin():
        await set_tenant_context(session, b)
        usage_b = await compute_storage_usage(session, b, settings=SETTINGS)
    assert usage_b.used_bytes == 0, "A'nın dosyaları B'nin kotasında görünüyor"

    # B'nin yüklemesi A'nın dolu kotasından ETKİLENMEZ.
    async with factory() as session, session.begin():
        await set_tenant_context(session, b)
        await enforce_storage_quota(session, b, incoming_bytes=100 * MB, settings=SETTINGS)


async def test_kurumsal_sinirsiz_sayim_maliyeti_odemez(factory) -> None:  # type: ignore[no-untyped-def]
    """Sınırsız kademede toplam HİÇ hesaplanmamalı (ucuz kontrol)."""
    tenant, tender = await _seed_tenant(
        factory, f"sq-ent-{uuid.uuid4().hex[:8]}", PlanTier.ENTERPRISE
    )
    await _add_document(factory, tenant, tender, size_bytes=50 * 1024 * MB)

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        usage = await compute_storage_usage(session, tenant, settings=SETTINGS)

    assert usage.limit_bytes is None
    assert usage.remaining_bytes is None
    # Toplam hesaplanmadığı için 0 döner — 50 GB dosya olmasına rağmen.
    assert usage.used_bytes == 0

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        await enforce_storage_quota(
            session, tenant, incoming_bytes=10 * 1024 * MB, settings=SETTINGS
        )


async def test_rezervasyon_eszamanli_yuklemeleri_gorunur_kilar(factory) -> None:  # type: ignore[no-untyped-def]
    """Henüz tamamlanmamış yüklemeler birbirini GÖRMELİ.

    Rezervasyon olmasaydı aynı anda başlatılan on yükleme boş bir kota görüp
    hepsi kabul edilir, kota birlikte aşılırdı — yalnız "yüklenmiş < kota"
    bakmanın hatası budur.
    """
    tenant, tender = await _seed_tenant(factory, f"sq-rez-{uuid.uuid4().hex[:8]}", PlanTier.FREE)
    # Beş eşzamanlı yükleme başlatıldı, hiçbiri tamamlanmadı.
    for _ in range(5):
        await _add_document(
            factory,
            tenant,
            tender,
            size_bytes=90 * MB,
            status=DocumentStatus.PENDING_UPLOAD,
        )

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        usage = await compute_storage_usage(session, tenant, settings=SETTINGS)
        assert usage.used_bytes == 450 * MB, "tamamlanmamış yüklemeler görünmüyor"
        with pytest.raises(StorageQuotaExceededError):
            await enforce_storage_quota(session, tenant, incoming_bytes=90 * MB, settings=SETTINGS)


async def test_bayat_rezervasyon_kiraciyi_kilitlemez(factory) -> None:  # type: ignore[no-untyped-def]
    """Sızıntı ters yönde: yarım kalan yükleme kotayı kalıcı şişirmemeli."""
    tenant, tender = await _seed_tenant(factory, f"sq-bayat-{uuid.uuid4().hex[:8]}", PlanTier.FREE)
    await _add_document(
        factory,
        tenant,
        tender,
        size_bytes=490 * MB,
        status=DocumentStatus.PENDING_UPLOAD,
        created_at=datetime.now(UTC) - timedelta(hours=48),
    )

    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant)
        usage = await compute_storage_usage(session, tenant, settings=SETTINGS)
        assert usage.used_bytes == 0, "bayat rezervasyon hâlâ sayılıyor"
        await enforce_storage_quota(session, tenant, incoming_bytes=400 * MB, settings=SETTINGS)
