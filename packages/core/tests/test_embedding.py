"""Embedding soyutlaması birim testleri (§6.4, ADR-0008) — model indirmesi gerektirmez."""

from __future__ import annotations

import pytest

from tenderiq_core.config import Settings
from tenderiq_core.indexing import (
    EmbeddingDimensionError,
    SentenceTransformerEmbeddingModel,
    create_embedding_model,
)


class _FakeSentenceTransformer:
    """SentenceTransformer.encode eşleniği — sabit boyutlu vektör üretir."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str], **_kwargs: object) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(index)] * self.dim for index, _ in enumerate(texts)]


def _model_with_fake(
    dim: int, *, fake_dim: int | None = None
) -> tuple[SentenceTransformerEmbeddingModel, _FakeSentenceTransformer]:
    model = SentenceTransformerEmbeddingModel("test/model", dim=dim, batch_size=2)
    fake = _FakeSentenceTransformer(fake_dim if fake_dim is not None else dim)
    model._model = fake  # lazy yükleme atlanır; gerçek model indirilmez
    return model, fake


def test_embed_sira_ve_boyut_korunur() -> None:
    model, fake = _model_with_fake(4)
    vectors = model.embed(["bir", "iki", "üç"])
    assert len(vectors) == 3
    assert all(len(vector) == 4 for vector in vectors)
    assert vectors[1] == [1.0, 1.0, 1.0, 1.0]  # girdi sırası çıktıda korunur
    assert fake.calls == [["bir", "iki", "üç"]]


def test_bos_girdi_model_yuklemeden_bos_doner() -> None:
    model = SentenceTransformerEmbeddingModel("test/model", dim=4)
    assert model.embed([]) == []
    assert model._model is None  # lazy yükleme tetiklenmedi


def test_boyut_uyusmazligi_hata_yukseltir() -> None:
    model, _fake = _model_with_fake(1024, fake_dim=768)
    with pytest.raises(EmbeddingDimensionError, match="768"):
        model.embed(["metin"])


def test_fabrika_ayarlardan_yerel_modeli_kurar() -> None:
    settings = Settings(
        embedding_provider="local",
        embedding_model="BAAI/bge-m3",
        embedding_dim=1024,
        embedding_batch_size=8,
    )
    model = create_embedding_model(settings)
    assert isinstance(model, SentenceTransformerEmbeddingModel)
    assert model.model_name == "BAAI/bge-m3"
    assert model.dim == 1024


def test_fabrika_yonetilen_saglayiciyi_henuz_desteklemez() -> None:
    settings = Settings(embedding_provider="managed")
    with pytest.raises(NotImplementedError, match="ADR-0008"):
        create_embedding_model(settings)


def test_fabrika_gecersiz_saglayiciyi_reddeder() -> None:
    settings = Settings(embedding_provider="baska-bir-sey")
    with pytest.raises(ValueError, match="baska-bir-sey"):
        create_embedding_model(settings)
