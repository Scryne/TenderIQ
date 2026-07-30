"""LLM kullanım kaydı ve bütçe sayımı (J.6).

Bu modül **yalnız yazma/sayma** işini yapar; tavan kararı (reddetme) ayrı
adımda eklenecek. Ölçümün tek başına değeri var: "ne kadar harcıyoruz"
sorusuna cevap veremeyen bir sistemde tavan koymak da anlamsız.

## Dönem penceresi

Sayım `quota.current_period_bounds` ile aynı takvim ayını kullanır. Tek kaynak
olması bilinçli: kota (doküman/sayfa) ile bütçe (para) farklı aylarda
sıfırlansaydı kullanıcıya iki farklı "dönem" anlatmak gerekirdi.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tenderiq_core.llm.cost import LlmCall
from tenderiq_core.llm.pricing import MICROS_PER_TRY, PricingStatus
from tenderiq_core.logging import get_logger
from tenderiq_core.models import LlmUsage
from tenderiq_core.services.quota import current_period_bounds

logger = get_logger("tenderiq.services.llm_budget")


@dataclass(frozen=True, slots=True)
class SpendSnapshot:
    """Bir kiracının dönem içindeki LLM harcaması."""

    period_start: datetime
    period_end: datetime
    #: Tutarı GÜVENİLİR olan kayıtların toplamı (mikro-TL).
    spent_micros_try: int
    #: Tutarı hesaplanamamış kayıt sayısı (bilinmeyen model / kur yok).
    unpriced_calls: int
    calls: int

    @property
    def spent_try(self) -> float:
        return self.spent_micros_try / MICROS_PER_TRY


def record_llm_calls_sync(
    session: Session, calls: list[LlmCall], *, job_id: uuid.UUID | None = None
) -> int:
    """Ölçülen çağrıları yazar; yazılan satır sayısını döndürür.

    Kiracı bağlamı ayarlı bir oturum bekler (RLS). Çağıran taraf hatayı
    yutmalıdır: ölçüm, ölçtüğü işi bozmamalı.
    """
    if not calls:
        return 0
    session.add_all(
        [
            LlmUsage(
                tenant_id=call.tenant_id,
                job_id=job_id,
                model=call.model[:120],
                operation=call.operation[:120],
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
                cost_micros_try=call.cost_micros_try,
                pricing_status=call.pricing_status.value,
            )
            for call in calls
        ]
    )
    return len(calls)


def compute_spend_sync(session: Session, *, now: datetime | None = None) -> SpendSnapshot:
    """Aktif kiracının dönem içi harcamasını hesaplar (RLS'ye tabi oturum).

    **Yalnız güvenilir tutarlar toplanır.** `unknown_model` ve `no_fx_rate`
    kayıtları 0 TL taşır; bunları toplamaya katmak "harcama yok" demek olurdu.
    Sayıları ayrıca döndürülür ki tavanın neden gevşek davrandığı sorulabilsin.
    """
    now = now or datetime.now(UTC)
    start, end = current_period_bounds(now)
    window = (LlmUsage.recorded_at >= start, LlmUsage.recorded_at < end)
    priced = (PricingStatus.PRICED.value, PricingStatus.UNVERIFIED.value)

    spent = session.scalar(
        select(func.coalesce(func.sum(LlmUsage.cost_micros_try), 0)).where(
            *window, LlmUsage.pricing_status.in_(priced)
        )
    )
    unpriced = session.scalar(
        select(func.count())
        .select_from(LlmUsage)
        .where(*window, LlmUsage.pricing_status.notin_(priced))
    )
    total = session.scalar(select(func.count()).select_from(LlmUsage).where(*window))

    return SpendSnapshot(
        period_start=start,
        period_end=end,
        spent_micros_try=int(spent or 0),
        unpriced_calls=int(unpriced or 0),
        calls=int(total or 0),
    )
