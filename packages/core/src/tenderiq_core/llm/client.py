"""Şema-zorlamalı LLM istemcisi (Sprint 2.2, §6.7).

Desen embedding/reranker katmanıyla aynıdır (ADR-0008/0012): ajanlar
``StructuredLLM`` protokolüne bağlıdır; sağlayıcı değişimi yalnızca fabrikaya
yeni bir daldır, testler sahtelerle koşar.

Şema zorlaması iki katmanlıdır:
1. **API düzeyi:** Anthropic structured outputs (``output_config.format``,
   SDK'da ``messages.parse``) çıktıyı JSON şemasına token düzeyinde kısıtlar.
2. **Reddet-ve-yeniden-iste:** yine de şemaya uymayan çıktı (ör. ``max_tokens``
   kesmesi) pydantic doğrulamasından geçemez → ihlal mesajı konuşmaya eklenir
   ve çıktı yeniden istenir (``LLM_SCHEMA_MAX_ATTEMPTS`` tavanına kadar);
   tavan aşılırsa ``SchemaEnforcementError`` yükselir (Celery retry devralır).

Güvenlik notu: ``stop_reason == "refusal"`` kalıcı hatadır — aynı istem
tekrarlanmaz (``LLMRefusalError``).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from tenderiq_core.config import Settings, get_settings
from tenderiq_core.llm.tracing import LLMTracer, create_llm_tracer
from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.llm")

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProvider(StrEnum):
    """LLM sağlayıcısı."""

    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"  # yerel model (localhost:11434); anahtarsız dev/ucuz iterasyon
    NVIDIA = "nvidia"  # NVIDIA NIM (OpenAI-uyumlu bulut); ücretsiz güçlü modeller (qwen3.5...)
    NONE = "none"  # ajanlar devre dışı (testler/CI; extracting fazı iskelet modunda)


class LLMError(Exception):
    """LLM katmanı hataları için temel sınıf."""


class LLMNotConfiguredError(LLMError):
    """Sağlayıcı seçili ama zorunlu yapılandırma (API anahtarı) eksik."""


class LLMRefusalError(LLMError):
    """Model güvenlik gerekçesiyle reddetti — aynı istem tekrarlanmaz."""


class SchemaEnforcementError(LLMError):
    """Çıktı, deneme tavanına rağmen şemaya uydurulamadı."""


class StructuredLLM(Protocol):
    """Yapılandırılmış çıkarım sözleşmesi: (sistem, istem, şema) → şema örneği."""

    @property
    def model_name(self) -> str:
        """Loglara/trace'lere yazılan model kimliği."""
        ...

    def extract(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        """İstemi şemaya birebir uyan doğrulanmış çıktıya çevirir."""
        ...


# Şema ihlalinde ikinci denemeye eklenen düzeltme talimatı şablonu.
_RETRY_TEMPLATE = (
    "Önceki çıktın şemaya uymadığı için REDDEDİLDİ. Doğrulama hatası:\n{error}\n\n"
    "Aynı görevi tekrar yap ve şemaya birebir uyan geçerli bir çıktı üret."
)


class AnthropicStructuredLLM:
    """Claude ile yapılandırılmış çıkarım (structured outputs + adaptive thinking).

    ``client`` parametresi testler içindir (sahte istemci enjeksiyonu);
    verilmezse gerçek ``anthropic.Anthropic`` istemcisi lazy kurulur.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        max_attempts: int,
        client: Any | None = None,
        tracer: LLMTracer | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._max_attempts = max(1, max_attempts)
        self._client = client
        self._tracer = tracer or LLMTracer()

    @property
    def model_name(self) -> str:
        return self._model

    def extract(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        last_error: ValidationError | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                # Her deneme bir Langfuse generation'ı (kapalıysa no-op); token
                # kullanımı çağrı içinde kaydedilir, retry'lar da izlenir.
                with self._tracer.generation(
                    name=schema.__name__, model=self._model, system=system, prompt=prompt
                ) as span:
                    response = self._get_client().messages.parse(
                        model=self._model,
                        max_tokens=self._max_output_tokens,
                        system=system,
                        thinking={"type": "adaptive"},
                        messages=messages,
                        output_format=schema,
                    )
                    usage = getattr(response, "usage", None)
                    span.record(
                        output=getattr(response, "parsed_output", None),
                        input_tokens=getattr(usage, "input_tokens", None),
                        output_tokens=getattr(usage, "output_tokens", None),
                    )
            except ValidationError as exc:
                # Şema ihlali (tipik neden: max_tokens kesmesi) → reddet, ihlali
                # konuşmaya ekle ve yeniden iste.
                last_error = exc
                logger.warning(
                    "llm_sema_ihlali",
                    model=self._model,
                    schema=schema.__name__,
                    attempt=attempt,
                    error_count=exc.error_count(),
                )
                messages = [
                    {"role": "user", "content": prompt},
                    {"role": "user", "content": _RETRY_TEMPLATE.format(error=exc)},
                ]
                continue
            if response.stop_reason == "refusal":
                raise LLMRefusalError(
                    f"Model isteği reddetti (schema={schema.__name__}); istem tekrarlanmayacak."
                )
            parsed: object = response.parsed_output
            if parsed is None:
                # Metin bloğu hiç gelmedi (beklenmedik durum) — şema ihlali say.
                messages = [
                    {"role": "user", "content": prompt},
                    {
                        "role": "user",
                        "content": _RETRY_TEMPLATE.format(error="çıktı boş — metin bloğu yok"),
                    },
                ]
                continue
            # SDK zaten şema örneği döndürür; istemci Any tiplendiği için burada
            # yeniden doğrulanır (tip güvencesi + sahte istemcilere tolerans).
            return schema.model_validate(parsed)
        raise SchemaEnforcementError(
            f"Çıktı {self._max_attempts} denemede şemaya uydurulamadı "
            f"(schema={schema.__name__}): {last_error}"
        )

    def flush(self) -> None:
        """Bekleyen Langfuse izlerini gönderir (anahtarsız/no-op tracer'da bedelsiz)."""
        self._tracer.flush()

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client


class OllamaStructuredLLM:
    """Yerel Ollama modeliyle yapılandırılmış çıkarım (structured outputs).

    Anthropic dalıyla aynı ``StructuredLLM`` sözleşmesini uygular; farklar
    sağlayıcıya özgü: (1) API anahtarı yoktur, ``localhost:11434``e HTTP; (2)
    şema zorlaması ``format=<json-schema>`` ile yapılır (Ollama'nın grammar
    kısıtı); (3) ``thinking``/``refusal`` gibi Claude'a özgü kavramlar yoktur.

    Reddet-ve-yeniden-iste döngüsü korunur: ``format`` çıktının YAPISAL
    geçerliliğini kısıtlar ama ``num_predict`` kesmesi/boş yanıt yine şemayı
    bozabilir → ihlal konuşmaya eklenir ve yeniden istenir. Sıcaklık 0:
    çıkarım deterministik olmalı (birebir alıntı/grounding için kritik).

    ``num_ctx`` bağlam penceresini AÇIKÇA belirtir: Ollama varsayılanı (4096)
    uzun şartname bağlamını sessizce kırpar ve grounding'i bozar (§6.9).

    ``client`` parametresi testler içindir; verilmezse gerçek ``ollama.Client``
    lazy kurulur.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        max_output_tokens: int,
        max_attempts: int,
        num_ctx: int = 8192,
        client: Any | None = None,
        tracer: LLMTracer | None = None,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._max_attempts = max(1, max_attempts)
        self._num_ctx = num_ctx
        self._client = client
        self._tracer = tracer or LLMTracer()

    @property
    def model_name(self) -> str:
        return self._model

    def extract(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        last_error: ValidationError | None = None
        for attempt in range(1, self._max_attempts + 1):
            # Geçici hatalar (bağlantı reddi/5xx) istisna olarak yükselir →
            # graph RetryPolicy'si devralır (ADR-0005); burada yakalanmaz.
            with self._tracer.generation(
                name=schema.__name__, model=self._model, system=system, prompt=prompt
            ) as span:
                response = self._get_client().chat(
                    model=self._model,
                    messages=messages,
                    format=schema.model_json_schema(),
                    options={
                        "temperature": 0,
                        "num_ctx": self._num_ctx,
                        "num_predict": self._max_output_tokens,
                    },
                )
                content = response.message.content
                span.record(
                    output=content,
                    input_tokens=getattr(response, "prompt_eval_count", None),
                    output_tokens=getattr(response, "eval_count", None),
                )
            if content:
                try:
                    return schema.model_validate_json(content)
                except ValidationError as exc:
                    last_error = exc
                    logger.warning(
                        "llm_sema_ihlali",
                        model=self._model,
                        schema=schema.__name__,
                        attempt=attempt,
                        error_count=exc.error_count(),
                    )
                    reason: str | ValidationError = exc
                else:  # pragma: no cover - return zaten döndü
                    reason = ""
            else:
                # Boş yanıt (tipik neden: num_predict kesmesi) — şema ihlali say.
                reason = "çıktı boş — model içerik döndürmedi"
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
                {"role": "user", "content": _RETRY_TEMPLATE.format(error=reason)},
            ]
        raise SchemaEnforcementError(
            f"Çıktı {self._max_attempts} denemede şemaya uydurulamadı "
            f"(schema={schema.__name__}): {last_error}"
        )

    def flush(self) -> None:
        """Bekleyen Langfuse izlerini gönderir (anahtarsız/no-op tracer'da bedelsiz)."""
        self._tracer.flush()

    def _get_client(self) -> Any:
        if self._client is None:
            import ollama

            self._client = ollama.Client(host=self._base_url)
        return self._client


class NvidiaStructuredLLM:
    """NVIDIA NIM (OpenAI-uyumlu bulut) ile yapılandırılmış çıkarım.

    ``integrate.api.nvidia.com`` — ücretsiz güçlü bulut modeller (qwen3.5,
    llama-3.3...). Yerel qwen2.5:7b'ye göre çok daha yüksek Tükçe + grounding
    kalitesi. Ollama dalıyla aynı ``StructuredLLM`` sözleşmesini uygular; farklar
    sağlayıcıya özgü: (1) API anahtarı (``nvapi-...``) gerekir; (2) şema zorlaması
    OpenAI-standardı ``response_format=json_schema`` ile yapılır (NIM strict guided
    decoding — iç içe pydantic şemaları `$defs`/`$ref` dahil kabul edilir).

    Reddet-ve-yeniden-iste döngüsü korunur: ``response_format`` çıktının YAPISAL
    geçerliliğini kısıtlar ama ``max_tokens`` kesmesi/boş yanıt yine şemayı
    bozabilir → ihlal konuşmaya eklenir ve yeniden istenir. Sıcaklık 0: çıkarım
    deterministik olmalı (birebir alıntı/grounding için kritik).

    KVKK notu (§10.3): bu BULUT sağlayıcıdır — doküman içeriği NVIDIA'ya gider
    (yerel Ollama'nın aksine). Retention duruşu kurulumda loglanır; production'da
    gerçek şartname içeriği için NVIDIA veri-saklama şartları/DPA gerekir.

    ``client`` parametresi testler içindir; verilmezse gerçek ``openai.OpenAI``
    istemcisi lazy kurulur (NVIDIA endpoint'ine yönlendirilmiş).
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        max_output_tokens: int,
        max_attempts: int,
        client: Any | None = None,
        tracer: LLMTracer | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._max_attempts = max(1, max_attempts)
        self._client = client
        self._tracer = tracer or LLMTracer()

    @property
    def model_name(self) -> str:
        return self._model

    def extract(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": True,
            },
        }
        last_error: ValidationError | None = None
        for attempt in range(1, self._max_attempts + 1):
            # Geçici hatalar (rate limit/5xx) istisna olarak yükselir → graph
            # RetryPolicy'si devralır (ADR-0005); burada yakalanmaz.
            with self._tracer.generation(
                name=schema.__name__, model=self._model, system=system, prompt=prompt
            ) as span:
                response = self._get_client().chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=0,
                    max_tokens=self._max_output_tokens,
                    response_format=response_format,
                )
                choice = response.choices[0]
                content = choice.message.content
                usage = getattr(response, "usage", None)
                span.record(
                    output=content,
                    input_tokens=getattr(usage, "prompt_tokens", None),
                    output_tokens=getattr(usage, "completion_tokens", None),
                )
            # İçerik filtresi / açık ret kalıcı hatadır — aynı istem tekrarlanmaz.
            if choice.finish_reason == "content_filter" or getattr(choice.message, "refusal", None):
                raise LLMRefusalError(
                    f"Model isteği reddetti (schema={schema.__name__}); istem tekrarlanmayacak."
                )
            if content:
                try:
                    return schema.model_validate_json(content)
                except ValidationError as exc:
                    last_error = exc
                    logger.warning(
                        "llm_sema_ihlali",
                        model=self._model,
                        schema=schema.__name__,
                        attempt=attempt,
                        error_count=exc.error_count(),
                    )
                    reason: str | ValidationError = exc
                else:  # pragma: no cover - return zaten döndü
                    reason = ""
            else:
                # Boş yanıt (tipik neden: max_tokens kesmesi) — şema ihlali say.
                reason = "çıktı boş — model içerik döndürmedi"
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
                {"role": "user", "content": _RETRY_TEMPLATE.format(error=reason)},
            ]
        raise SchemaEnforcementError(
            f"Çıktı {self._max_attempts} denemede şemaya uydurulamadı "
            f"(schema={schema.__name__}): {last_error}"
        )

    def flush(self) -> None:
        """Bekleyen Langfuse izlerini gönderir (anahtarsız/no-op tracer'da bedelsiz)."""
        self._tracer.flush()

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client


def _log_retention_posture(settings: Settings, provider: LLMProvider) -> None:
    """Zero-retention duruşunu (§10.3) gözlemlenebilir kılar (istek başına değil, kurulumda).

    - ``ollama``: veri makineden ÇIKMAZ → zero-retention doğası gereği sağlanır.
    - ``anthropic``: Claude API'si varsayılan olarak veriyi eğitimde kullanmaz;
      kalıcı sıfır-saklama (ZDR) kurumsal anlaşmaya dayanır (yayın öncesi teyit).
    - ``nvidia``: BULUT NIM API'si — doküman içeriği NVIDIA'ya gider; veri-saklama
      şartları sağlayıcıya bağlıdır (production gerçek şartname için DPA gerekir).
    - Langfuse etkinse ``capture_io`` False iken doküman içeriği trace'e GİRMEZ.
    """
    posture = {
        LLMProvider.OLLAMA: "local_zero_retention",
        LLMProvider.NVIDIA: "nvidia_cloud_api",
    }.get(provider, "anthropic_api")
    logger.info(
        "llm_retention_posture",
        provider=provider.value,
        posture=posture,
        langfuse_enabled=bool(settings.langfuse_public_key and settings.langfuse_secret_key),
        langfuse_capture_io=settings.langfuse_capture_io,
    )


def create_structured_llm(settings: Settings | None = None) -> StructuredLLM | None:
    """Ayarlardaki sağlayıcıya göre LLM istemcisi kurar; ``none`` → ``None``."""
    settings = settings or get_settings()
    provider = LLMProvider(settings.llm_provider)
    if provider is LLMProvider.NONE:
        return None
    tracer = create_llm_tracer(settings)  # Langfuse anahtarları yoksa no-op
    _log_retention_posture(settings, provider)
    if provider is LLMProvider.OLLAMA:
        # Yerel sağlayıcı: anahtar gerektirmez; erişilemezse çağrı anında hata
        # verir (graph RetryPolicy'si devralır) — kurulumda fail-fast yok.
        return OllamaStructuredLLM(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            # Yerel model kendi (düşük) tavanını kullanır; Claude'un 16000'i değil.
            max_output_tokens=settings.ollama_num_predict,
            max_attempts=settings.llm_schema_max_attempts,
            num_ctx=settings.ollama_num_ctx,
            tracer=tracer,
        )
    if provider is LLMProvider.NVIDIA:
        if not settings.nvidia_api_key:
            raise LLMNotConfiguredError(
                "LLM_PROVIDER=nvidia için NVIDIA_API_KEY zorunludur "
                "(nvapi-... anahtarı; ajanları bilinçli kapatmak için LLM_PROVIDER=none)."
            )
        return NvidiaStructuredLLM(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            model=settings.nvidia_model,
            max_output_tokens=settings.nvidia_max_output_tokens,
            max_attempts=settings.llm_schema_max_attempts,
            tracer=tracer,
        )
    if not settings.anthropic_api_key:
        raise LLMNotConfiguredError(
            "LLM_PROVIDER=anthropic için ANTHROPIC_API_KEY zorunludur "
            "(ajanları bilinçli kapatmak için LLM_PROVIDER=none)."
        )
    return AnthropicStructuredLLM(
        api_key=settings.anthropic_api_key,
        model=settings.llm_primary_model,
        max_output_tokens=settings.llm_max_output_tokens,
        max_attempts=settings.llm_schema_max_attempts,
        tracer=tracer,
    )
