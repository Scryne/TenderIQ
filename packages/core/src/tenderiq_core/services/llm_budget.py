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
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tenderiq_core.billing.plans import DEFAULT_PLAN_TIER, PlanTier, get_plan
from tenderiq_core.config import Settings, get_settings
from tenderiq_core.llm.cost import LlmCall
from tenderiq_core.llm.pricing import MICROS_PER_TRY, PricingStatus
from tenderiq_core.logging import get_logger
from tenderiq_core.models import LlmUsage, Subscription
from tenderiq_core.ops import record_llm_budget_degraded
from tenderiq_core.services.llm_reservation import release, try_reserve
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


# ── Tavan (J.6 madde 2) ─────────────────────────────────────────────────────


class LlmBudgetExceededError(Exception):
    """Aylık LLM bütçesi doldu: YENİ iş reddedilir.

    Sert tavan **reddeder**. Sessizce küçük modele düşmek, bağlamı kısaltmak ya
    da kısmi sonuç üretmek seçenek değil: kullanıcı, sonucun neden eksik
    olduğunu göremeyeceği bir "başarı" yerine açık bir ret görmeli.
    """

    def __init__(self, *, spent_micros: int, limit_micros: int, period_end: datetime) -> None:
        super().__init__(
            f"Aylık analiz bütçesi doldu ({spent_micros / MICROS_PER_TRY:.2f}/"
            f"{limit_micros / MICROS_PER_TRY:.2f} TL)."
        )
        self.spent_micros = spent_micros
        self.limit_micros = limit_micros
        self.period_end = period_end


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    """Kabul kararı + kullanıcıya/yöneticiye anlatılacak sayılar."""

    accepted: bool
    limit_micros: int | None
    spent_micros: int
    reserved_micros: int
    period_end: datetime
    #: Yumuşak eşik aşıldı mı (uyarı; ret DEĞİL).
    soft_exceeded: bool
    #: Rezervasyon kurulamadığı için muhafazakâr DB kontrolüne düşüldü mü.
    degraded: bool
    unpriced_calls: int

    @property
    def remaining_micros(self) -> int | None:
        if self.limit_micros is None:
            return None
        return max(0, self.limit_micros - self.spent_micros - self.reserved_micros)


def period_key(period_start: datetime) -> str:
    """Rezervasyon anahtarının dönem parçası (kota dönemiyle AYNI takvim ayı)."""
    return period_start.strftime("%Y-%m")


def _tenant_plan_tier(session: Session) -> PlanTier:
    """Aktif kiracının plan kademesi; aboneliği yoksa varsayılan (FREE).

    Bilinmeyen/eksik abonelikte **en sıkı** kademeye düşmek bilinçli: kaydı
    olmayan bir kiracıya sınırsız bütçe vermek, kayıt açıkken doğrudan zarardır.
    """
    row = session.scalar(select(Subscription.plan))
    if row is None:
        return DEFAULT_PLAN_TIER
    return PlanTier(row)


def _degraded_decision(remaining_micros: int, estimate_micros: int) -> tuple[bool, int]:
    """Rezervasyonsuz, muhafazakâr karar: tek iş varmış gibi davran."""
    accepted = remaining_micros >= estimate_micros
    return accepted, estimate_micros if accepted else 0


def estimate_job_micros(pages: int | None, settings: Settings) -> int:
    """Bir işin rezerve edilecek muhafazakâr maliyet tahmini (mikro-TL).

    **Neden sabit bir tutar YETMEZ.** Aşım `eşzamanlılık × tahmin` ile sınırlı;
    bu sınırın anlamlı olması tahminin gerçek maliyetin ALTINDA kalmamasına
    bağlı. Tur 15'te gerçek şartnamelerle ölçüldü: sabit 5 TL, 12-29 sayfalık
    tipik bir şartnamenin gerçek maliyetinin (10-25 TL) 2-5 katı ALTINDA kaldı —
    yani rezervasyon tavanı koruyor görünüp korumuyordu.

    Tahminin iki bileşeni ölçümün yapısını izler:

    - **Sabit**: dört çıkarım ajanının bağlamı `retrieval_agent_context_limit`
      ile TAVANLIDIR, dolayısıyla doküman büyüdükçe büyümez.
    - **Sayfa başına**: büyüyen şey bulgu sayısıdır — çıktı token'ları ve
      compliance isteminin gereksinim listesi.

    ``pages`` bilinmiyorsa (parsing sayfa sayısı yazmamışsa) tavan kullanılır:
    bilinmeyen boyutu ucuz saymak, tam da korunmak istenen aşımı üretirdi.
    """
    if pages is None:
        return int(settings.llm_job_reservation_max_try * MICROS_PER_TRY)
    estimate_try = settings.llm_job_reservation_try + max(0, pages) * (
        settings.llm_job_reservation_page_try
    )
    capped = min(estimate_try, settings.llm_job_reservation_max_try)
    return int(capped * MICROS_PER_TRY)


def admit_job_sync(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    redis: Any | None,
    pages: int | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> BudgetDecision:
    """Bir işi bütçe açısından kabul eder ya da REDDEDER (karar döndürür).

    Sıra önemli: önce harcama okunur (DB), sonra rezervasyon denenir (Redis).
    Karar ``harcanan + rezerve`` üzerinden verilir — yalnız harcanana bakmak,
    eşzamanlı işlerin tavanı birlikte aşmasına izin verirdi (harcama iş
    BİTİNCE yazılıyor).

    **Redis kesintisinde muhafazakâr DB kontrolüne düşülür**, işler
    durdurulmaz. Gerekçe: kesintide her işi reddetmek ürünü tamamen durdurur;
    DB kontrolü KAYITLI harcamayı hâlâ zorlar ve kaybedilen tek şey yarış
    korumasıdır. Muhafazakârlık şurada: tek bir rezervasyon varmış gibi
    davranılır (``harcanan + tahmin <= tavan``), yani sınır erken kapanır.
    Kesinti ops metriğine yazılır — "sessizce geç" seçenek değildi.
    """
    settings = settings or get_settings()
    snapshot = compute_spend_sync(session, now=now)
    plan = get_plan(_tenant_plan_tier(session))
    limit_try = plan.llm_budget_try_per_month

    if limit_try is None:  # sınırsız kademe (kurumsal: tavan sözleşmeyle)
        return BudgetDecision(
            accepted=True,
            limit_micros=None,
            spent_micros=snapshot.spent_micros_try,
            reserved_micros=0,
            period_end=snapshot.period_end,
            soft_exceeded=False,
            degraded=False,
            unpriced_calls=snapshot.unpriced_calls,
        )

    limit_micros = limit_try * MICROS_PER_TRY
    estimate = estimate_job_micros(pages, settings)
    remaining = max(0, limit_micros - snapshot.spent_micros_try)
    soft_exceeded = snapshot.spent_micros_try >= int(
        limit_micros * settings.llm_budget_soft_threshold
    )
    degraded = False

    if redis is None:
        accepted, reserved = _degraded_decision(remaining, estimate)
        degraded = True
    else:
        try:
            accepted, reserved = try_reserve(
                redis,
                tenant_id=tenant_id,
                period_key=period_key(snapshot.period_start),
                job_id=job_id,
                amount_micros=estimate,
                remaining_micros=remaining,
                ttl_seconds=settings.llm_reservation_ttl_seconds,
            )
        except Exception as exc:
            logger.warning("llm_rezervasyon_kurulamadi", error=str(exc))
            record_llm_budget_degraded(reason="redis_unavailable")
            accepted, reserved = _degraded_decision(remaining, estimate)
            degraded = True

    return BudgetDecision(
        accepted=accepted,
        limit_micros=limit_micros,
        spent_micros=snapshot.spent_micros_try,
        reserved_micros=reserved,
        period_end=snapshot.period_end,
        soft_exceeded=soft_exceeded,
        degraded=degraded,
        unpriced_calls=snapshot.unpriced_calls,
    )


def enforce_llm_budget_sync(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    redis: Any | None,
    pages: int | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> BudgetDecision:
    """`admit_job_sync` + reddedildiyse `LlmBudgetExceededError`."""
    decision = admit_job_sync(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        redis=redis,
        pages=pages,
        settings=settings,
        now=now,
    )
    if not decision.accepted:
        # Sınırsız kademede ret üretilmez; tip daraltması için açık kontrol
        # (assert üretimde -O ile silinebilir, bu yol para kararı veriyor).
        if decision.limit_micros is None:  # pragma: no cover - mantıken erişilmez
            return decision
        raise LlmBudgetExceededError(
            spent_micros=decision.spent_micros,
            limit_micros=decision.limit_micros,
            period_end=decision.period_end,
        )
    return decision


def release_job_reservation(
    redis: Any | None, *, tenant_id: uuid.UUID, job_id: uuid.UUID, now: datetime | None = None
) -> None:
    """İş bitince rezervasyonu bırakır (gerçek maliyet artık kayıtta)."""
    if redis is None:
        return
    start, _ = current_period_bounds(now or datetime.now(UTC))
    release(redis, tenant_id=tenant_id, period_key=period_key(start), job_id=job_id)
