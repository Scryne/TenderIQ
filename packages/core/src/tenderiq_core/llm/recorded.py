"""Kayıtlı yanıt kipi (``LLM_PROVIDER=recorded``) — dış servis çağırmayan, deterministik LLM.

Ne için: yerel geliştirme, demo ve tarayıcı sınamasında analiz hattını (ayrıştır → indeksle →
çıkar → incele) UÇTAN UCA koşturmak; anahtar, ağ ve maliyet olmadan. Yalnız
``ENVIRONMENT=development``da açılır (bkz. ``Settings._enforce_recorded_llm_dev_only``):
kayıtlı yanıt üretimde gerçek analiz gibi görünür ve kimse fark etmezdi.

Nasıl: istemin hash'ine bağlı bir "kayıt" getirim sırası değişince kırılırdı. Bunun yerine
kayıt dosyası, şema başına BİREBİR alıntılı öğeler taşır. Sağlayıcı, istemdeki
``[KAYNAK n]`` bloklarını ayrıştırır ve alıntısı bir blokta GERÇEKTEN geçen öğeleri, o bloğun
numarasıyla döndürür. Böylece:

- çıktı gerçek bir modelinkiyle aynı yoldan geçer: şema doğrulaması + ``agents.grounding``,
- bağlamda kanıtı olmayan öğe asla üretilmez (uydurma alıntı yok),
- aynı belge ve aynı kayıt → aynı bulgular, getirim sırasından bağımsız.

Uygunluk (``ComplianceCheck``) için kayıt, gereksinim metninde geçen bir anahtar ve profilde
aranan ifadelerle durum seçer: profil ifadeyi içeriyorsa ``met_*``, içermiyorsa ``unmet_*``.

Kayıt biçimi (JSON)::

    {
      "RequirementExtraction": [{"source_quote": "...", "text": "...", "kind": "technical",
                                 "is_mandatory": true}],
      "RiskExtraction": [...], "DeliverableExtraction": [...], "TimelineExtraction": [...],
      "ComplianceCheck": [{"requirement_contains": "27001", "profile_contains": ["27001"],
                           "met_rationale": "...", "unmet_rationale": "..."}]
    }
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from tenderiq_core.agents.grounding import normalize_for_match
from tenderiq_core.logging import get_logger

SchemaT = TypeVar("SchemaT", bound=BaseModel)

logger = get_logger(__name__)

_BLOCK_RE = re.compile(r"^\[KAYNAK (\d+)\][^\n]*$", re.MULTILINE)
_REQ_LINE_RE = re.compile(r"^(\d+)\. (.+)$", re.MULTILINE)
_PROFILE_RE = re.compile(r"FİRMA YETKİNLİK PROFİLİ:\n(.*?)\n\nGEREKSİNİMLER", re.DOTALL)


class RecordedLLMError(RuntimeError):
    """Kayıt dosyası okunamadı ya da biçimi bozuk."""


def parse_context_blocks(prompt: str) -> dict[int, str]:
    """İstemdeki ``[KAYNAK n]`` bloklarını ``{n: metin}`` olarak çıkarır."""
    matches = list(_BLOCK_RE.finditer(prompt))
    blocks: dict[int, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(prompt)
        blocks[int(match.group(1))] = prompt[match.end() : end]
    return blocks


class RecordedStructuredLLM:
    """``StructuredLLM`` protokolünü kayıt dosyasından karşılar (ağ yok, maliyet yok)."""

    def __init__(self, *, recordings: dict[str, list[dict[str, Any]]], source: str) -> None:
        self._recordings = recordings
        self._source = source

    @classmethod
    def from_path(cls, path: Path) -> RecordedStructuredLLM:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecordedLLMError(f"Kayıtlı LLM yanıt dosyası okunamadı: {path} ({exc})") from exc
        if not isinstance(data, dict):
            raise RecordedLLMError(f"Kayıt dosyası şema adı → öğe listesi olmalı: {path}")
        # "_" ile başlayan anahtarlar açıklamadır (JSON'da yorum yok).
        recordings = {k: v for k, v in data.items() if not k.startswith("_")}
        if not all(isinstance(v, list) for v in recordings.values()):
            raise RecordedLLMError(f"Kayıt dosyası şema adı → öğe listesi olmalı: {path}")
        return cls(recordings=recordings, source=path.name)

    @property
    def model_name(self) -> str:
        return f"recorded:{self._source}"

    def extract(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        entries = self._recordings.get(schema.__name__, [])
        if schema.__name__ == "ComplianceCheck":
            items = self._compliance(prompt, entries)
        else:
            items = self._grounded_items(prompt, entries)
        logger.info(
            "kayitli_llm_yaniti",
            schema=schema.__name__,
            recorded=len(entries),
            returned=len(items),
            source=self._source,
        )
        # Gerçek sağlayıcılarla aynı kapı: şemaya uymayan kayıt sessizce geçmez.
        return schema.model_validate({"items": items})

    @staticmethod
    def _grounded_items(prompt: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        blocks = {n: normalize_for_match(text) for n, text in parse_context_blocks(prompt).items()}
        items: list[dict[str, Any]] = []
        for entry in entries:
            quote = str(entry.get("source_quote", ""))
            needle = normalize_for_match(quote)
            if not needle:
                continue
            index = next((n for n, text in sorted(blocks.items()) if needle in text), None)
            if index is None:
                continue  # bağlamda kanıtı yok → üretilmez
            items.append({**entry, "source_index": index, "source_quote": quote})
        return items

    @staticmethod
    def _compliance(prompt: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        profile_match = _PROFILE_RE.search(prompt)
        profile = normalize_for_match(profile_match.group(1)) if profile_match else ""
        requirements = {int(m.group(1)): m.group(2) for m in _REQ_LINE_RE.finditer(prompt)}
        items: list[dict[str, Any]] = []
        for index, text in sorted(requirements.items()):
            normalized = normalize_for_match(text)
            entry = next(
                (
                    e
                    for e in entries
                    if normalize_for_match(str(e.get("requirement_contains", ""))) in normalized
                ),
                None,
            )
            if entry is None:
                continue
            wanted = [normalize_for_match(str(p)) for p in entry.get("profile_contains", [])]
            met = bool(wanted) and any(w in profile for w in wanted)
            items.append(
                {
                    "requirement_index": index,
                    "status": "met" if met else str(entry.get("unmet_status", "unmet")),
                    "rationale": str(entry["met_rationale" if met else "unmet_rationale"]),
                }
            )
        return items

    def flush(self) -> None:
        """Gerçek istemcilerle aynı arayüz (iz gönderimi yok)."""
