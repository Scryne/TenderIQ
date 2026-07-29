"""Tek kullanımlık ("disposable") e-posta alan adı filtresi.

Neden var: ücretsiz plan gerçek para harcatır (OCR + LLM). Atılabilir adresle
sınırsız hesap açmak, doğrudan maliyet üretir ve e-posta doğrulama kapısını da
işlevsizleştirir — atılabilir kutu doğrulama bağlantısını da alır.

Neden yerleşik ve kısa bir liste: kapsamlı listeler on binlerce satırdır, sık
değişir ve bakımı bir bağımlılık gerektirir. Buradaki liste **en yaygın**
sağlayıcıları kapsar; kurulum `EXTRA_DISPOSABLE_EMAIL_DOMAINS` ile genişletir.
Amaç mükemmel engelleme değil, **maliyeti caydırıcı** kılmaktır: listeyi aşmak
isteyen kendi alan adını almak zorunda kalır.

Alt alan adları da yakalanır (``mail.mailinator.com`` → ``mailinator.com``).
"""

from __future__ import annotations


def _normalize(email: str) -> str:
    """Kayıt akışıyla aynı normalizasyon (kırpma + küçük harf).

    ``services.auth.normalize_email``i import ETMİYORUZ: bu modül güvenlik
    katmanındadır ve servis katmanına bağımlı olmamalıdır (auth zaten bu modülü
    kullanacak — ters yönde bağımlılık döngü üretirdi).
    """
    return email.strip().lower()


#: Yaygın tek kullanımlık e-posta sağlayıcıları.
DISPOSABLE_DOMAINS: frozenset[str] = frozenset(
    {
        "10minutemail.com",
        "20minutemail.com",
        "burnermail.io",
        "dispostable.com",
        "emailondeck.com",
        "fakeinbox.com",
        "getairmail.com",
        "getnada.com",
        "guerrillamail.com",
        "guerrillamail.info",
        "guerrillamail.net",
        "inboxbear.com",
        "mailcatch.com",
        "maildrop.cc",
        "mailinator.com",
        "mailnesia.com",
        "moakt.com",
        "mohmal.com",
        "mytemp.email",
        "sharklasers.com",
        "spam4.me",
        "temp-mail.io",
        "temp-mail.org",
        "tempail.com",
        "tempmail.dev",
        "tempmailo.com",
        "throwawaymail.com",
        "trashmail.com",
        "yopmail.com",
        "yopmail.fr",
        "yopmail.net",
    }
)


def email_domain(email: str) -> str:
    """E-postanın alan adı (küçük harf); ``@`` yoksa boş string."""
    _, separator, domain = _normalize(email).partition("@")
    return domain if separator else ""


def is_disposable_email(email: str, *, extra_domains: frozenset[str] | None = None) -> bool:
    """Adres tek kullanımlık bir sağlayıcıya mı ait.

    Alt alan adları da yakalanır: ``x.mailinator.com`` engellenirse
    ``mailinator.com`` üzerinden kurulan alt alanlar filtreyi delemez.
    """
    domain = email_domain(email)
    if not domain:
        return False
    blocked = DISPOSABLE_DOMAINS | (extra_domains or frozenset())
    if domain in blocked:
        return True
    return any(domain.endswith(f".{candidate}") for candidate in blocked)
