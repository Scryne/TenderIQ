"""Kiracı × model × işlem bazında LLM kullanım/maliyet ölçümü (J.6, madde 1).

## Neden yeni bir seam yok

`LLMTracer` zaten her LLM üretimini sarıyor ve `span.record(input_tokens=…,
output_tokens=…)` ile token'ları bildiriyor; `generation(model=…)` modeli,
`name=` ise işlemi (şema adı) taşıyor. Ölçüm için gereken her şey orada. Bu
yüzden `CostTracer` mevcut tracer'ı **sarmalar**: Langfuse yolu aynen çalışmaya
devam eder, ajan katmanına ve istemcilere hiç dokunulmaz.

## Neden ölçüm çağrıyı bloke etmiyor

Kayıt yazımı LLM çağrısının içinde DB'ye gitmez: `CostTracer` yalnız bellekteki
bir tampona ekler (contextvar), worker faz bitiminde tamponu boşaltıp tek
transaction'da yazar. Sebep iki yönlü:

1. LLM çağrısı zaten saniyeler sürüyor; araya senkron DB yazması koymak
   gecikmeyi ve hata yüzeyini büyütür.
2. **Ölçüm, ölçtüğü işi bozmamalı.** DB yazması başarısız olursa iş düşmez;
   kaybedilen kayıt sayısı ops metriğine yazılır (`llm_usage_lost`), böylece
   "maliyet düşük görünüyor" ile "kayıt kayboluyor" ayırt edilebilir.

## Kiracı bağlamı

`tenant_id_var` (contextvar) worker'da faz başında kuruluyor. Bağlam yoksa kayıt
tamponlanır ama `tenant_id=None` ile işaretlenir ve boşaltma sırasında atılır —
kiracıya atfedilemeyen bir maliyeti rastgele bir kiracıya yazmak, kotayı yanlış
kişiden düşerdi.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from tenderiq_core.config import Settings, get_settings
from tenderiq_core.llm.pricing import PricingStatus, PricingTable, load_pricing
from tenderiq_core.llm.tracing import GenerationSpan, LLMTracer
from tenderiq_core.logging import get_logger, tenant_id_var

logger = get_logger("tenderiq.llm.cost")


@dataclass(slots=True)
class LlmCall:
    """Tek bir LLM çağrısının ölçümü (henüz DB'ye yazılmamış)."""

    tenant_id: uuid.UUID | None
    model: str
    operation: str
    input_tokens: int
    output_tokens: int
    cost_micros_try: int
    pricing_status: PricingStatus


@dataclass(slots=True)
class UsageBuffer:
    """Faz süresince biriken çağrılar."""

    calls: list[LlmCall] = field(default_factory=list)


#: Faz başına tampon. ContextVar: aynı süreçte eşzamanlı işler birbirinin
#: kaydını toplamasın (Celery prefetch=1 ama beat/eventlet ileride değişebilir).
_buffer_var: ContextVar[UsageBuffer | None] = ContextVar("llm_usage_buffer", default=None)


@contextmanager
def collect_llm_usage() -> Iterator[UsageBuffer]:
    """Bu blok içindeki LLM çağrılarının ölçümünü toplar."""
    buffer = UsageBuffer()
    token = _buffer_var.set(buffer)
    try:
        yield buffer
    finally:
        _buffer_var.reset(token)


def _current_tenant() -> uuid.UUID | None:
    raw = tenant_id_var.get()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


class _CostSpan:
    """Delege span'i sarar; `record` çağrısında ölçümü tampona ekler."""

    __slots__ = ("_delegate", "_model", "_operation", "_pricing", "_recorded")

    def __init__(
        self, delegate: GenerationSpan, *, model: str, operation: str, pricing: PricingTable
    ) -> None:
        self._delegate = delegate
        self._model = model
        self._operation = operation
        self._pricing = pricing
        self._recorded = False

    def record(
        self,
        *,
        output: object = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        # Önce delege (Langfuse) — ölçüm eklentisi asıl tracing'i geciktirmesin.
        self._delegate.record(output=output, input_tokens=input_tokens, output_tokens=output_tokens)
        # Token bilgisi gelmediyse ölçecek bir şey yok (sağlayıcı bildirmemiş).
        if input_tokens is None and output_tokens is None:
            return
        self._recorded = True
        cost, status = self._pricing.cost_micros_try(
            self._model, input_tokens=input_tokens or 0, output_tokens=output_tokens or 0
        )
        if status is PricingStatus.UNKNOWN_MODEL:
            # Sessizce 0 TL saymak, tavanı görünmez biçimde devre dışı bırakırdı.
            logger.warning(
                "llm_fiyati_bilinmiyor",
                model=self._model,
                operation=self._operation,
                pricing_source=self._pricing.source,
            )
        call = LlmCall(
            tenant_id=_current_tenant(),
            model=self._model,
            operation=self._operation,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            cost_micros_try=cost,
            pricing_status=status,
        )
        buffer = _buffer_var.get()
        if buffer is None:
            # Tampon yoksa kayıt tutulamaz. Sessiz kalmak "maliyet düşük"
            # yanılsaması üretirdi; sayaç bunu görünür kılar.
            _count_lost(1, reason="no_buffer")
            return
        buffer.calls.append(call)


class CostTracer(LLMTracer):
    """Var olan tracer'ı sarmalayıp her üretimin maliyetini ölçer."""

    def __init__(self, delegate: LLMTracer, *, pricing: PricingTable) -> None:
        self._delegate = delegate
        self._pricing = pricing

    @contextmanager
    def generation(
        self, *, name: str, model: str, system: str, prompt: str
    ) -> Iterator[GenerationSpan]:
        with self._delegate.generation(
            name=name, model=model, system=system, prompt=prompt
        ) as span:
            yield _CostSpan(span, model=model, operation=name, pricing=self._pricing)

    def flush(self) -> None:
        # Delege Langfuse ise flush'ı vardır; no-op tracer'da yoktur.
        flush = getattr(self._delegate, "flush", None)
        if callable(flush):
            flush()


def _count_lost(amount: int, *, reason: str) -> None:
    """Kaybedilen kayıt sayacı — ölçümün kendi arızasını görünür kılar."""
    logger.warning("llm_kullanim_kaydi_kayboldu", amount=amount, reason=reason)
    try:
        from tenderiq_core.ops import record_llm_usage_lost

        record_llm_usage_lost(amount, reason=reason)
    except Exception as exc:  # ölçüm, ölçtüğü işi ASLA bozmaz
        logger.debug("llm_kayip_sayaci_yazilamadi", error=str(exc))


def wrap_tracer_with_cost(delegate: LLMTracer, settings: Settings | None = None) -> LLMTracer:
    """`create_llm_tracer` çıktısını maliyet ölçümüyle sarar."""
    settings = settings or get_settings()
    return CostTracer(delegate, pricing=load_pricing(settings))


def drain_buffer(buffer: UsageBuffer) -> list[LlmCall]:
    """Tamponu boşaltır; kiracıya atfedilemeyen kayıtlar ATILIR ve sayılır."""
    calls = buffer.calls
    buffer.calls = []
    attributable = [call for call in calls if call.tenant_id is not None]
    orphaned = len(calls) - len(attributable)
    if orphaned:
        _count_lost(orphaned, reason="no_tenant")
    return attributable
