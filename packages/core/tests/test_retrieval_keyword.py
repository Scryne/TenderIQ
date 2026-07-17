"""TR-farkında tokenizasyon + BM25 testleri (ihale/mevzuat terimleriyle, §6.6)."""

from __future__ import annotations

from tenderiq_core.retrieval import Bm25Index, tokenize_tr

# Gerçek şartname dilini taklit eden mini korpus (idari + teknik karışımı).
CORPUS_TEXTS = [
    "Madde 26 - Geçici teminat: İstekliler teklif ettikleri bedelin %3'ünden az "
    "olmamak üzere geçici teminat vereceklerdir. Geçici teminatın süresi teklif "
    "geçerlilik süresinden en az otuz gün fazla olmalıdır.",
    "Madde 33 - Cezai şart: Yüklenici işi süresinde bitirmediği takdirde geciken "
    "her takvim günü için sözleşme bedelinin %0,05'i oranında gecikme cezası "
    "kesilir.",
    "İstekliler iş deneyim belgesi olarak ilk ilan tarihinden geriye doğru son "
    "beş yıl içinde kabul işlemleri tamamlanan işlerden en az bir iş bitirme "
    "belgesi sunacaktır.",
    "Sistem 7x24 kesintisiz çalışacak; yıllık kullanılabilirlik oranı en az "
    "%99,5 olacaktır. Kesinti durumunda SLA kapsamında müdahale süresi iki "
    "saati aşamaz.",
    "Teklifler İdarenin adresine elden teslim edilebileceği gibi iadeli "
    "taahhütlü posta ile de gönderilebilir.",
]


def _index() -> Bm25Index:
    return Bm25Index([tokenize_tr(text) for text in CORPUS_TEXTS])


class TestTokenizeTr:
    def test_turkce_buyuk_i_katlamasi(self) -> None:
        # 'İ' → 'i', 'I' → 'ı' (str.lower'ın aksine).
        assert tokenize_tr("İSTEKLİ") == ["istekli"]
        assert tokenize_tr("ISLAK IMZA") == ["ıslak", "ımza"]

    def test_noktalama_ve_rakam(self) -> None:
        assert tokenize_tr("Madde 7.5.2 - Geçici teminat (%3)") == [
            "madde",
            "7",
            "5",
            "2",
            "geçici",
            "teminat",
            "3",
        ]

    def test_bos_metin(self) -> None:
        assert tokenize_tr("") == []


class TestBm25:
    def test_gecici_teminat_sorgusu_dogru_maddeyi_bulur(self) -> None:
        index = _index()
        top = index.top(tokenize_tr("geçici teminat oranı"), k=3)
        assert top, "aday dönmedi"
        assert top[0][0] == 0  # Madde 26 - Geçici teminat

    def test_cezai_sart_sorgusu(self) -> None:
        index = _index()
        top = index.top(tokenize_tr("cezai şart gecikme cezası"), k=3)
        assert top[0][0] == 1

    def test_is_deneyim_belgesi_sorgusu(self) -> None:
        index = _index()
        top = index.top(tokenize_tr("iş deneyim belgesi"), k=3)
        assert top[0][0] == 2

    def test_sla_kesinti_sorgusu(self) -> None:
        index = _index()
        top = index.top(tokenize_tr("SLA kesinti müdahale süresi"), k=3)
        assert top[0][0] == 3

    def test_eslesmeyen_sorgu_bos_doner(self) -> None:
        index = _index()
        assert index.top(tokenize_tr("blokzincir kuantum"), k=5) == []

    def test_sifir_skor_aday_olmaz(self) -> None:
        index = _index()
        hits = index.top(tokenize_tr("geçici teminat"), k=10)
        assert all(score > 0.0 for _, score in hits)
        # "geçici teminat" yalnızca 0. dokümanda geçer.
        assert [index_ for index_, _ in hits] == [0]

    def test_deterministik_siralama(self) -> None:
        index = _index()
        assert index.top(tokenize_tr("teklif süresi"), k=5) == index.top(
            tokenize_tr("teklif süresi"), k=5
        )

    def test_bos_korpus(self) -> None:
        empty = Bm25Index([])
        assert len(empty) == 0
        assert empty.top(tokenize_tr("teminat"), k=3) == []
