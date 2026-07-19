"""LLM tracing (Langfuse seam) testleri — sağlayıcı-agnostik, no-op varsayılan (§6.11)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from tenderiq_core.agents.schemas import RequirementExtraction
from tenderiq_core.config import Settings
from tenderiq_core.llm import AnthropicStructuredLLM, LLMTracer, OllamaStructuredLLM
from tenderiq_core.llm.tracing import LangfuseTracer, _LangfuseSpan, create_llm_tracer

_VALID_ITEM = {
    "text": "İstekli ISO 27001 belgesine sahip olmalıdır.",
    "kind": "administrative",
    "is_mandatory": True,
    "source_index": 1,
    "source_quote": "ISO 27001 belgesi zorunludur",
}


# ── Kaydedici sahte tracer (istemci enstrümantasyonunu sınamak için) ──────────


class _RecordingSpan:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(
        self,
        *,
        output: object = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        self.records.append(
            {"output": output, "input_tokens": input_tokens, "output_tokens": output_tokens}
        )


class RecordingTracer(LLMTracer):
    def __init__(self) -> None:
        self.generations: list[dict[str, Any]] = []
        self.span = _RecordingSpan()

    @contextmanager
    def generation(
        self, *, name: str, model: str, system: str, prompt: str
    ) -> Iterator[_RecordingSpan]:
        self.generations.append({"name": name, "model": model, "system": system, "prompt": prompt})
        yield self.span


# ── No-op varsayılan (anahtar yoksa langfuse hiç import edilmez) ──────────────


def test_anahtar_yoksa_no_op_tracer() -> None:
    tracer = create_llm_tracer(Settings(_env_file=None))
    assert type(tracer) is LLMTracer  # LangfuseTracer DEĞİL
    with tracer.generation(name="x", model="m", system="s", prompt="p") as span:
        span.record(output="çıktı", input_tokens=10, output_tokens=5)  # hata vermez
    tracer.flush()


# ── İstemci enstrümantasyonu: her çağrı bir generation + token kaydı ─────────


class _OllamaResponse:
    def __init__(self, content: str | None, *, prompt_tokens: int, eval_tokens: int) -> None:
        self.message = type("_Msg", (), {"content": content})()
        self.prompt_eval_count = prompt_tokens
        self.eval_count = eval_tokens


class _FakeOllamaClient:
    def __init__(self, response: Any) -> None:
        self._response = response

    def chat(self, **_kwargs: Any) -> Any:
        return self._response


def test_ollama_cagrisi_generation_ve_token_kaydeder() -> None:
    tracer = RecordingTracer()
    client = _FakeOllamaClient(
        _OllamaResponse(json.dumps({"items": [_VALID_ITEM]}), prompt_tokens=321, eval_tokens=88)
    )
    llm = OllamaStructuredLLM(
        base_url="http://x",
        model="qwen2.5",
        max_output_tokens=1000,
        max_attempts=1,
        client=client,
        tracer=tracer,
    )
    llm.extract(system="sys", prompt="istem", schema=RequirementExtraction)
    assert tracer.generations[0]["name"] == "RequirementExtraction"
    assert tracer.generations[0]["model"] == "qwen2.5"
    assert tracer.span.records[0]["input_tokens"] == 321
    assert tracer.span.records[0]["output_tokens"] == 88


class _AnthropicUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _AnthropicResponse:
    def __init__(self, parsed: Any) -> None:
        self.stop_reason = "end_turn"
        self.parsed_output = parsed
        self.usage = _AnthropicUsage(1200, 340)


class _FakeAnthropicClient:
    def __init__(self, parsed: Any) -> None:
        self.messages = self
        self._parsed = parsed

    def parse(self, **_kwargs: Any) -> Any:
        return _AnthropicResponse(self._parsed)


def test_anthropic_cagrisi_generation_ve_token_kaydeder() -> None:
    tracer = RecordingTracer()
    expected = RequirementExtraction.model_validate({"items": [_VALID_ITEM]})
    llm = AnthropicStructuredLLM(
        api_key="k",
        model="claude-opus-4-8",
        max_output_tokens=1000,
        max_attempts=1,
        client=_FakeAnthropicClient(expected),
        tracer=tracer,
    )
    llm.extract(system="sys", prompt="istem", schema=RequirementExtraction)
    assert tracer.generations[0]["model"] == "claude-opus-4-8"
    assert tracer.span.records[0]["input_tokens"] == 1200
    assert tracer.span.records[0]["output_tokens"] == 340


# ── KVKK: capture_io kapalıyken doküman içeriği (output) Langfuse'a gitmez ────


class _FakeGeneration:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)


def test_capture_io_kapali_ciktiyi_gondermez() -> None:
    gen = _FakeGeneration()
    span = _LangfuseSpan(gen, capture_io=False)
    span.record(output="DOKÜMAN İÇERİĞİ", input_tokens=100, output_tokens=20)
    assert gen.updates == [{"usage_details": {"input": 100, "output": 20}}]  # output YOK


def test_capture_io_acik_ciktiyi_gonderir() -> None:
    gen = _FakeGeneration()
    span = _LangfuseSpan(gen, capture_io=True)
    span.record(output="çıktı", input_tokens=100, output_tokens=20)
    assert gen.updates[0]["output"] == "çıktı"
    assert gen.updates[0]["usage_details"] == {"input": 100, "output": 20}


class _FakeLangfuseClient:
    def __init__(self) -> None:
        self.generation = _FakeGeneration()
        self.started: list[dict[str, Any]] = []
        self.flushed = 0

    @contextmanager
    def start_as_current_generation(
        self, *, name: str, model: str, input: Any
    ) -> Iterator[_FakeGeneration]:
        self.started.append({"name": name, "model": model, "input": input})
        yield self.generation

    def flush(self) -> None:
        self.flushed += 1


def test_langfuse_tracer_capture_io_kapali_input_gondermez() -> None:
    client = _FakeLangfuseClient()
    tracer = LangfuseTracer(client, capture_io=False)
    with tracer.generation(name="n", model="m", system="s", prompt="p") as span:
        span.record(input_tokens=5, output_tokens=3)
    assert client.started[0]["input"] is None  # istem (doküman) gönderilmedi
    tracer.flush()
    assert client.flushed == 1
