"""Getirim katmanı sözleşme tipleri (§6.6).

Korpus girdisi (``CorpusEntry``) Chunk ORM satırının oturumdan bağımsız
izdüşümüdür: korpus bir kez yüklenir, sorgular arasında bellekte yeniden
kullanılır (getirim kapsamı her zaman tek ihalenin dokümanlarıdır).
``RetrievedChunk`` citation zincirini eksiksiz taşır — bulgu → chunk →
öğe ``seq`` aralığı → sayfa/bbox (citation-first, A.4/1).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CorpusEntry:
    """Getirim korpusundaki tek chunk: metin + citation metadata'sı."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    seq: int  # doküman içi chunk sırası (deterministik eşitlik kırıcı)
    text: str
    section: str | None
    page_start: int
    page_end: int
    element_seq_start: int  # kaynak ParsedElement.seq aralığı (dahil)
    element_seq_end: int

    def match_text(self) -> str:
        """Eşlemede kullanılan metin: bölüm başlığı bağlam olarak öne eklenir.

        Embedding girdisiyle aynı kural (``ChunkDraft.embedding_input``) —
        anahtar kelime ve semantik yol aynı metni görür.
        """
        if self.section and not self.text.startswith(self.section):
            return f"{self.section}\n{self.text}"
        return self.text


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Hibrit getirimin tek sonucu: chunk + hangi yoldan/skorla geldiği.

    ``semantic_rank``/``keyword_rank`` 1-indekslidir; chunk o yoldan aday
    listesine girmediyse ``None``. ``score`` nihai sıralama skorudur:
    reranker devredeyse cross-encoder skoru, değilse RRF fusion skoru
    (``fused_score`` ile aynı).
    """

    entry: CorpusEntry
    score: float
    fused_score: float
    semantic_rank: int | None
    keyword_rank: int | None
