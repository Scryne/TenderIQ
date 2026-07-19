"""LLM çağrı izleme (Langfuse, §6.11) — sağlayıcı-agnostik, anahtar-kapılı no-op.

Sentry deseniyle aynı (bkz. ``observability``): ``LANGFUSE_*`` anahtarları yoksa
tracing TAMAMEN no-op — langfuse hiç import edilmez, dev/test/CI hesap
gerektirmez. Anahtarlar doldurulunca her LLM üretimi (generation) trace edilir:
model, gecikme ve token kullanımı (maliyet Langfuse tarafında model fiyatından
hesaplanır). Sağlayıcı fark etmez — qwen (Ollama) çağrıları da izlenir.

KVKK / zero-retention (§10.3): getirilen bağlam blokları DOKÜMAN İÇERİĞİDİR.
Varsayılan olarak Langfuse'a YALNIZ metadata gönderilir (istem/çıktı gönderilmez);
``LANGFUSE_CAPTURE_IO=true`` (yalnız self-hosted Langfuse önerilir) tam I/O açar.

Not: langfuse SDK yolu (``start_as_current_generation``) tek bir adaptörde
izole tutulmuştur ve ilk kez etkinleştirildiğinde canlı doğrulanmalıdır; dev'de
qwen + anahtarsız kurulumda bu yol hiç çalışmaz (no-op).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

from tenderiq_core.config import Settings, get_settings
from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.llm.tracing")


class GenerationSpan(Protocol):
    """Tek bir LLM üretiminin kaydedici sözleşmesi (no-op ↔ Langfuse ortak yüzü)."""

    def record(
        self,
        *,
        output: object = ...,
        input_tokens: int | None = ...,
        output_tokens: int | None = ...,
    ) -> None:
        """Token kullanımını (ve capture_io açıksa çıktıyı) trace'e yazar."""
        ...


class _NoOpSpan:
    """Tracing kapalıyken kullanılan span — her çağrı no-op."""

    def record(
        self,
        *,
        output: object = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        return None


class LLMTracer:
    """Varsayılan no-op tracer. ``LangfuseTracer`` davranışı geçersiz kılar.

    ``generation`` bir bağlam yöneticisidir: LLM API çağrısı bununla sarılır,
    çağrı içinde ``span.record(...)`` ile token kullanımı (ve isteğe bağlı çıktı)
    bildirilir. Kapalıyken tüm yol maliyetsizdir.
    """

    @contextmanager
    def generation(
        self, *, name: str, model: str, system: str, prompt: str
    ) -> Iterator[GenerationSpan]:
        yield _NoOpSpan()

    def flush(self) -> None:
        """Bekleyen trace'leri gönderir (no-op tracer'da anlamsız)."""
        return None


class _LangfuseSpan:
    """Tek bir Langfuse generation'ının kaydedici sarmalayıcısı."""

    def __init__(self, generation: Any, *, capture_io: bool) -> None:
        self._generation = generation
        self._capture_io = capture_io

    def record(
        self,
        *,
        output: object = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        update: dict[str, Any] = {}
        usage: dict[str, int] = {}
        if input_tokens is not None:
            usage["input"] = input_tokens
        if output_tokens is not None:
            usage["output"] = output_tokens
        if usage:
            update["usage_details"] = usage
        # KVKK: çıktı (doküman türevi) yalnız açıkça izin verilirse gönderilir.
        if self._capture_io and output is not None:
            update["output"] = output
        if update:
            self._generation.update(**update)


class LangfuseTracer(LLMTracer):
    """Langfuse ile gerçek tracing (yalnız anahtarlar tanımlıyken kurulur)."""

    def __init__(self, client: Any, *, capture_io: bool) -> None:
        self._client = client
        self._capture_io = capture_io

    @contextmanager
    def generation(
        self, *, name: str, model: str, system: str, prompt: str
    ) -> Iterator[GenerationSpan]:
        # İstem/çıktı = doküman içeriği; capture_io kapalıysa Langfuse'a gitmez.
        input_payload = {"system": system, "prompt": prompt} if self._capture_io else None
        with self._client.start_as_current_generation(
            name=name, model=model, input=input_payload
        ) as generation:
            yield _LangfuseSpan(generation, capture_io=self._capture_io)

    def flush(self) -> None:
        self._client.flush()


def create_llm_tracer(settings: Settings | None = None) -> LLMTracer:
    """Ayarlara göre tracer kurar; Langfuse anahtarları yoksa no-op döner."""
    settings = settings or get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return LLMTracer()  # no-op — langfuse import EDİLMEZ
    from langfuse import Langfuse  # lazy: yalnız anahtar tanımlıyken

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    logger.info(
        "langfuse_tracing_etkin",
        host=settings.langfuse_host,
        capture_io=settings.langfuse_capture_io,
    )
    return LangfuseTracer(client, capture_io=settings.langfuse_capture_io)
