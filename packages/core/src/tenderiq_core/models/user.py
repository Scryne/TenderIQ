"""User (kullanıcı hesabı) modeli."""

from __future__ import annotations

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import UUIDPKMixin


class User(UUIDPKMixin, TimestampMixin, Base):
    """Kullanıcı hesabı (Membership ile bir/birden çok organizasyona bağlanır).

    Not: ``user`` PostgreSQL'de ayrılmış sözcük olduğundan tablo ``user_account``.
    """

    __tablename__ = "user_account"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # E-posta doğrulaması (Sprint 3.3-D): kayıtta False; doğrulama bağlantısıyla True.
    # Giriş bloke edilmez (yalnız gösterim/işaret); mevcut hesaplar False başlar.
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
