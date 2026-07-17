"""Yapı-farkında chunking (§6.3): başlık/madde/tablo sınırına göre bölme.

Naif sabit-pencere chunking gereksinim maddelerini cümle ortasından bölüp anlamı
bozar; burada bölme sınırları dokümanın YAPISINDAN gelir:

- ``HEADING`` yeni bir chunk başlatır ve bölüm bağlamını (``section``) günceller;
- ``TABLE`` tek başına bir chunk olur — satır ortasından birleştirilmez; taşarsa
  satır sınırından parçalanır;
- diğer öğeler (paragraf/madde) ``max_chars``'a kadar birikir ve YALNIZCA öğe
  sınırında bölünür;
- tek başına taşan öğe cümle/satır sınırından, ``overlap_chars`` bindirmeli
  parçalara ayrılır. Yapısal sınırlar arasında bindirme bilinçli olarak yoktur
  (bindirme, naif chunking'in bozduğu bağlamı ancak zorunlu bölmede telafi eder);
  bölümler-arası bağlamı ``section`` metadata'sı taşır.

Her chunk kaynağını bilir: sayfa aralığı + girdi dizisindeki öğe aralığı
(citation-first, §6.2). Girdi, okuma sırasına dizilmiş parse öğeleridir.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from tenderiq_core.parsing.types import ElementKind, ParsedElement

# BGE-M3 8192 token'a kadar destekler; getirim granülerliği için hedef ~400-600
# token ≈ 1800 karakter (Türkçe). Ayarlardan değiştirilebilir (INDEXING_CHUNK_*).
DEFAULT_MAX_CHARS = 1800
DEFAULT_OVERLAP_CHARS = 200

# Zorunlu bölmede tercih edilen kesim sınırları (öncelik sırasıyla).
_CUT_MARKERS = ("\n", ". ", "! ", "? ", "; ", " ")


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """Kalıcılaştırılmaya hazır tek chunk — metin + bölüm + kaynak aralığı."""

    text: str
    seq: int  # doküman içi chunk sırası (0-…)
    section: str | None  # ait olduğu bölüm başlığı
    page_start: int  # kapsanan ilk sayfa (1-indeksli; konumsuz öğede 0)
    page_end: int  # kapsanan son sayfa (dahil)
    element_start: int  # girdi dizisindeki ilk öğe indeksi (dahil)
    element_end: int  # girdi dizisindeki son öğe indeksi (dahil)

    def embedding_input(self) -> str:
        """Gömülecek metin: bölüm başlığı bağlam olarak öne eklenir (§6.3)."""
        if self.section and not self.text.startswith(self.section):
            return f"{self.section}\n{self.text}"
        return self.text


@dataclass
class _Buffer:
    """Aynı chunk'ta biriken ardışık öğeler."""

    section: str | None
    element_start: int
    element_end: int
    parts: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return sum(len(part) for part in self.parts) + max(0, len(self.parts) - 1)


def chunk_elements(
    elements: Sequence[ParsedElement],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[ChunkDraft]:
    """Okuma sırasındaki öğeleri yapı-farkında chunk'lara böler."""
    if max_chars <= 0:
        raise ValueError("max_chars pozitif olmalıdır")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars, [0, max_chars) aralığında olmalıdır")

    chunks: list[ChunkDraft] = []
    buffer: _Buffer | None = None
    current_section: str | None = None

    def flush() -> None:
        nonlocal buffer
        if buffer is not None and buffer.parts:
            chunks.append(
                ChunkDraft(
                    text="\n".join(buffer.parts),
                    seq=len(chunks),
                    section=buffer.section,
                    page_start=min(buffer.pages),
                    page_end=max(buffer.pages),
                    element_start=buffer.element_start,
                    element_end=buffer.element_end,
                )
            )
        buffer = None

    def emit_pieces(pieces: list[str], *, section: str | None, page: int, index: int) -> None:
        for piece in pieces:
            chunks.append(
                ChunkDraft(
                    text=piece,
                    seq=len(chunks),
                    section=section,
                    page_start=page,
                    page_end=page,
                    element_start=index,
                    element_end=index,
                )
            )

    for index, element in enumerate(elements):
        text = element.text.strip()
        if not text:
            continue  # boş/whitespace öğe chunk üretmez
        section = element.section or current_section

        if element.kind is ElementKind.HEADING:
            flush()
            current_section = text
            buffer = _Buffer(section=text, element_start=index, element_end=index)
            buffer.parts.append(text)
            buffer.pages.append(element.page)
            continue

        if element.kind is ElementKind.TABLE:
            flush()
            # Tablo hiçbir öğeyle birleştirilmez; taşarsa satır sınırından ve
            # bindirmesiz bölünür (satır tekrarı tabloyu bozar).
            pieces = _split_text(text, max_chars=max_chars, overlap_chars=0)
            emit_pieces(pieces, section=section, page=element.page, index=index)
            continue

        if len(text) > max_chars:
            flush()
            pieces = _split_text(text, max_chars=max_chars, overlap_chars=overlap_chars)
            emit_pieces(pieces, section=section, page=element.page, index=index)
            continue

        if buffer is not None and buffer.char_count + 1 + len(text) > max_chars:
            flush()
        if buffer is None:
            buffer = _Buffer(section=section, element_start=index, element_end=index)
        buffer.parts.append(text)
        buffer.pages.append(element.page)
        buffer.element_end = index

    flush()
    return chunks


def _split_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    """Taşan metni tercihen doğal sınırlardan, bindirmeli parçalara böler."""
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        cut = _find_cut(text, start, end) if end < len(text) else end
        piece = text[start:cut].strip()
        if piece:
            pieces.append(piece)
        if cut >= len(text):
            break
        # Bindirme geriye taşınır; +1 ilerleme garantisi (sonsuz döngü imkânsız).
        start = max(cut - overlap_chars, start + 1)
    return pieces


def _find_cut(text: str, start: int, end: int) -> int:
    """[start, end) penceresinde en iyi kesim noktası: satır > cümle > boşluk."""
    window = text[start:end]
    for marker in _CUT_MARKERS:
        position = window.rfind(marker)
        if position > 0:
            return start + position + len(marker)
    return end  # doğal sınır yok (tek dev kelime): sert kesim
