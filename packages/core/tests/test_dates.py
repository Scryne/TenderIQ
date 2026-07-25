"""``tenderiq_core.dates.parse_tr_date`` birim testleri.

Sözleşme web'deki ``lib/format.ts → parseTrDate`` ile aynı olmalıdır; buradaki
vakalar o davranışı sabitler.
"""

from __future__ import annotations

from datetime import date

import pytest

from tenderiq_core.dates import parse_tr_date


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Sayısal biçimler — TR yazımında gün önce gelir.
        ("15.08.2026", date(2026, 8, 15)),
        ("15/08/2026", date(2026, 8, 15)),
        ("15-08-2026", date(2026, 8, 15)),
        ("1.1.2026", date(2026, 1, 1)),
        # Ay adı biçimi; Türkçe'ye özgü harfler dâhil.
        ("15 Ağustos 2026", date(2026, 8, 15)),
        ("1 Ocak 2027", date(2027, 1, 1)),
        ("30 Eylül 2026", date(2026, 9, 30)),
        ("28 Şubat 2026", date(2026, 2, 28)),
        ("31 Aralık 2026", date(2026, 12, 31)),
        # Büyük/küçük harf duyarsız (İ/I Türkçe kuralıyla indirgenir).
        ("15 AĞUSTOS 2026", date(2026, 8, 15)),
        ("15 ağustos 2026", date(2026, 8, 15)),
        ("1 KASIM 2026", date(2026, 11, 1)),
        # Cümle içinde geçen tarih yakalanır.
        ("Son teklif verme tarihi: 15.08.2026 saat 14:00", date(2026, 8, 15)),
        ("Teklifler 20 Ekim 2026 tarihine kadar sunulur.", date(2026, 10, 20)),
    ],
)
def test_ayristirilabilen_tarihler(text: str, expected: date) -> None:
    assert parse_tr_date(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "belirtilmemiştir",
        "sözleşme imzalanmasından itibaren 30 gün",  # süre, tarih değil
        "31.02.2026",  # takvimde yok
        "15 Foobar 2026",  # tanınmayan ay adı
        "2026",  # yalnız yıl
        "15.08",  # yıl yok
    ],
)
def test_ayristirilamayan_degerler_none_doner(text: str) -> None:
    """Ayrıştırılamama bir hata değildir: "tarihi bilinmiyor" meşru bir durumdur."""
    assert parse_tr_date(text) is None
