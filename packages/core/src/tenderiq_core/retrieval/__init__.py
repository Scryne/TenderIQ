"""Getirim katmanı (§6.6, ADR-0012): hibrit getirim + reranker.

Bu paketin import'u hafiftir; ağır cross-encoder yığını
``CrossEncoderReranker`` içinde lazy yüklenir (embedding katmanıyla aynı desen).
"""

from tenderiq_core.retrieval.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from tenderiq_core.retrieval.keyword import Bm25Index, tokenize_tr
from tenderiq_core.retrieval.rerank import (
    CrossEncoderReranker,
    Reranker,
    RerankerProvider,
    RerankError,
    RerankNotConfiguredError,
    create_reranker,
)
from tenderiq_core.retrieval.semantic import semantic_search
from tenderiq_core.retrieval.service import (
    HybridRetriever,
    RetrievalCorpus,
    SemanticSearchFn,
    load_corpus,
)
from tenderiq_core.retrieval.types import CorpusEntry, RetrievedChunk

__all__ = [
    "DEFAULT_RRF_K",
    "Bm25Index",
    "CorpusEntry",
    "CrossEncoderReranker",
    "HybridRetriever",
    "RerankError",
    "RerankNotConfiguredError",
    "Reranker",
    "RerankerProvider",
    "RetrievalCorpus",
    "RetrievedChunk",
    "SemanticSearchFn",
    "create_reranker",
    "load_corpus",
    "reciprocal_rank_fusion",
    "semantic_search",
    "tokenize_tr",
]
