"""E-posta mesajı ve türleri — sağlayıcıdan bağımsız veri modeli.

Mesaj **türü** (``EmailKind``) sadece etiket değil: bastırma (suppression)
kararı türe göre değişir. Pazarlama benzeri bir bildirim bastırılmış adrese
gönderilmezken, **güvenlik kritik** mesajlar (parola sıfırlama) bastırma
listesine rağmen denenir — kullanıcı adresini düzeltmiş olabilir ve onu
hesabından kalıcı olarak kilitlemek, bir bounce kaydından daha ağır bir zarardır.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EmailKind(StrEnum):
    """İşlemsel e-posta türleri."""

    VERIFY_EMAIL = "verify_email"
    INVITATION = "invitation"
    PASSWORD_RESET = "password_reset"  # noqa: S105  (tür adı, parola değil)
    WAITLIST_ACCEPTED = "waitlist_accepted"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    SUBSCRIPTION_STARTED = "subscription_started"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_SUSPENDED = "subscription_suspended"
    SUBSCRIPTION_CANCELED = "subscription_canceled"
    SUBSCRIPTION_RESUMED = "subscription_resumed"
    #: Aylık analiz bütçesi eşiğe yaklaştı / doldu (J.6).
    BUDGET_SOFT_THRESHOLD = "budget_soft_threshold"
    BUDGET_EXCEEDED = "budget_exceeded"
    STORAGE_SOFT_THRESHOLD = "storage_soft_threshold"
    STORAGE_EXCEEDED = "storage_exceeded"


# NOT: Daha önce burada tür bazlı bir "bastırmayı aşan mesajlar" listesi vardı
# (doğrulama + parola sıfırlama). Kaldırıldı: kalıcı bounce almış bir adrese
# OTOMATİK olarak yeniden göndermek, teslim edilemeyeceği KESİN bilinen bir
# mesajı tekrar tekrar denemektir — gönderen alan adının itibarını düşürür ve
# kullanıcıya hiçbir fayda sağlamaz.
#
# Yerine geçen kural: atlama, mesajın TÜRÜNE değil, gönderimin KAYNAĞINA bağlıdır
# (``send_email(..., manual_retry=True)``). Kullanıcı "yeniden gönder" dediyse
# ya da parolasını sıfırlamayı kendisi istediyse deneriz; sistem kendiliğinden
# denemez. Kullanıcı adresini güncellerse bastırma yeni adres için zaten
# geçerli değildir.


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """Gönderilecek tek bir e-posta (sağlayıcıdan bağımsız)."""

    kind: EmailKind
    to: str
    subject: str
    text: str
    html: str
    #: Aynı olayın iki kez e-posta üretmesini engelleyen anahtar. ``None`` ise
    #: tekrar koruması uygulanmaz (ör. kullanıcının açıkça istediği yeniden
    #: gönderim).
    idempotency_key: str | None = None
