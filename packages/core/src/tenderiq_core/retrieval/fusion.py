"""Reciprocal Rank Fusion (RRF): sıralı aday listelerini tek skora birleştirir.

Semantik ve anahtar-kelime yollarının skorları farklı ölçeklerdedir (cosine
benzerliği vs. BM25); RRF skorları değil SIRALARI birleştirdiği için ölçek
normalizasyonu gerektirmez ve iki listede birden geçen adayı doğal olarak
öne çeker (§6.6). ``k`` sabiti alt sıralardaki adayların katkısını yumuşatır
(literatür varsayılanı 60).
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion[K: Hashable](
    rankings: Sequence[Sequence[K]], *, k: int = DEFAULT_RRF_K
) -> dict[K, float]:
    """Sıralı listeleri RRF skorlarına birleştirir: skor = Σ 1/(k + sıra).

    Sıra 1-indekslidir; bir aday birden çok listede geçerse katkıları toplanır.
    Dönen sözlük sırasız skor haritasıdır — nihai sıralama ve deterministik
    eşitlik kırma çağıranın sorumluluğundadır.
    """
    if k < 1:
        raise ValueError("RRF k sabiti pozitif olmalıdır")
    scores: dict[K, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return scores
