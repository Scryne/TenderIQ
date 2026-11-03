"""LLM istemcilerinin GERÇEK SDK üzerinden tel (HTTP) sözleşmesi — sahte taşıyıcıyla, ağ yok.

``test_llm_client.py`` istemciyi tamamen sahteyle değiştirir; SDK'nın kendisi orada hiç
koşmaz. Bu dosya gerçek ``anthropic.Anthropic`` / ``openai.OpenAI`` istemcisini kurar ve
yalnız HTTP katmanını ``httpx2.MockTransport`` ile keser. Böylece bir SDK majör
yükseltmesi (ör. anthropic 1.x → 2.x, API sürümü ``2026-10-21``) şunları sessizce
değiştiremez:

- Anthropic isteğinin gövdesi (``output_config.format`` + adaptive thinking),
- yeni API sürümünde 400 dönen örnekleme parametrelerinin (``temperature``/``top_p``/
  ``top_k``) gönderilmemesi,
- ayrıştırma sonucunun bizim dallarımıza (refusal / şema ihlali → yeniden iste) akışı.

Sürüm başlığı bilinçli olarak sabitlenir: bir sonraki SDK majörü API sürümünü yine
değiştirirse bu test kırılır ve geçiş notları okunmadan yükseltme birleşemez.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import anthropic
import httpx2
import openai
import pytest

from tenderiq_core.agents.schemas import RequirementExtraction
from tenderiq_core.llm import (
    AnthropicStructuredLLM,
    LLMRefusalError,
    NvidiaStructuredLLM,
)

_VALID = {
    "items": [
        {
            "text": "İstekli ISO 27001 belgesine sahip olmalıdır.",
            "kind": "administrative",
            "is_mandatory": True,
            "source_index": 1,
            "source_quote": "ISO 27001 belgesi zorunludur",
        }
    ]
}

# anthropic 2.x'in gönderdiği API sürümü.
# Geçiş notu: platform.claude.com/docs/en/api/migration-2026-10-21
_ANTHROPIC_API_VERSION = "2026-10-21"
_SAMPLING_PARAMS = {"temperature", "top_p", "top_k"}


class _Recorder:
    """İstekleri kaydeder, yanıt listesini sırayla oynatır."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.requests: list[httpx2.Request] = []
        self._responses = list(responses)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(200, json=self._responses.pop(0))

    def body(self, index: int) -> dict[str, Any]:
        parsed: dict[str, Any] = json.loads(self.requests[index].content)
        return parsed


def _anthropic_message(*, stop_reason: str, text: str | None) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "thinking", "thinking": "...", "signature": "s"}]
    if text is not None:
        content.append({"type": "text", "text": text})
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-test",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 11, "output_tokens": 22},
    }


def _anthropic_llm(handler: Callable[[httpx2.Request], httpx2.Response]) -> AnthropicStructuredLLM:
    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicStructuredLLM(
        api_key="test-key",
        model="claude-test",
        max_output_tokens=1000,
        max_attempts=3,
        client=client,
    )


def test_anthropic_parse_istek_govdesi_ve_basliklari() -> None:
    rec = _Recorder([_anthropic_message(stop_reason="end_turn", text=json.dumps(_VALID))])
    result = _anthropic_llm(rec).extract(
        system="sistem", prompt="istem", schema=RequirementExtraction
    )

    assert result.items[0].source_quote == "ISO 27001 belgesi zorunludur"
    assert len(rec.requests) == 1
    request = rec.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/messages"
    assert request.headers["anthropic-version"] == _ANTHROPIC_API_VERSION
    # 2.x anahtarı Authorization: Bearer ile taşır (X-Api-Key artık gönderilmez).
    assert request.headers["authorization"].startswith("Bearer ")
    assert "x-api-key" not in request.headers

    body = rec.body(0)
    assert set(body) == {"model", "max_tokens", "system", "thinking", "messages", "output_config"}
    assert not _SAMPLING_PARAMS & set(body)  # 2026-10-21'de 400 döner
    assert body["thinking"] == {"type": "adaptive"}
    assert body["messages"] == [{"role": "user", "content": "istem"}]
    fmt = body["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["additionalProperties"] is False
    assert "items" in fmt["schema"]["required"]


def test_anthropic_kesik_cikti_sdk_dogrulamasindan_yeniden_istenir() -> None:
    rec = _Recorder(
        [
            _anthropic_message(stop_reason="max_tokens", text='{"items": [{"text": "yar'),
            _anthropic_message(stop_reason="end_turn", text=json.dumps(_VALID)),
        ]
    )
    result = _anthropic_llm(rec).extract(system="s", prompt="istem", schema=RequirementExtraction)

    assert result.items[0].is_mandatory is True
    assert len(rec.requests) == 2
    retry_messages = rec.body(1)["messages"]
    assert retry_messages[0] == {"role": "user", "content": "istem"}
    assert "REDDEDİLDİ" in retry_messages[1]["content"]
    assert not _SAMPLING_PARAMS & set(rec.body(1))


def test_anthropic_refusal_tek_istekte_kalici_hata() -> None:
    rec = _Recorder([_anthropic_message(stop_reason="refusal", text=None)])
    with pytest.raises(LLMRefusalError):
        _anthropic_llm(rec).extract(system="s", prompt="istem", schema=RequirementExtraction)
    assert len(rec.requests) == 1


def test_anthropic_metin_blogu_yoksa_yeniden_istenir() -> None:
    rec = _Recorder(
        [
            _anthropic_message(stop_reason="end_turn", text=None),
            _anthropic_message(stop_reason="end_turn", text=json.dumps(_VALID)),
        ]
    )
    result = _anthropic_llm(rec).extract(system="s", prompt="istem", schema=RequirementExtraction)
    assert len(result.items) == 1
    assert len(rec.requests) == 2


def _chat_completion(*, finish_reason: str, content: str | None) -> dict[str, Any]:
    return {
        "id": "c1",
        "object": "chat.completion",
        "created": 1,
        "model": "nim-test",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content, "refusal": None},
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
    }


def _nvidia_llm(handler: Callable[[httpx2.Request], httpx2.Response]) -> NvidiaStructuredLLM:
    client = openai.OpenAI(
        api_key="nvapi-test",
        base_url="https://nim.invalid/v1",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return NvidiaStructuredLLM(
        api_key="nvapi-test",
        base_url="https://nim.invalid/v1",
        model="nim-test",
        max_output_tokens=500,
        max_attempts=3,
        client=client,
    )


def test_openai_uyumlu_istek_govdesi() -> None:
    rec = _Recorder([_chat_completion(finish_reason="stop", content=json.dumps(_VALID))])
    result = _nvidia_llm(rec).extract(system="sistem", prompt="istem", schema=RequirementExtraction)

    assert result.items[0].kind == "administrative"
    request = rec.requests[0]
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["authorization"].startswith("Bearer ")
    body = rec.body(0)
    assert body["temperature"] == 0
    assert body["max_tokens"] == 500
    assert body["messages"] == [
        {"role": "system", "content": "sistem"},
        {"role": "user", "content": "istem"},
    ]
    rf = body["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "RequirementExtraction"
    assert rf["json_schema"]["strict"] is True


def test_openai_uyumlu_content_filter_kalici_hata() -> None:
    rec = _Recorder([_chat_completion(finish_reason="content_filter", content=None)])
    with pytest.raises(LLMRefusalError):
        _nvidia_llm(rec).extract(system="s", prompt="istem", schema=RequirementExtraction)
    assert len(rec.requests) == 1


def test_anthropic_refusal_bos_metin_blogu_ile_kalici_hata() -> None:
    """Ret + boş metin bloğu: SDK ayrıştırması ``""`` üzerinde patlar (ValidationError).

    Bu durumda bile sonuç ``LLMRefusalError`` olmalı ve istem tekrarlanmamalıdır;
    aksi hâlde ret şema ihlali sanılıp ``max_attempts`` kez yeniden istenir.
    """
    rec = _Recorder([_anthropic_message(stop_reason="refusal", text="") for _ in range(3)])
    with pytest.raises(LLMRefusalError):
        _anthropic_llm(rec).extract(system="s", prompt="istem", schema=RequirementExtraction)
    assert len(rec.requests) == 1
