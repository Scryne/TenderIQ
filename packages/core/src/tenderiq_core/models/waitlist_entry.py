"""Bekleme listesi kaydı — ``SIGNUP_MODE=waitlist`` modunda kayıt talebi.

Kiracıya ait DEĞİLDİR (henüz kiracı yoktur), bu yüzden ``TenantMixin`` almaz ve
RLS'ye tabi değildir; ``organization`` gibi kiracı-kök tablolarla aynı sınıftadır.

Neden log değil tablo: bekleme listesi ticari bir varlıktır — sırasıyla davet
gönderilir, dönüşüm ölçülür. Loga yazılan bir talep, log rotasyonuyla kaybolur.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import UUIDPKMixin


class WaitlistEntry(UUIDPKMixin, TimestampMixin, Base):
    """Kayıtların kapalı olduğu dönemde alınan ilgi bildirimi."""

    __tablename__ = "waitlist_entry"

    # Normalize edilmiş e-posta (kayıt akışıyla aynı kural) — aynı adres iki kez
    # sıraya girmesin; tekrar başvuru "zaten listedesiniz" yanıtı alır.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    organization_name: Mapped[str | None] = mapped_column(String(255))
    # Davet gönderildiğinde işaretlenir; boş olanlar sıradakilerdir.
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
