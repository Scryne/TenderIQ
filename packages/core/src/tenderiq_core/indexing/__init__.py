"""İndeksleme katmanı (§6.3–6.5): chunking + embedding + pgvector yazımı.

Bu paketin import'u hafiftir; ağır embedding yığını (sentence-transformers)
``SentenceTransformerEmbeddingModel`` içinde lazy yüklenir.
"""

from tenderiq_core.indexing.chunking import (
    DEFAULT_MAX_CHARS,
    DEFAULT_OVERLAP_CHARS,
    ChunkDraft,
    chunk_elements,
)
from tenderiq_core.indexing.embedding import (
    EmbeddingDimensionError,
    EmbeddingError,
    EmbeddingModel,
    EmbeddingNotConfiguredError,
    EmbeddingProvider,
    SentenceTransformerEmbeddingModel,
    create_embedding_model,
)

__all__ = [
    "DEFAULT_MAX_CHARS",
    "DEFAULT_OVERLAP_CHARS",
    "ChunkDraft",
    "EmbeddingDimensionError",
    "EmbeddingError",
    "EmbeddingModel",
    "EmbeddingNotConfiguredError",
    "EmbeddingProvider",
    "SentenceTransformerEmbeddingModel",
    "chunk_elements",
    "create_embedding_model",
]
