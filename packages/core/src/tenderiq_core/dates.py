"""Türkçe serbest-metin tarih ayrıştırma.

Çıkarım hattı takvim öğelerini **ham metin** olarak saklar (``TimelineEvent.value_text``):
şartnamedeki ifade ("15 Ağustos 2026", "15.08.2026", "son teklif: 15/08/2026") kaynağa
sadık kalmalı ve ayrıştırılamayan bir değer bulguyu yok etmemeli. Ancak panel gibi
**toplu** görünümler tarihe göre sıralayıp yakın olanları öne almak zorunda; bu da
ayrıştırmayı sunucuda gerektirir (istemcide yapılırsa sunucu anlamlı bir LIMIT
uygulayamaz ve tüm satırları göndermek zorunda kalır).

Sözleşme, web tarafındaki ``lib/format.ts`` → ``parseTrDate`` ile birebir aynıdır:
sayısal biçim önce denenir, sonra ay adı; hiçbiri tutmazsa ``None`` (hata değil —
"tarihi bilinmiyor" meşru bir durumdur ve sıralamada sona düşer).
"""

from __future__ import annotations

import re
from datetime import date

__all__ = ["parse_tr_date"]

# Ay adları küçük harfe Türkçe kurallarıyla indirgenerek aranır (İ→i, I→ı).
_TR_MONTHS: dict[str, int] = {
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12,
}

_NUMERIC = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})")
_NAMED = re.compile(r"(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})")


def _lower_tr(text: str) -> str:
    """Türkçe küçük harf: ``I→ı`` ve ``İ→i`` (varsayılan ``lower()`` ikisini de bozar)."""
    return text.replace("I", "ı").replace("İ", "i").lower()


def parse_tr_date(text: str) -> date | None:
    """Serbest metinden tarih çıkarır; çıkaramazsa ``None`` döner.

    Desteklenen biçimler ``15.08.2026`` / ``15/08/2026`` / ``15-08-2026`` (gün önce —
    TR yazım) ve ``15 Ağustos 2026``. Geçersiz gün/ay birleşimi (``31.02.2026``)
    ayrıştırılamamış sayılır: takvimde var olmayan bir günü uydurmak, sıralamayı
    sessizce yanlışlamaktan iyidir.
    """
    trimmed = text.strip()

    numeric = _NUMERIC.search(trimmed)
    if numeric is not None:
        day, month, year = (int(part) for part in numeric.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    named = _NAMED.search(trimmed)
    if named is not None:
        day_text, month_word, year_text = named.groups()
        named_month = _TR_MONTHS.get(_lower_tr(month_word))
        if named_month is not None:
            try:
                return date(int(year_text), named_month, int(day_text))
            except ValueError:
                return None

    return None
