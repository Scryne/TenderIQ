"""Yapı-farkında chunking birim testleri (§6.3)."""

from __future__ import annotations

from itertools import pairwise

import pytest

from tenderiq_core.indexing import chunk_elements
from tenderiq_core.parsing import ElementKind, ParsedElement


def _el(
    text: str,
    *,
    page: int = 1,
    kind: ElementKind = ElementKind.PARAGRAPH,
    section: str | None = None,
) -> ParsedElement:
    return ParsedElement(text=text, page=page, kind=kind, section=section)


def test_bos_girdi_bos_liste_dondurur() -> None:
    assert chunk_elements([]) == []


def test_kucuk_ogeler_tek_chunkta_birikir() -> None:
    chunks = chunk_elements(
        [_el("Birinci madde."), _el("İkinci madde.", page=2), _el("Üçüncü madde.", page=2)]
    )
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.text == "Birinci madde.\nİkinci madde.\nÜçüncü madde."
    assert (chunk.element_start, chunk.element_end) == (0, 2)
    assert (chunk.page_start, chunk.page_end) == (1, 2)
    assert chunk.seq == 0


def test_baslik_yeni_chunk_baslatir_ve_bolum_atar() -> None:
    chunks = chunk_elements(
        [
            _el("1. KAPSAM", kind=ElementKind.HEADING),
            _el("Kapsam açıklaması."),
            _el("2. TEMİNAT", kind=ElementKind.HEADING, page=2),
            _el("Teminat oranı %3'tür.", page=2),
        ]
    )
    assert len(chunks) == 2
    assert chunks[0].text == "1. KAPSAM\nKapsam açıklaması."
    assert chunks[0].section == "1. KAPSAM"
    assert chunks[1].text == "2. TEMİNAT\nTeminat oranı %3'tür."
    assert chunks[1].section == "2. TEMİNAT"
    assert [chunk.seq for chunk in chunks] == [0, 1]


def test_tablo_tek_basina_chunk_olur() -> None:
    chunks = chunk_elements(
        [
            _el("3. BELGELER", kind=ElementKind.HEADING),
            _el("Aşağıdaki tablo geçerlidir."),
            _el("Belge | Adet\nTicaret sicil | 1", kind=ElementKind.TABLE),
            _el("Tablo sonrası açıklama."),
        ]
    )
    assert [chunk.text for chunk in chunks] == [
        "3. BELGELER\nAşağıdaki tablo geçerlidir.",
        "Belge | Adet\nTicaret sicil | 1",
        "Tablo sonrası açıklama.",
    ]
    # Tablo ve devamı, başlığın bölüm bağlamını taşır.
    assert all(chunk.section == "3. BELGELER" for chunk in chunks)


def test_max_chars_yalnizca_oge_sinirinda_boler() -> None:
    paragraphs = [_el(f"Madde {i}: " + "x" * 80) for i in range(5)]
    chunks = chunk_elements(paragraphs, max_chars=200, overlap_chars=20)
    assert len(chunks) > 1
    # Hiçbir öğe ortadan bölünmedi: her chunk, tam öğe metinlerinin birleşimidir.
    reconstructed = [part for chunk in chunks for part in chunk.text.split("\n")]
    assert reconstructed == [element.text for element in paragraphs]
    # Öğe aralıkları bitişik ve kesişimsizdir.
    spans = [(chunk.element_start, chunk.element_end) for chunk in chunks]
    for (_, previous_end), (next_start, _) in pairwise(spans):
        assert next_start == previous_end + 1


def test_tasan_oge_bindirmeli_bolunur() -> None:
    sentences = " ".join(f"Cümle {i} burada biter." for i in range(40))
    chunks = chunk_elements([_el(sentences, page=3)], max_chars=200, overlap_chars=50)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 200 for chunk in chunks)
    # Tüm parçalar aynı kaynak öğeyi ve sayfayı gösterir (citation korunur).
    assert all((chunk.element_start, chunk.element_end) == (0, 0) for chunk in chunks)
    assert all((chunk.page_start, chunk.page_end) == (3, 3) for chunk in chunks)
    # Bindirme: bir parçanın başı, önceki parçanın sonunda da geçer.
    for previous, current in pairwise(chunks):
        assert current.text[:20] in previous.text


def test_tasan_tablo_satir_sinirindan_bindirmesiz_bolunur() -> None:
    rows = [f"Satır {i} | Değer {i}" for i in range(30)]
    chunks = chunk_elements(
        [_el("\n".join(rows), kind=ElementKind.TABLE)], max_chars=120, overlap_chars=50
    )
    assert len(chunks) > 1
    # Satırlar bölünmez ve (bindirme olmadığından) tekrarlanmaz.
    reassembled = [line for chunk in chunks for line in chunk.text.split("\n")]
    assert reassembled == rows


def test_bos_ve_whitespace_ogeler_atlanir() -> None:
    chunks = chunk_elements([_el("   "), _el(""), _el("Gerçek içerik.")])
    assert len(chunks) == 1
    assert chunks[0].text == "Gerçek içerik."
    assert (chunks[0].element_start, chunks[0].element_end) == (2, 2)


def test_parser_bolumu_baslik_yokken_kullanilir() -> None:
    chunks = chunk_elements([_el("Devam eden metin.", section="4. CEZALAR")])
    assert chunks[0].section == "4. CEZALAR"


def test_embedding_input_bolum_baslugunu_one_ekler() -> None:
    chunks = chunk_elements(
        [
            _el("5. SÜRELER", kind=ElementKind.HEADING),
            _el("A" * 100),
            _el("B" * 100),
        ],
        max_chars=110,
        overlap_chars=10,
    )
    # İlk chunk başlıkla başlar → ön ek eklenmez (çift başlık olmaz).
    assert chunks[0].embedding_input() == chunks[0].text
    # Devam chunk'ı bölüm bağlamını embedding girdisinde taşır.
    assert chunks[-1].section == "5. SÜRELER"
    assert chunks[-1].embedding_input() == "5. SÜRELER\n" + chunks[-1].text


@pytest.mark.parametrize(
    ("max_chars", "overlap_chars"),
    [(0, 0), (-5, 0), (100, 100), (100, 150), (100, -1)],
)
def test_gecersiz_parametreler_reddedilir(max_chars: int, overlap_chars: int) -> None:
    with pytest.raises(ValueError, match="olmalıdır"):
        chunk_elements([_el("x")], max_chars=max_chars, overlap_chars=overlap_chars)


def test_dogal_siniri_olmayan_metin_sert_kesilir() -> None:
    chunks = chunk_elements([_el("K" * 500)], max_chars=200, overlap_chars=0)
    assert all(len(chunk.text) <= 200 for chunk in chunks)
    assert "".join(chunk.text for chunk in chunks) == "K" * 500
