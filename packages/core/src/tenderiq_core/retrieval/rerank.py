"""Reranker soyutlaması (§6.6, ADR-0012): cross-encoder + kapatma opsiyonu.

Embedding katmanıyla aynı desen (ADR-0008): hattın geri kalanı ``Reranker``
protokolüne bağlıdır; sağlayıcı değişimi yalnızca fabrikaya yeni bir daldır.
``CrossEncoderReranker`` BGE reranker'ı sentence-transformers ile lazy yükler
(ağır yığın yalnız worker imajında — kök ``embedding`` grubu, torch'u BGE-M3
ile paylaşır). ``RETRIEVAL_RERANKER_PROVIDER=none`` reranker'ı kapatır ve
RRF sırası korunur (hafif ortamlar/testler).
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Protocol

from tenderiq_core.config import Settings, get_settings


class RerankerProvider(StrEnum):
    """Reranker sağlayıcısı."""

    LOCAL = "local"  # cross-encoder, süreç içinde (sentence-transformers)
    NONE = "none"  # reranker yok — RRF fusion sırası nihai sıradır


class RerankError(Exception):
    """Reranker katmanı hataları için temel sınıf."""


class RerankNotConfiguredError(RerankError):
    """Reranker bağımlılığı kurulu değil (``uv sync --group embedding``)."""


class Reranker(Protocol):
    """Rerank sözleşmesi: (sorgu, metinler) → metinlerle aynı sırada skorlar."""

    @property
    def model_name(self) -> str:
        """Loglara/trace'lere yazılan model kimliği."""
        ...

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        """Her metin için sorguyla alaka skoru döndürür (büyük = alakalı)."""
        ...


class CrossEncoderReranker:
    """BGE reranker (ya da uyumlu herhangi bir cross-encoder) ile yerel rerank.

    Skorlar ham logit'tir — sıralama monotoniktir, mutlak değeri sorgular
    arasında karşılaştırılabilir (aynı model) ama olasılık değildir.
    """

    def __init__(self, model_name: str, *, batch_size: int = 16) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._model: Any = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        scores = self._load().predict(
            [(query, text) for text in texts],
            batch_size=self._batch_size,
            convert_to_numpy=True,
        )
        return [float(score) for score in scores]

    def _load(self) -> Any:
        """Modeli ilk kullanımda yükler (süreç başına bir kez; ~1 GB indirme)."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:  # pragma: no cover - ortam koşuluna bağlı
                raise RerankNotConfiguredError(
                    "sentence-transformers kurulu değil; reranker yalnız worker'da "
                    "gerekir: `uv sync --group embedding` (veya "
                    "RETRIEVAL_RERANKER_PROVIDER=none)."
                ) from exc
            self._model = CrossEncoder(self._model_name)
        return self._model


def create_reranker(settings: Settings | None = None) -> Reranker | None:
    """Ayarlardaki sağlayıcıya göre reranker kurar; ``none`` → ``None``."""
    settings = settings or get_settings()
    provider = RerankerProvider(settings.retrieval_reranker_provider)
    if provider is RerankerProvider.NONE:
        return None
    return CrossEncoderReranker(settings.retrieval_reranker_model)
