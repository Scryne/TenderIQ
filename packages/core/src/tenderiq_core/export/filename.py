"""Rapor dosya adı: ihale başlığından okunur, güvenli bir ad.

Depolama anahtarı temizleyicisi (``storage.safe_key_component``) burada kullanılamaz: "/"yi yol
ayracı sayıp öncesini atar. Türk ihale başlıkları İKN ile başlar ("2026/418732 — İşin adı"),
yani yıl düşer ve ad "418732 _ İşin adı" olurdu. Burada "/" kısa çizgiye çevrilir, uzun tire
ve diğer özel karakterler boşluğa iner, kenarlar ve çift boşluklar temizlenir.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

_SEPARATORS = re.compile(r"[\\/]+")
_UNSAFE = re.compile(r"[^\w.\- ]+")
_SPACES = re.compile(r"\s+")
_EDGES = " .-_"


def report_filename(
    title: str, generated_at: datetime, extension: str, *, max_stem: int = 60
) -> str:
    """``tenderiq-<başlık>-<YYYYMMDD>.<uzantı>`` (başlık boşsa ``tenderiq-rapor-...``)."""
    stem = unicodedata.normalize("NFKC", title)
    stem = _SEPARATORS.sub("-", stem)
    stem = _UNSAFE.sub(" ", stem)
    stem = _SPACES.sub(" ", stem).strip(_EDGES)
    if len(stem) > max_stem:
        cut = stem[:max_stem]
        # Kelime ortasında kesme ("Altyapı…"): sığan son boşlukta bırak.
        stem = cut.rsplit(" ", 1)[0] if " " in cut[max_stem // 2 :] else cut
    stem = stem.rstrip(_EDGES) or "rapor"
    return f"tenderiq-{stem}-{generated_at:%Y%m%d}.{extension}"
