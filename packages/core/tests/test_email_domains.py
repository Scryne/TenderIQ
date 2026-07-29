"""Tek kullanımlık e-posta alan adı filtresi (§4 kötüye kullanım koruması)."""

from __future__ import annotations

import pytest

from tenderiq_core.security.email_domains import email_domain, is_disposable_email


@pytest.mark.parametrize(
    "email",
    ["a@mailinator.com", "A@MAILINATOR.COM", "  x@yopmail.com  ", "b@temp-mail.org"],
)
def test_yaygin_saglayicilar_engellenir(email: str) -> None:
    assert is_disposable_email(email)


def test_alt_alan_adlari_da_yakalanir() -> None:
    """Aksi hâlde filtre tek bir alt alan adıyla delinirdi."""
    assert is_disposable_email("kullanici@mail.mailinator.com")


@pytest.mark.parametrize("email", ["ad.soyad@firma.com.tr", "x@gmail.com", "y@outlook.com"])
def test_gercek_adresler_engellenmez(email: str) -> None:
    assert not is_disposable_email(email)


def test_kurulum_listeyi_genisletebilir() -> None:
    assert is_disposable_email(
        "x@ornek-atilabilir.com", extra_domains=frozenset({"ornek-atilabilir.com"})
    )
    assert not is_disposable_email("x@ornek-atilabilir.com")


def test_bozuk_adres_engel_uretmez() -> None:
    """Biçim doğrulaması pydantic'in işi; bu filtre yanlış pozitif üretmemeli."""
    assert email_domain("alansiz") == ""
    assert not is_disposable_email("alansiz")
