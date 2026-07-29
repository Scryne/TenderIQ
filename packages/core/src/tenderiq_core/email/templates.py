"""Türkçe işlemsel e-posta şablonları (düz metin + HTML).

Kurallar (DESIGN.md Ek B):
- Konu satırında marka önde, eylem net: "TenderIQ — Hesabınızı doğrulayın".
- Cümle düzeni: ilk harf büyük, gerisi küçük. Başlık Stili Yok.
- Sistem dili yok: "token geçersiz" değil "bağlantının süresi dolmuş".
- Her mesajda **tek** birincil eylem; bağlantı düz metinde de tam yazılır
  (e-posta istemcileri HTML'i engelleyebilir).

HTML bilinçli olarak sade: tablo düzeni yok, gömülü görsel yok, harici font
yok. İşlemsel e-postada teslimat oranı estetiğin önündedir; ağır HTML spam
filtresine takılır ve karanlık modda bozulur.
"""

from __future__ import annotations

from html import escape

from tenderiq_core.email.message import EmailKind, EmailMessage

_BRAND = "TenderIQ"

# Tek renk (mürekkep) + tek vurgu. Karanlık modda da okunur olması için zemin
# beyaz bırakılmaz, istemcinin varsayılanı kullanılır.
_HTML_SHELL = """\
<!doctype html>
<html lang="tr">
<body style="margin:0;padding:24px;font-family:-apple-system,Segoe UI,Roboto,
 Helvetica,Arial,sans-serif;font-size:15px;line-height:1.55;color:#18181b">
  <div style="max-width:520px;margin:0 auto">
    <p style="font-size:15px;font-weight:600;letter-spacing:-0.01em;margin:0 0 24px">{brand}</p>
    {body}
    <hr style="border:none;border-top:1px solid #e7e7e9;margin:28px 0 16px">
    <p style="font-size:12px;color:#71717a;margin:0">
      Bu e-postayı beklemiyorsanız görmezden gelebilirsiniz.
    </p>
  </div>
</body>
</html>
"""


def _button(url: str, label: str) -> str:
    return (
        f'<p style="margin:24px 0"><a href="{escape(url, quote=True)}" '
        'style="display:inline-block;background:#18181b;color:#fff;text-decoration:none;'
        'padding:10px 18px;border-radius:6px;font-weight:500">'
        f"{escape(label)}</a></p>"
        f'<p style="font-size:13px;color:#52525b;margin:0">Buton çalışmazsa bu adresi '
        f'tarayıcınıza yapıştırın:<br><span style="word-break:break-all">{escape(url)}</span></p>'
    )


def _paragraphs(*lines: str) -> str:
    return "".join(f'<p style="margin:0 0 12px">{escape(line)}</p>' for line in lines)


def _wrap(body: str) -> str:
    return _HTML_SHELL.format(brand=_BRAND, body=body)


def verify_email(*, to: str, link: str) -> EmailMessage:
    """Kayıt sonrası e-posta doğrulama."""
    text = (
        "Hesabınızı doğrulamak için aşağıdaki bağlantıya gidin:\n\n"
        f"{link}\n\n"
        "Doğrulamadan doküman yükleyemezsiniz. Bağlantı 24 saat geçerlidir."
    )
    html = _wrap(
        _paragraphs(
            "Hesabınızı doğrulamak için aşağıdaki düğmeye basın.",
            "Doğrulamadan doküman yükleyemezsiniz. Bağlantı 24 saat geçerlidir.",
        )
        + _button(link, "E-postamı doğrula")
    )
    return EmailMessage(
        kind=EmailKind.VERIFY_EMAIL,
        to=to,
        subject=f"{_BRAND} — E-posta adresinizi doğrulayın",
        text=text,
        html=html,
    )


def invitation(
    *, to: str, link: str, organization: str, inviter: str | None = None
) -> EmailMessage:
    """Organizasyona üye daveti."""
    who = f"{inviter}, sizi" if inviter else "Sizi"
    text = (
        f"{who} {organization} çalışma alanına davet etti.\n\n"
        f"Daveti kabul etmek için: {link}\n\n"
        "Bağlantı 72 saat geçerlidir."
    )
    html = _wrap(
        _paragraphs(
            f"{who} {organization} çalışma alanına davet etti.",
            "Bağlantı 72 saat geçerlidir.",
        )
        + _button(link, "Daveti kabul et")
    )
    return EmailMessage(
        kind=EmailKind.INVITATION,
        to=to,
        subject=f"{_BRAND} — {organization} çalışma alanına davet edildiniz",
        text=text,
        html=html,
    )


def password_reset(*, to: str, link: str) -> EmailMessage:
    """Parola sıfırlama bağlantısı."""
    text = (
        "Parolanızı sıfırlamak için aşağıdaki bağlantıya gidin:\n\n"
        f"{link}\n\n"
        "Bağlantı 1 saat geçerlidir ve yalnızca bir kez kullanılabilir.\n"
        "Bu talebi siz yapmadıysanız parolanız değişmez; bir şey yapmanız gerekmez."
    )
    html = _wrap(
        _paragraphs(
            "Parolanızı sıfırlamak için aşağıdaki düğmeye basın.",
            "Bağlantı 1 saat geçerlidir ve yalnızca bir kez kullanılabilir.",
            "Bu talebi siz yapmadıysanız parolanız değişmez; bir şey yapmanız gerekmez.",
        )
        + _button(link, "Parolamı sıfırla")
    )
    return EmailMessage(
        kind=EmailKind.PASSWORD_RESET,
        to=to,
        subject=f"{_BRAND} — Parola sıfırlama",
        text=text,
        html=html,
    )


def waitlist_accepted(*, to: str, link: str) -> EmailMessage:
    """Bekleme listesinden sıra gelmesi."""
    text = (
        "Sıra size geldi. Hesabınızı açmak için aşağıdaki bağlantıya gidin:\n\n"
        f"{link}\n\n"
        "Ücretsiz planda ayda 5 doküman analiz edebilirsiniz; kredi kartı istenmez."
    )
    html = _wrap(
        _paragraphs(
            "Sıra size geldi.",
            "Ücretsiz planda ayda 5 doküman analiz edebilirsiniz; kredi kartı istenmez.",
        )
        + _button(link, "Hesabımı aç")
    )
    return EmailMessage(
        kind=EmailKind.WAITLIST_ACCEPTED,
        to=to,
        subject=f"{_BRAND} — Sıra size geldi",
        text=text,
        html=html,
        idempotency_key=f"waitlist:{to}",
    )


def payment_succeeded(
    *, to: str, plan: str, amount_text: str, period_end_text: str, event_id: str
) -> EmailMessage:
    """Tahsilat başarılı."""
    text = (
        f"{plan} planı için ödemeniz alındı: {amount_text}.\n\n"
        f"Aboneliğiniz {period_end_text} tarihine kadar geçerli.\n\n"
        "Faturanız ayrıca iletilecektir."
    )
    html = _wrap(
        _paragraphs(
            f"{plan} planı için ödemeniz alındı: {amount_text}.",
            f"Aboneliğiniz {period_end_text} tarihine kadar geçerli.",
            "Faturanız ayrıca iletilecektir.",
        )
    )
    return EmailMessage(
        kind=EmailKind.PAYMENT_SUCCEEDED,
        to=to,
        subject=f"{_BRAND} — Ödemeniz alındı",
        text=text,
        html=html,
        idempotency_key=f"payment_succeeded:{event_id}",
    )


def payment_failed(
    *, to: str, plan: str, attempt: int, max_attempts: int, link: str, event_id: str
) -> EmailMessage:
    """Tahsilat başarısız — dunning adımı."""
    remaining = max_attempts - attempt
    tail = (
        "Yeniden deneyeceğiz."
        if remaining > 0
        else "Bu son denemeydi; ödeme alınamazsa aboneliğiniz askıya alınacak."
    )
    text = (
        f"{plan} planı için ödemeniz alınamadı ({attempt}/{max_attempts}. deneme). {tail}\n\n"
        f"Kart bilgilerinizi güncellemek için: {link}"
    )
    html = _wrap(
        _paragraphs(
            f"{plan} planı için ödemeniz alınamadı ({attempt}/{max_attempts}. deneme).",
            tail,
        )
        + _button(link, "Ödeme yöntemimi güncelle")
    )
    return EmailMessage(
        kind=EmailKind.PAYMENT_FAILED,
        to=to,
        subject=f"{_BRAND} — Ödemeniz alınamadı",
        text=text,
        html=html,
        idempotency_key=f"payment_failed:{event_id}",
    )


def subscription_canceled(
    *, to: str, plan: str, access_until_text: str, event_id: str
) -> EmailMessage:
    """Abonelik iptali — erişimin ne zaman biteceği net yazılır."""
    text = (
        f"{plan} aboneliğiniz iptal edildi.\n\n"
        f"Verilerinize ve analizlerinize {access_until_text} tarihine kadar erişmeye "
        "devam edebilirsiniz. Bu tarihten sonra hesabınız ücretsiz plana döner.\n\n"
        "Verilerinizi dışa aktarmak isterseniz Ayarlar → Verilerim bölümünü kullanın."
    )
    html = _wrap(
        _paragraphs(
            f"{plan} aboneliğiniz iptal edildi.",
            f"Verilerinize {access_until_text} tarihine kadar erişebilirsiniz; "
            "sonrasında hesabınız ücretsiz plana döner.",
            "Verilerinizi dışa aktarmak isterseniz Ayarlar → Verilerim bölümünü kullanın.",
        )
    )
    return EmailMessage(
        kind=EmailKind.SUBSCRIPTION_CANCELED,
        to=to,
        subject=f"{_BRAND} — Aboneliğiniz iptal edildi",
        text=text,
        html=html,
        idempotency_key=f"subscription_canceled:{event_id}",
    )
