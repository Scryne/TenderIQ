"""E-posta kanonikleştirme birim testleri (D-03).

Kayıt, giriş, davet ve oran-sınırlama anahtarları AYNI kanonik biçimi kullanmak
zorundadır; ayrışırlarsa kullanıcı parolasını sıfırlayamaz (kayıt ham değerle,
arama normalize değerle yapılırdı) ve yalnızca harf durumuyla ayrışan mükerrer
hesaplar oluşabilir.
"""

from __future__ import annotations

import pytest

from tenderiq_core.services.auth import normalize_email
from tenderiq_core.services.invitations import _normalize_email as invitation_normalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Berkay.Test@Example.COM", "berkay.test@example.com"),
        ("  bosluklu@example.com  ", "bosluklu@example.com"),
        ("ZATEN@example.com", "zaten@example.com"),
        ("kucuk@example.com", "kucuk@example.com"),
    ],
)
def test_normalize_email_kanonik_bicim(raw: str, expected: str) -> None:
    assert normalize_email(raw) == expected


def test_normalize_idempotenttir() -> None:
    once = normalize_email("Karisik@Ornek.Com")
    assert normalize_email(once) == once


def test_davet_akisi_ayni_kurali_kullanir() -> None:
    """Davet ve hesap kimliği ayrışırsa davet edilen kullanıcı eşleşmezdi."""
    raw = "Davet.Edilen@Example.COM"
    assert invitation_normalize(raw) == normalize_email(raw)


def test_pydantic_email_str_yalniz_alan_adini_kucultur() -> None:
    """Normalizasyonun neden gerekli olduğunun kaydı (regresyon koruması).

    ``EmailStr`` yalnız domain'i küçültür; local-part'ı olduğu gibi bırakır. Bu
    davranışa güvenip normalizasyonu atlamak D-03'ü geri getirirdi.
    """
    from pydantic import BaseModel, EmailStr

    class _Body(BaseModel):
        email: EmailStr

    parsed = _Body(email="Berkay.Test@Example.COM").email
    assert parsed == "Berkay.Test@example.com"  # local-part korunur
    assert normalize_email(parsed) == "berkay.test@example.com"
