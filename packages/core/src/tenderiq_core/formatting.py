"""Sunucu tarafı Türkçe biçimlendirme.

Frontend `Intl.*` kullanır (DESIGN.md Ek B). Sunucu tarafında biçimlendirme
yalnız **kullanıcıya giden metinlerde** (hata mesajı, e-posta) gerekir; sayıyı
ham bayt olarak göstermek ("524288000/524288000") okunabilir değildir.

Ondalık ayırıcı Türkçede **virgül**dür.
"""

from __future__ import annotations

__all__ = ["format_bytes_tr"]

_UNITS = ("B", "KB", "MB", "GB", "TB")


def format_bytes_tr(value: int | None) -> str:
    """Bayt sayısını okunur Türkçe birime çevirir (``None`` → "sınırsız").

    ``None`` bilinçli olarak "sınırsız"a çevrilir: kurumsal kademede kota
    yoktur ve mesajda boş bir sayı görünmesi anlamsız olurdu.
    """
    if value is None:
        return "sınırsız"
    if value < 0:
        value = 0

    size = float(value)
    unit_index = 0
    while size >= 1024 and unit_index < len(_UNITS) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {_UNITS[unit_index]}"
    # Bir ondalık basamak yeter; Türkçe ondalık ayırıcı virgüldür.
    return f"{size:.1f} {_UNITS[unit_index]}".replace(".", ",")
