"""Bastırma listesi — kalıcı bounce / şikâyet almış adresler.

Kiracıya ait DEĞİLDİR: bir adres hangi kiracı için gönderildiğinden bağımsız
olarak teslim edilemezdir. Kiracı-kök tablolarla aynı sınıftadır, RLS'ye tabi
değildir.

Neden kalıcı: kalıcı bounce (hard bounce) alan bir adrese göndermeye devam
etmek, gönderen alan adının itibarını (sender reputation) düşürür ve bir süre
sonra **meşru** e-postalar da spam'e düşer. Yani bu tablo, teslimat oranını
koruyan bir yatırımdır.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import UUIDPKMixin


class SuppressionReason(StrEnum):
    """Adresin neden bastırıldığı."""

    #: Kalıcı teslim hatası (adres yok, alan adı çözülemiyor).
    HARD_BOUNCE = "hard_bounce"
    #: Kullanıcı "spam" olarak işaretledi — yasal olarak da göndermeyi kesmeliyiz.
    COMPLAINT = "complaint"
    #: Elle eklendi (destek talebi).
    MANUAL = "manual"


class EmailSuppression(UUIDPKMixin, TimestampMixin, Base):
    """Gönderim yapılmayacak e-posta adresi."""

    __tablename__ = "email_suppression"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    reason: Mapped[SuppressionReason] = mapped_column(
        SAEnum(SuppressionReason, native_enum=False, length=20), nullable=False
    )
    #: Sağlayıcının olay kimliği — aynı webhook iki kez gelirse ayırt edilir.
    provider_event_id: Mapped[str | None] = mapped_column(String(255))
    detail: Mapped[str | None] = mapped_column(Text)
