"""Embedding soyutlaması (§6.4, ADR-0008): BGE-M3 (OSS) + yönetilen geçiş opsiyonu.

- ``EmbeddingModel`` protokolü: hattın geri kalanı somut modele değil sözleşmeye
  bağlıdır; yönetilen bir sağlayıcıya geçiş yalnızca fabrikaya yeni bir dal
  eklemektir (çağıran kod değişmez).
- ``SentenceTransformerEmbeddingModel``: BGE-M3'ü sentence-transformers ile
  yükler (lazy — modülün import'u hafiftir; ağır yığın yalnız worker imajında
  kurulur, bkz. kök ``embedding`` grubu).
- Vektörler L2-normalize edilir → cosine benzerliği iç çarpıma denk düşer ve
  pgvector ``vector_cosine_ops`` indeksiyle tutarlıdır.
- Boyut sözleşmesi: DB kolonu sabit boyutludur (``vector(EMBEDDING_DIM)``);
  model çıktısı uyuşmazsa sessizce yanlış veri yazmak yerine hata yükselir.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Protocol

from tenderiq_core.config import Settings, get_settings


class EmbeddingProvider(StrEnum):
    """Embedding sağlayıcısı (§6.4 geçiş opsiyonu)."""

    LOCAL = "local"  # BGE-M3, süreç içinde (sentence-transformers)
    MANAGED = "managed"  # yönetilen API — ADR-0008'deki yükseltme yolu, henüz yok


class EmbeddingError(Exception):
    """Embedding katmanı hataları için temel sınıf."""


class EmbeddingNotConfiguredError(EmbeddingError):
    """Embedding bağımlılığı kurulu değil (``uv sync --group embedding``)."""


class EmbeddingDimensionError(EmbeddingError):
    """Model çıktısı, yapılandırılmış vektör boyutuyla uyuşmuyor."""


class EmbeddingModel(Protocol):
    """Embedding sözleşmesi: metin dizisi → aynı sırada yoğun vektörler."""

    @property
    def model_name(self) -> str:
        """Vektörle birlikte kalıcılaştırılan model kimliği."""
        ...

    @property
    def dim(self) -> int:
        """Vektör boyutu (DB kolonuyla aynı olmak zorunda)."""
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Metinleri L2-normalize yoğun vektörlere gömer."""
        ...


class SentenceTransformerEmbeddingModel:
    """BGE-M3 (ya da uyumlu herhangi bir ST modeli) ile yerel embedding."""

    def __init__(self, model_name: str, *, dim: int, batch_size: int = 16) -> None:
        self._model_name = model_name
        self._dim = dim
        self._batch_size = batch_size
        self._model: Any = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._load().encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        result: list[list[float]] = [[float(value) for value in row] for row in vectors]
        for row in result:
            if len(row) != self._dim:
                raise EmbeddingDimensionError(
                    f"{self._model_name} {len(row)} boyutlu vektör üretti; "
                    f"yapılandırılan boyut {self._dim} (EMBEDDING_DIM ve DB "
                    "kolonu birlikte değişmeli — ADR-0008)."
                )
        return result

    def _load(self) -> Any:
        """Modeli ilk kullanımda yükler (süreç başına bir kez; ~2 GB indirme)."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - ortam koşuluna bağlı
                raise EmbeddingNotConfiguredError(
                    "sentence-transformers kurulu değil; embedding yığını yalnız "
                    "worker'da gerekir: `uv sync --group embedding`."
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        return self._model


def create_embedding_model(settings: Settings | None = None) -> EmbeddingModel:
    """Ayarlardaki sağlayıcıya göre embedding modeli kurar."""
    settings = settings or get_settings()
    provider = EmbeddingProvider(settings.embedding_provider)
    if provider is EmbeddingProvider.MANAGED:
        raise NotImplementedError(
            "Yönetilen embedding sağlayıcısı henüz bağlanmadı (ADR-0008 yükseltme "
            "yolu); EMBEDDING_PROVIDER=local kullanın."
        )
    return SentenceTransformerEmbeddingModel(
        settings.embedding_model,
        dim=settings.embedding_dim,
        batch_size=settings.embedding_batch_size,
    )
