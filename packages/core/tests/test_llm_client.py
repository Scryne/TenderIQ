"""Şema-zorlamalı LLM istemcisi testleri — sahte Anthropic/Ollama istemcisiyle (§6.7)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from tenderiq_core.agents.schemas import RequirementExtraction
from tenderiq_core.config import Settings
from tenderiq_core.llm import (
    AnthropicStructuredLLM,
    LLMNotConfiguredError,
    LLMRefusalError,
    OllamaStructuredLLM,
    SchemaEnforcementError,
    create_structured_llm,
)

_VALID_ITEM = {
    "text": "İstekli ISO 27001 belgesine sahip olmalıdır.",
    "kind": "administrative",
    "is_mandatory": True,
    "source_index": 1,
    "source_quote": "ISO 27001 belgesi zorunludur",
}


def _validation_error() -> ValidationError:
    """Gerçek bir pydantic doğrulama hatası üretir (SDK'nın fırlattığıyla aynı tip)."""
    try:
        RequirementExtraction.model_validate({"items": [{"bogus": 1}]})
    except ValidationError as exc:
        return exc
    raise AssertionError("doğrulama hatası bekleniyordu")


class _Response:
    def __init__(self, *, stop_reason: str = "end_turn", parsed: Any = None) -> None:
        self.stop_reason = stop_reason
        self.parsed_output = parsed


class FakeAnthropicClient:
    """``messages.parse`` çağrılarını kaydeder; senaryo listesini sırayla oynatır.

    Senaryo öğesi bir istisna ise fırlatılır, değilse yanıt olarak döner.
    """

    def __init__(self, script: list[Any]) -> None:
        self.calls: list[dict[str, Any]] = []
        self._script = list(script)
        self.messages = self

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        step = self._script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


def _llm(client: FakeAnthropicClient, *, max_attempts: int = 3) -> AnthropicStructuredLLM:
    return AnthropicStructuredLLM(
        api_key="test-key",
        model="claude-opus-4-8",
        max_output_tokens=1000,
        max_attempts=max_attempts,
        client=client,
    )


def test_ilk_denemede_gecerli_cikti() -> None:
    expected = RequirementExtraction.model_validate({"items": [_VALID_ITEM]})
    client = FakeAnthropicClient([_Response(parsed=expected)])
    result = _llm(client).extract(system="sys", prompt="istem", schema=RequirementExtraction)
    assert result.items[0].text == _VALID_ITEM["text"]
    assert len(client.calls) == 1
    # Structured output + adaptive thinking istekte olmalı.
    assert client.calls[0]["output_format"] is RequirementExtraction
    assert client.calls[0]["thinking"] == {"type": "adaptive"}


def test_sema_ihlali_reddedilir_ve_yeniden_istenir() -> None:
    expected = RequirementExtraction.model_validate({"items": [_VALID_ITEM]})
    client = FakeAnthropicClient([_validation_error(), _Response(parsed=expected)])
    result = _llm(client).extract(system="sys", prompt="istem", schema=RequirementExtraction)
    assert result.items[0].is_mandatory is True
    assert len(client.calls) == 2
    # İkinci istek, ret gerekçesini (doğrulama hatasını) içermeli.
    retry_messages = client.calls[1]["messages"]
    assert len(retry_messages) == 2
    assert "REDDEDİLDİ" in retry_messages[1]["content"]


def test_israrli_ihlal_tavani_asinca_hata() -> None:
    client = FakeAnthropicClient([_validation_error(), _validation_error()])
    with pytest.raises(SchemaEnforcementError, match="2 denemede"):
        _llm(client, max_attempts=2).extract(
            system="sys", prompt="istem", schema=RequirementExtraction
        )
    assert len(client.calls) == 2


def test_refusal_kalici_hatadir_tekrarlanmaz() -> None:
    client = FakeAnthropicClient([_Response(stop_reason="refusal")])
    with pytest.raises(LLMRefusalError):
        _llm(client).extract(system="sys", prompt="istem", schema=RequirementExtraction)
    assert len(client.calls) == 1  # aynı istem yeniden gönderilmez


def test_gecici_api_hatasi_yukselir() -> None:
    # Rate limit / 5xx istisnaları şema-retry döngüsüne girmez; graph
    # RetryPolicy'si (ADR-0005) devralsın diye olduğu gibi yükselir.
    client = FakeAnthropicClient([RuntimeError("api kesintisi")])
    with pytest.raises(RuntimeError, match="api kesintisi"):
        _llm(client).extract(system="sys", prompt="istem", schema=RequirementExtraction)


def test_fabrika_none_saglayici() -> None:
    settings = Settings(_env_file=None, llm_provider="none")
    assert create_structured_llm(settings) is None


def test_fabrika_anahtarsiz_anthropic_reddedilir() -> None:
    settings = Settings(_env_file=None, llm_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(LLMNotConfiguredError, match="ANTHROPIC_API_KEY"):
        create_structured_llm(settings)


def test_fabrika_anthropic_kurulur() -> None:
    settings = Settings(_env_file=None, llm_provider="anthropic", anthropic_api_key="sk-test")
    llm = create_structured_llm(settings)
    assert llm is not None
    assert llm.model_name == settings.llm_primary_model


# ── Ollama sağlayıcısı (yerel) ───────────────────────────────────────────────


class _OllamaMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _OllamaResponse:
    """``ollama.Client.chat`` dönüşünü taklit eder (``response.message.content``)."""

    def __init__(self, content: str | None) -> None:
        self.message = _OllamaMessage(content)


class FakeOllamaClient:
    """``chat`` çağrılarını kaydeder; senaryo listesini sırayla oynatır."""

    def __init__(self, script: list[Any]) -> None:
        self.calls: list[dict[str, Any]] = []
        self._script = list(script)

    def chat(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        step = self._script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


def _valid_json() -> str:
    return json.dumps({"items": [_VALID_ITEM]})


def _ollama_llm(client: FakeOllamaClient, *, max_attempts: int = 3) -> OllamaStructuredLLM:
    return OllamaStructuredLLM(
        base_url="http://localhost:11434",
        model="qwen2.5:7b-instruct-q5_K_M",
        max_output_tokens=1000,
        max_attempts=max_attempts,
        client=client,
    )


def test_ollama_ilk_denemede_gecerli_cikti() -> None:
    client = FakeOllamaClient([_OllamaResponse(_valid_json())])
    result = _ollama_llm(client).extract(system="sys", prompt="istem", schema=RequirementExtraction)
    assert result.items[0].text == _VALID_ITEM["text"]
    assert len(client.calls) == 1
    # Şema `format` ile zorlanmalı, sıcaklık 0 (deterministik), sistem mesajı ilk.
    assert client.calls[0]["format"] == RequirementExtraction.model_json_schema()
    assert client.calls[0]["options"]["temperature"] == 0
    # Bağlam penceresi açıkça verilmeli (4096 varsayılanı bağlamı kırpar).
    assert client.calls[0]["options"]["num_ctx"] == 8192
    assert client.calls[0]["messages"][0]["role"] == "system"


def test_ollama_sema_ihlali_reddedilir_ve_yeniden_istenir() -> None:
    client = FakeOllamaClient(
        [_OllamaResponse(json.dumps({"items": [{"bogus": 1}]})), _OllamaResponse(_valid_json())]
    )
    result = _ollama_llm(client).extract(system="sys", prompt="istem", schema=RequirementExtraction)
    assert result.items[0].is_mandatory is True
    assert len(client.calls) == 2
    # İkinci istek: sistem + özgün istem + ret gerekçesi.
    retry_messages = client.calls[1]["messages"]
    assert len(retry_messages) == 3
    assert "REDDEDİLDİ" in retry_messages[2]["content"]


def test_ollama_bos_yanit_ihlal_sayilir_ve_yeniden_istenir() -> None:
    client = FakeOllamaClient([_OllamaResponse(None), _OllamaResponse(_valid_json())])
    result = _ollama_llm(client).extract(system="sys", prompt="istem", schema=RequirementExtraction)
    assert result.items[0].text == _VALID_ITEM["text"]
    assert "çıktı boş" in client.calls[1]["messages"][2]["content"]


def test_ollama_israrli_ihlal_tavani_asinca_hata() -> None:
    invalid = json.dumps({"items": [{"bogus": 1}]})
    client = FakeOllamaClient([_OllamaResponse(invalid), _OllamaResponse(invalid)])
    with pytest.raises(SchemaEnforcementError, match="2 denemede"):
        _ollama_llm(client, max_attempts=2).extract(
            system="sys", prompt="istem", schema=RequirementExtraction
        )
    assert len(client.calls) == 2


def test_ollama_gecici_baglanti_hatasi_yukselir() -> None:
    # Bağlantı reddi/5xx şema-retry döngüsüne girmez; graph RetryPolicy'si devralsın.
    client = FakeOllamaClient([ConnectionError("ollama erişilemez")])
    with pytest.raises(ConnectionError, match="ollama erişilemez"):
        _ollama_llm(client).extract(system="sys", prompt="istem", schema=RequirementExtraction)


def test_fabrika_ollama_kurulur_anahtarsiz() -> None:
    settings = Settings(_env_file=None, llm_provider="ollama")
    llm = create_structured_llm(settings)
    assert llm is not None
    assert llm.model_name == settings.ollama_model
