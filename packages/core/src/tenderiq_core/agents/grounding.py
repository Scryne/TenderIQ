"""Zorunlu grounding altyapısı (§6.9, ADR-0006) — tüm ajanların temeli.

İlke (A.4/1, citation-first): kaynağa bağlanamayan hiçbir bulgu gösterilmez.
Ajan çıktısındaki her öğe, bağlam bloğu numarası (``source_index``) + birebir
alıntı (``source_quote``) taşır; bu modül alıntıyı kaynakta DOĞRULAR ve
bulguyu citation zincirine bağlar: bulgu → chunk → ``ParsedElement.seq`` →
sayfa/bbox.

Çözünürlük düzeyleri:
- ``ELEMENT``: alıntı, chunk'ın kaynak aralığındaki TEK bir öğede bulundu —
  en keskin bağ (Faz 3 PDF vurgusu doğrudan bbox'a gider).
- ``CHUNK``: alıntı chunk metninde doğrulandı ama öğe sınırı aştığı için tek
  öğeye indirgenemedi — aralığın ilk öğesine bağlanır (sayfa hâlâ izlenebilir).
- ``UNGROUNDED``: alıntı kaynakta bulunamadı → düşük güven; DB'ye kaynaksız
  yazılır (gözlemlenebilirlik/eval) ama API'den DÖNMEZ.

Alıntı eşlemesi deterministiktir (LLM'siz): TR-farkında büyük harf katlaması
(İ/I — ``retrieval.keyword`` ile aynı kural), tipografik noktalama eşdeğerliği
(’→' vb.) ve boşluk normalizasyonu dışında birebir arama yapılır.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from tenderiq_core.findings import GroundingResolution

__all__ = [
    "ElementView",
    "GroundedSource",
    "GroundingResolution",
    "SourceChunk",
    "ground_item",
    "normalize_for_match",
]

# TR katlaması: str.lower() 'I'→'i' (yanlış) ve 'İ'→'i̇' (kombinasyon) üretir.
_TR_CASEFOLD = str.maketrans({"İ": "i", "I": "ı"})
# LLM çıktısı tipografik işaretleri düzleştirebilir; iki yön de aynı forma iner.
_PUNCT_EQUIV = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
_WS_RE = re.compile(r"\s+")


class GroundedSource(BaseModel):
    """Bulgunun kaynak bağı (graph durumunda taşınır — serileştirilebilir)."""

    resolution: GroundingResolution
    quote: str
    chunk_id: str | None = None
    document_id: str | None = None
    element_seq: int | None = None  # bağlanan ParsedElement.seq (UNGROUNDED → None)
    page: int | None = None

    @property
    def is_grounded(self) -> bool:
        """Kaynak bağı kuruldu mu (ELEMENT veya CHUNK)."""
        return self.resolution is not GroundingResolution.UNGROUNDED


class SourceChunk(Protocol):
    """Grounding'in chunk'tan beklediği alanlar (``ContextChunk`` yapısal uyar)."""

    @property
    def chunk_id(self) -> str: ...
    @property
    def document_id(self) -> str: ...
    @property
    def text(self) -> str: ...
    @property
    def page_start(self) -> int: ...
    @property
    def element_seq_start(self) -> int: ...
    @property
    def element_seq_end(self) -> int: ...


@dataclass(frozen=True, slots=True)
class ElementView:
    """``ParsedElement`` satırının grounding için gereken izdüşümü."""

    seq: int
    page: int
    text: str


def normalize_for_match(text: str) -> str:
    """Alıntı eşlemesi için normalize eder (TR katlama + noktalama + boşluk)."""
    folded = text.translate(_PUNCT_EQUIV).translate(_TR_CASEFOLD).lower()
    return _WS_RE.sub(" ", folded).strip()


def ground_item(
    *,
    source_index: int,
    quote: str,
    contexts: Sequence[SourceChunk],
    elements_by_seq: Mapping[int, ElementView],
) -> GroundedSource:
    """Tek bir ajan öğesini kaynağına bağlar (bağlanamazsa UNGROUNDED).

    ``source_index`` 1-indekslidir (istemdeki ``[KAYNAK n]`` numarası).
    """
    normalized_quote = normalize_for_match(quote)
    if not normalized_quote or not (1 <= source_index <= len(contexts)):
        return GroundedSource(resolution=GroundingResolution.UNGROUNDED, quote=quote)
    chunk = contexts[source_index - 1]

    # 1) Öğe düzeyi: chunk'ın kaynak aralığındaki tek öğede birebir ara.
    for seq in range(chunk.element_seq_start, chunk.element_seq_end + 1):
        element = elements_by_seq.get(seq)
        if element is not None and normalized_quote in normalize_for_match(element.text):
            return GroundedSource(
                resolution=GroundingResolution.ELEMENT,
                quote=quote,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                element_seq=seq,
                page=element.page,
            )

    # 2) Chunk düzeyi: öğe sınırı aşan alıntı chunk metninde doğrulanır.
    if normalized_quote in normalize_for_match(chunk.text):
        first = elements_by_seq.get(chunk.element_seq_start)
        return GroundedSource(
            resolution=GroundingResolution.CHUNK,
            quote=quote,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            element_seq=chunk.element_seq_start,
            page=first.page if first is not None else chunk.page_start,
        )

    return GroundedSource(resolution=GroundingResolution.UNGROUNDED, quote=quote)
