"""LLM bütçe tavanı — yarış, sızıntı, kesinti ve kiracı izolasyonu (J.6 madde 2).

Bu dosyanın konusu **tavanın gerçekten tavan olması**. Bir bütçe kontrolü üç
ayrı yoldan sessizce işlevsizleşebilir ve üçü de burada sınanır:

1. **Yarış:** harcama iş BİTİNCE yazılıyor. Yalnız "harcanan < tavan" bakan bir
   kontrol, aynı anda başlayan iki işi de geçirir ve tavan birlikte aşılır.
2. **Sızıntı:** worker çökerse rezervasyon bırakılmaz. Süresi geçmiş rezervasyon
   sayılmaya devam ederse kiracı kendi tavanına KİLİTLENİR (tavan bu kez ters
   yönde arızalanır).
3. **Kesinti:** Redis yoksa "sessizce geç" seçeneği sınırsız harcama demekti;
   muhafazakâr karara düşülmeli.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

import pytest
from redis import Redis as SyncRedis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from tenderiq_core.billing.plans import PlanTier, get_plan
from tenderiq_core.config import Settings, get_settings
from tenderiq_core.db.tenant import set_tenant_context_sync
from tenderiq_core.llm.cost import LlmCall
from tenderiq_core.llm.pricing import MICROS_PER_TRY, PricingStatus
from tenderiq_core.services.llm_budget import (
    LlmBudgetExceededError,
    admit_job_sync,
    enforce_llm_budget_sync,
    period_key,
    record_llm_calls_sync,
    release_job_reservation,
)
from tenderiq_core.services.llm_reservation import _key, reserved_total, try_reserve
from tenderiq_core.services.quota import current_period_bounds

pytestmark = pytest.mark.integration

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()

#: Rezervasyon 5 TL; FREE tavanı 25 TL → 5 iş sığar.
SETTINGS = Settings(llm_job_reservation_try=5.0, llm_reservation_ttl_seconds=600)


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def redis():  # type: ignore[no-untyped-def]
    """Gerçek Redis (testler zaten Redis'e bağlı koşuyor).

    Her testin başında bu kiracıların rezervasyonları temizlenir: önceki
    testten kalan rezervasyon, tavanı yanlış yerde kapatıp testi
    ANLAMSIZ biçimde kırardı.
    """
    client = SyncRedis.from_url(get_settings().redis_url)
    period = period_key(current_period_bounds(_now())[0])
    for tenant in (TENANT_A, TENANT_B):
        client.delete(_key(tenant, period))
    yield client
    for tenant in (TENANT_A, TENANT_B):
        client.delete(_key(tenant, period))
    client.close()


@pytest.fixture
def engine(app_database_url: str):  # type: ignore[no-untyped-def]
    engine = create_engine(app_database_url)
    try:
        yield engine
    finally:
        with Session(engine) as session, session.begin():
            for tenant in (TENANT_A, TENANT_B):
                set_tenant_context_sync(session, tenant)
                session.execute(text("DELETE FROM llm_usage"))
        engine.dispose()


def _spend(engine, tenant: uuid.UUID, try_amount: float) -> None:  # type: ignore[no-untyped-def]
    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, tenant)
        record_llm_calls_sync(
            session,
            [
                LlmCall(
                    tenant_id=tenant,
                    model="m",
                    operation="op",
                    input_tokens=1,
                    output_tokens=1,
                    cost_micros_try=int(try_amount * MICROS_PER_TRY),
                    pricing_status=PricingStatus.PRICED,
                )
            ],
        )


def _admit(engine, redis_client, tenant: uuid.UUID, job_id: uuid.UUID):  # type: ignore[no-untyped-def]
    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, tenant)
        return admit_job_sync(
            session, tenant_id=tenant, job_id=job_id, redis=redis_client, settings=SETTINGS
        )


def test_plan_tavanlari_ucretsizde_daha_siki() -> None:
    """Ücretsiz kademe kötüye kullanım yüzeyi: tavanı Pro'dan belirgin küçük."""
    free = get_plan(PlanTier.FREE).llm_budget_try_per_month
    pro = get_plan(PlanTier.PRO).llm_budget_try_per_month
    kurumsal = get_plan(PlanTier.ENTERPRISE).llm_budget_try_per_month
    assert free is not None
    assert pro is not None
    assert free < pro
    assert kurumsal is None  # sınırsız: tavan sözleşmeyle konur


def test_eszamanli_isler_tavani_birlikte_asamaz(engine, redis) -> None:  # type: ignore[no-untyped-def]
    """Rezervasyon olmasa ikisi de geçerdi; olunca yalnız sığan kadarı geçer.

    FREE tavanı 25 TL, rezervasyon 5 TL → en fazla 5 eşzamanlı iş. Harcama
    HENÜZ yazılmadı (işler bitmedi); tek koruma rezervasyondur.
    """
    kabuller = [_admit(engine, redis, TENANT_A, uuid.uuid4()).accepted for _ in range(7)]
    assert kabuller.count(True) == 5, kabuller
    assert kabuller.count(False) == 2


def test_suresi_gecmis_rezervasyon_sayilmaz_kiraci_kilitlenmez(redis) -> None:  # type: ignore[no-untyped-def]
    """Worker çökerse `release` çağrılmaz — TTL üst sınır olmalı.

    Süresi geçmiş rezervasyon sayılsaydı kiracı, hiç harcamadığı hâlde kendi
    tavanına kilitlenirdi (tavan ters yönde arızalanır).
    """
    period = period_key(current_period_bounds(_now())[0])
    key = _key(TENANT_A, period)
    redis.delete(key)
    # Çökmüş bir işin geride bıraktığı rezervasyon: son kullanma GEÇMİŞTE.
    redis.hset(key, "cokmus-is", f"{20 * MICROS_PER_TRY}:{int(time.time()) - 1}")

    assert reserved_total(redis, tenant_id=TENANT_A, period_key=period) == 0
    kabul, toplam = try_reserve(
        redis,
        tenant_id=TENANT_A,
        period_key=period,
        job_id=uuid.uuid4(),
        amount_micros=5 * MICROS_PER_TRY,
        remaining_micros=25 * MICROS_PER_TRY,
        ttl_seconds=600,
    )
    assert kabul is True
    assert toplam == 5 * MICROS_PER_TRY  # sahipsiz 20 TL sayılmadı
    assert redis.hexists(key, "cokmus-is") is False  # temizlendi


def test_is_bitince_rezervasyon_birakilir(engine, redis) -> None:  # type: ignore[no-untyped-def]
    period = period_key(current_period_bounds(_now())[0])
    job_id = uuid.uuid4()
    assert _admit(engine, redis, TENANT_A, job_id).accepted
    assert reserved_total(redis, tenant_id=TENANT_A, period_key=period) == 5 * MICROS_PER_TRY

    release_job_reservation(redis, tenant_id=TENANT_A, job_id=job_id)
    assert reserved_total(redis, tenant_id=TENANT_A, period_key=period) == 0


def test_tavan_dolunca_yeni_is_reddedilir(engine, redis) -> None:  # type: ignore[no-untyped-def]
    """Sert tavan reddeder — küçük modele düşme/kısaltma yok, açık hata var."""
    _spend(engine, TENANT_A, 25.0)  # FREE tavanı tam doldu
    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, TENANT_A)
        with pytest.raises(LlmBudgetExceededError) as exc:
            enforce_llm_budget_sync(
                session,
                tenant_id=TENANT_A,
                job_id=uuid.uuid4(),
                redis=redis,
                settings=SETTINGS,
            )
    # Kullanıcıya söylenecek üç şey: ne kadar, tavan ne, ne zaman sıfırlanır.
    assert exc.value.spent_micros == 25 * MICROS_PER_TRY
    assert exc.value.limit_micros == 25 * MICROS_PER_TRY
    assert exc.value.period_end is not None


def test_yumusak_esik_reddetmez_ama_isaretler(engine, redis) -> None:  # type: ignore[no-untyped-def]
    """Eşik UYARIDIR; iş kabul edilmeye devam eder.

    Harcama tam %80'e (20/25 TL) getiriliyor: kalan 5 TL, tek rezervasyona
    (5 TL) tam yeter. Daha yükseğe çıkarsaydık ret gelirdi — ama o ret
    yumuşak eşikten değil, SERT tavandan gelirdi ve test yanlış şeyi
    ölçerdi. Pratik sonuç: kabul sınırı fiilen `tavan - rezervasyon`dur,
    yani son kısmi dilim hiç verilmez (bilinçli muhafazakârlık).
    """
    _spend(engine, TENANT_A, 20.0)
    decision = _admit(engine, redis, TENANT_A, uuid.uuid4())
    assert decision.accepted is True
    assert decision.soft_exceeded is True


def test_bir_kiracinin_harcamasi_digerinin_tavanini_etkilemez(engine, redis) -> None:  # type: ignore[no-untyped-def]
    _spend(engine, TENANT_A, 25.0)
    assert _admit(engine, redis, TENANT_A, uuid.uuid4()).accepted is False
    assert _admit(engine, redis, TENANT_B, uuid.uuid4()).accepted is True


def test_redis_yoksa_muhafazakar_karara_dusulur(engine) -> None:  # type: ignore[no-untyped-def]
    """Kesintide sessizce geçmek sınırsız harcama demekti.

    Muhafazakârlık: tek rezervasyon varmış gibi davranılır, yani sınır erken
    kapanır. Tavan hâlâ zorlanır; kaybedilen tek şey yarış korumasıdır.
    """
    _spend(engine, TENANT_A, 21.0)  # kalan 4 TL < 5 TL tahmin
    decision = _admit(engine, None, TENANT_A, uuid.uuid4())
    assert decision.degraded is True
    assert decision.accepted is False  # erken kapandı

    decision_b = _admit(engine, None, TENANT_B, uuid.uuid4())  # hiç harcamamış
    assert decision_b.degraded is True
    assert decision_b.accepted is True
