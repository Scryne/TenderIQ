"""Invitation — bir organizasyona üye daveti (RLS'siz kimlik tablosu) — 3.3-E-2.

Davet edilen kişi henüz bir hesaba sahip olmayabilir ve accept akışı **kimliksiz**
(unauthenticated) çalışıp token'la kiracı sınırını aşar. Bu yüzden ``Membership`` /
``User`` gibi RLS'siz bir kimlik tablosudur; yönetici uçları aktif organizasyona
**elle** filtreler (bkz. routers/v1/members.py deseni). Token yüksek-entropili ve
opaktır; DB'de yalnızca SHA-256 **özeti** saklanır (sızıntıda tersine çevrilemez,
bkz. services.one_time_tokens güvenlik duruşu — orada Redis, burada kalıcı DB).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import UUIDPKMixin
from tenderiq_core.models.membership import Role


class InvitationStatus(StrEnum):
    """Davetin yaşam döngüsü durumu.

    ``EXPIRED`` saklanmaz — süre aşımı ``expires_at``'ten türetilir; süresi geçmiş
    ``PENDING`` bir davet accept sırasında geçersiz sayılır.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


class Invitation(UUIDPKMixin, TimestampMixin, Base):
    """Bir e-postayı bir organizasyona belirli bir rolle davet eden kayıt."""

    __tablename__ = "invitation"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[Role] = mapped_column(SAEnum(Role, native_enum=False, length=20), nullable=False)
    # Ham token e-postayla gider; burada yalnız SHA-256 özeti (64 hex) tutulur.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[InvitationStatus] = mapped_column(
        SAEnum(InvitationStatus, native_enum=False, length=20), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="SET NULL")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
