"""Kayıt modu (``SIGNUP_MODE``) ve bekleme listesi.

Üç mod da çalışır durumdadır; ürünü kapalı betaya geri almak bir ortam
değişkeni değişikliğidir, kod değişikliği değil:

- ``open`` — herkes hesap açar (varsayılan).
- ``invite_only`` — kayıt ucu reddeder; **davet akışı çalışmaya devam eder**
  (davetli kullanıcı `POST /invitations/accept` ile katılır).
- ``waitlist`` — talep listeye alınır, hesap açılmaz.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.models import WaitlistEntry
from tenderiq_core.services.auth import normalize_email

#: PostgreSQL benzersizlik ihlali (unique_violation).
_UNIQUE_VIOLATION = "23505"

SIGNUP_OPEN = "open"
SIGNUP_INVITE_ONLY = "invite_only"
SIGNUP_WAITLIST = "waitlist"

SIGNUP_MODES = frozenset({SIGNUP_OPEN, SIGNUP_INVITE_ONLY, SIGNUP_WAITLIST})


async def add_to_waitlist(
    session: AsyncSession,
    *,
    email: str,
    full_name: str | None = None,
    organization_name: str | None = None,
) -> bool:
    """Adresi bekleme listesine ekler. Zaten varsa ``False`` döner (idempotent).

    Yanıt metni bu bayrağa göre değişir ama **her iki durumda da başarı**
    döndürülür: "bu adres listede yok" ile "listede" arasındaki farkı 4xx ile
    ayırmak, kayıtlı adresleri numaralandırmaya açık bir yan kanal olurdu.
    """
    normalized = normalize_email(email)
    existing = await session.scalar(select(WaitlistEntry).where(WaitlistEntry.email == normalized))
    if existing is not None:
        return False
    session.add(
        WaitlistEntry(
            email=normalized,
            full_name=full_name,
            organization_name=organization_name,
        )
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        # YALNIZCA benzersizlik ihlali yutulur (SQLSTATE 23505): ön-kontrol ile
        # INSERT arasındaki yarışta kısıt DB'de yakalanır ve çağıran için sonuç
        # aynıdır — adres listededir.
        #
        # Geniş bir `except IntegrityError` tehlikelidir: bu fonksiyonun ilk
        # sürümü öyleydi ve eksik bir sunucu varsayılanı yüzünden oluşan
        # NOT NULL ihlalini "zaten listede" diye raporladı — kayıt sessizce
        # kayboluyordu ve uç 202 dönüyordu.
        if getattr(exc.orig, "sqlstate", None) != _UNIQUE_VIOLATION:
            raise
        return False
    return True
