"""LlmUsage kiracı izolasyonu ve harcama sayımı (J.6 madde 1; gerçek DB).

İki şey birden sınanır ve ikisi de para ile ilgili olduğu için ayrı ayrı önemli:

1. **İzolasyon:** bir kiracı başka kiracının LLM harcamasını GÖREMEZ. Görebilse
   yalnız gizlilik değil, gelecekteki tavan da yanlış hesaplanırdı (başkasının
   harcaması kendi kotasını doldururdu).
2. **Sayım:** dönem toplamı YALNIZ tutarı güvenilir kayıtları toplar.
   `unknown_model` / `no_fx_rate` kayıtları 0 TL taşır; onları toplama katmak
   "harcama yok" demek olurdu — ama sayıları ayrıca döndürülür ki tavanın neden
   gevşek davrandığı sorulabilsin.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from tenderiq_core.db.tenant import set_tenant_context_sync
from tenderiq_core.llm.cost import LlmCall
from tenderiq_core.llm.pricing import MICROS_PER_TRY, PricingStatus
from tenderiq_core.models import LlmUsage
from tenderiq_core.services.llm_budget import compute_spend_sync, record_llm_calls_sync

pytestmark = pytest.mark.integration

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()


def _call(tenant: uuid.UUID, *, micros: int, status: PricingStatus, model: str = "m") -> LlmCall:
    return LlmCall(
        tenant_id=tenant,
        model=model,
        operation="TestSemasi",
        input_tokens=1000,
        output_tokens=100,
        cost_micros_try=micros,
        pricing_status=status,
    )


@pytest.fixture
def engine(app_database_url: str):  # type: ignore[no-untyped-def]
    engine = create_engine(app_database_url)
    try:
        yield engine
    finally:
        with Session(engine) as session, session.begin():
            # Temizlik ayrıcalıklı bağlamda değil, her kiracı kendi satırını siler.
            for tenant in (TENANT_A, TENANT_B):
                set_tenant_context_sync(session, tenant)
                session.execute(text("DELETE FROM llm_usage"))
        engine.dispose()


def test_kiraci_baskasinin_llm_harcamasini_goremez(engine) -> None:  # type: ignore[no-untyped-def]
    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, TENANT_A)
        record_llm_calls_sync(
            session, [_call(TENANT_A, micros=5 * MICROS_PER_TRY, status=PricingStatus.PRICED)]
        )
    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, TENANT_B)
        record_llm_calls_sync(
            session, [_call(TENANT_B, micros=7 * MICROS_PER_TRY, status=PricingStatus.PRICED)]
        )

    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, TENANT_A)
        gorunen = session.scalars(select(LlmUsage)).all()
        assert [row.cost_micros_try for row in gorunen] == [5 * MICROS_PER_TRY]
        assert compute_spend_sync(session).spent_micros_try == 5 * MICROS_PER_TRY

    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, TENANT_B)
        assert compute_spend_sync(session).spent_micros_try == 7 * MICROS_PER_TRY


def test_fiyatlandirilamayan_kayitlar_toplama_katilmaz_ama_sayilir(engine) -> None:  # type: ignore[no-untyped-def]
    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, TENANT_A)
        record_llm_calls_sync(
            session,
            [
                _call(TENANT_A, micros=3 * MICROS_PER_TRY, status=PricingStatus.PRICED),
                _call(TENANT_A, micros=2 * MICROS_PER_TRY, status=PricingStatus.UNVERIFIED),
                _call(TENANT_A, micros=0, status=PricingStatus.UNKNOWN_MODEL),
                _call(TENANT_A, micros=0, status=PricingStatus.NO_FX_RATE),
            ],
        )

    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, TENANT_A)
        snapshot = compute_spend_sync(session)

    # Doğrulanmamış fiyat TAHMİNDİR ama harcamadır; toplama girer.
    assert snapshot.spent_micros_try == 5 * MICROS_PER_TRY
    assert snapshot.spent_try == 5.0
    # Hesaplanamayanlar ayrı sayılır — "harcama yok" ile karıştırılamaz.
    assert snapshot.unpriced_calls == 2
    assert snapshot.calls == 4


def test_onceki_donem_kayitlari_bu_donemi_kirletmez(engine) -> None:  # type: ignore[no-untyped-def]
    """Dönem penceresi kota ile AYNI takvim ayı (tek dönem tanımı)."""
    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, TENANT_A)
        record_llm_calls_sync(
            session, [_call(TENANT_A, micros=9 * MICROS_PER_TRY, status=PricingStatus.PRICED)]
        )
        # `record_llm_calls_sync` yalnız `add_all` yapar; INSERT commit'te iner.
        # Flush olmadan aşağıdaki UPDATE hiçbir satır bulamaz (ilk sürümde
        # tam olarak bu oldu ve test yanlış nedenle kırıldı).
        session.flush()
        # Kaydı geçen aya taşı.
        session.execute(
            text("UPDATE llm_usage SET recorded_at = :eski"),
            {"eski": datetime.now(UTC).replace(day=1) - timedelta(days=5)},
        )

    with Session(engine) as session, session.begin():
        set_tenant_context_sync(session, TENANT_A)
        snapshot = compute_spend_sync(session)

    assert snapshot.spent_micros_try == 0
    assert snapshot.calls == 0
