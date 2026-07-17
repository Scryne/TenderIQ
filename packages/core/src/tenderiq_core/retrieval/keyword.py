"""Anahtar kelime getirimi: TR-farkında tokenizasyon + Okapi BM25 (§6.6, ADR-0012).

Neden süreç-içi BM25 (Postgres FTS değil): getirim kapsamı her zaman TEK
ihalenin dokümanlarıdır (10²–10³ chunk) — korpus belleğe sığar, skorlama
deterministiktir (CI'da tekrarlanabilir) ve Türkçe kıvrımları (İ/I katlama,
madde/paragraf numaraları) bizim kontrolümüzdedir. Kiracılar-arası küresel
arama gerekirse Postgres FTS/GIN yükseltme yolu ADR-0012'de kayıtlıdır.

Gövde ekleri (agglutinatif morfoloji) bilinçli olarak stem'lenmez: yanlış
stem sessiz alaka kaybı üretir; morfolojik eşleşmeyi hibrit hattın semantik
yolu (BGE-M3) taşır, BM25 tam terim/numara isabetinden sorumludur.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

# Türkçe büyük harf katlaması: str.lower() 'I'yı 'i' yapar (yanlış — 'ı' olmalı)
# ve 'İ' için 'i̇' (noktalı kombinasyon) üretir; önce açıkça eşleriz.
_TR_CASEFOLD = str.maketrans({"İ": "i", "I": "ı"})

# Harf/rakam dizileri token'dır; noktalama madde numaralarını böler ("7.5.2" →
# "7","5","2" — sorgu aynı tokenizasyondan geçtiği için eşleşme korunur).
_TOKEN_RE = re.compile(r"[0-9a-zçğıöşü]+")


def tokenize_tr(text: str) -> list[str]:
    """Metni Türkçe-farkında küçük harfe çevirip harf/rakam token'larına böler."""
    return _TOKEN_RE.findall(text.translate(_TR_CASEFOLD).lower())


class Bm25Index:
    """Okapi BM25 indeksi — küçük, salt-okunur, deterministik.

    Korpus yapıcıda bir kez indekslenir; ``top`` çağrıları yan etkisizdir.
    k1/b literatür varsayılanlarıdır; kalibrasyon golden-set ile Sprint 2.4'te.
    """

    def __init__(
        self,
        documents: Sequence[Sequence[str]],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self._k1 = k1
        self._b = b
        self._term_freqs: list[Counter[str]] = [Counter(doc) for doc in documents]
        self._doc_lens = [sum(freq.values()) for freq in self._term_freqs]
        total = sum(self._doc_lens)
        self._avg_len = (total / len(documents)) if documents and total else 1.0
        doc_freq: Counter[str] = Counter()
        for freq in self._term_freqs:
            doc_freq.update(freq.keys())
        n = len(documents)
        # BM25+ değil klasik Okapi; +1 varyantı negatif IDF'i engeller.
        self._idf = {
            term: math.log(1.0 + (n - df + 0.5) / (df + 0.5)) for term, df in doc_freq.items()
        }

    def __len__(self) -> int:
        return len(self._term_freqs)

    def scores(self, query_tokens: Sequence[str]) -> list[float]:
        """Her korpus dokümanı için sorgunun BM25 skorunu döndürür."""
        scores = [0.0] * len(self._term_freqs)
        for term in query_tokens:
            idf = self._idf.get(term)
            if idf is None:
                continue
            for index, freq in enumerate(self._term_freqs):
                tf = freq.get(term, 0)
                if not tf:
                    continue
                norm = 1.0 - self._b + self._b * (self._doc_lens[index] / self._avg_len)
                scores[index] += idf * (tf * (self._k1 + 1.0)) / (tf + self._k1 * norm)
        return scores

    def top(self, query_tokens: Sequence[str], k: int) -> list[tuple[int, float]]:
        """En yüksek skorlu ``k`` dokümanı (indeks, skor) olarak döndürür.

        Sıfır skorlar elenir (hiçbir sorgu terimi geçmeyen chunk aday olmaz);
        eşitlik korpus sırasına göre kırılır (deterministik).
        """
        scores = self.scores(query_tokens)
        ranked = sorted(
            ((index, score) for index, score in enumerate(scores) if score > 0.0),
            key=lambda pair: (-pair[1], pair[0]),
        )
        return ranked[:k]
