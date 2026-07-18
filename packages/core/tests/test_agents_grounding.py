"""Zorunlu grounding testleri (§6.9, ADR-0006) — TR-farkında alıntı doğrulama."""

from __future__ import annotations

import uuid

from tenderiq_core.agents import (
    ContextChunk,
    ElementView,
    GroundingResolution,
    ground_item,
)
from tenderiq_core.agents.grounding import normalize_for_match
from tenderiq_core.retrieval import CorpusEntry, RetrievedChunk

# İki öğeli bir chunk: madde başlığı + gövde (gerçek şartname dili).
_ELEMENTS = {
    10: ElementView(seq=10, page=4, text="Madde 26 - Geçici teminat"),
    11: ElementView(
        seq=11,
        page=4,
        text=(
            "İstekliler teklif ettikleri bedelin %3'ünden az olmamak üzere "
            "kendi belirleyecekleri tutarda geçici teminat vereceklerdir."
        ),
    ),
}


def _chunk() -> ContextChunk:
    text = "\n".join(_ELEMENTS[seq].text for seq in sorted(_ELEMENTS))
    return ContextChunk.from_retrieved(
        RetrievedChunk(
            entry=CorpusEntry(
                chunk_id=uuid.UUID(int=1),
                document_id=uuid.UUID(int=99),
                seq=0,
                text=text,
                section="Madde 26",
                page_start=4,
                page_end=4,
                element_seq_start=10,
                element_seq_end=11,
            ),
            score=1.0,
            fused_score=1.0,
            semantic_rank=1,
            keyword_rank=None,
        )
    )


def _ground(quote: str, *, index: int = 1) -> object:
    return ground_item(
        source_index=index, quote=quote, contexts=[_chunk()], elements_by_seq=_ELEMENTS
    )


def test_birebir_alinti_ogeye_baglanir() -> None:
    source = _ground("teklif ettikleri bedelin %3'ünden az olmamak üzere")
    assert source.resolution is GroundingResolution.ELEMENT
    assert source.element_seq == 11
    assert source.page == 4
    assert source.chunk_id == str(uuid.UUID(int=1))
    assert source.is_grounded


def test_tr_buyuk_harf_katlamasi_eslesir() -> None:
    # LLM alıntıyı büyük harfle döndürse de eşleşme korunur (İ/I katlaması).
    source = _ground("GEÇİCİ TEMİNAT VERECEKLERDİR")
    assert source.resolution is GroundingResolution.ELEMENT
    assert source.element_seq == 11


def test_tipografik_kesme_isareti_eslesir() -> None:
    # Kaynakta düz kesme (%3'ünden), alıntıda tipografik (%3'ünden → ’) olabilir.
    source = _ground("bedelin %3’ünden az olmamak")
    assert source.resolution is GroundingResolution.ELEMENT


def test_bosluk_farklari_eslesir() -> None:
    source = _ground("teklif  ettikleri\nbedelin %3'ünden")
    assert source.resolution is GroundingResolution.ELEMENT


def test_oge_siniri_asan_alinti_chunk_duzeyine_iner() -> None:
    # Alıntı başlık + gövdeyi kapsıyor: tek öğede yok, chunk metninde var.
    source = _ground("Madde 26 - Geçici teminat\nİstekliler teklif ettikleri")
    assert source.resolution is GroundingResolution.CHUNK
    assert source.element_seq == 10  # aralığın ilk öğesine bağlanır
    assert source.page == 4
    assert source.is_grounded


def test_kaynakta_olmayan_alinti_dusuk_guven() -> None:
    source = _ground("kesin teminat oranı %6'dır")
    assert source.resolution is GroundingResolution.UNGROUNDED
    assert source.element_seq is None
    assert not source.is_grounded


def test_gecersiz_kaynak_numarasi_dusuk_guven() -> None:
    assert _ground("geçici teminat", index=7).resolution is GroundingResolution.UNGROUNDED
    assert _ground("geçici teminat", index=0).resolution is GroundingResolution.UNGROUNDED


def test_bos_alinti_dusuk_guven() -> None:
    assert _ground("   ").resolution is GroundingResolution.UNGROUNDED


def test_normalize_tr_katlamasi() -> None:
    assert normalize_for_match("İSTANBUL IĞDIR") == "istanbul ığdır"
    assert normalize_for_match("“tırnak” – tire") == '"tırnak" - tire'
