"""Membership + Role — kullanıcı↔organizasyon ilişkisi ve RBAC rolü."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import UUIDPKMixin


class Role(StrEnum):
    """RBAC rolleri."""

    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Membership(UUIDPKMixin, TimestampMixin, Base):
    """Bir kullanıcının bir organizasyondaki üyeliği ve rolü."""

    __tablename__ = "membership"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_membership_user_organization"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[Role] = mapped_column(SAEnum(Role, native_enum=False, length=20), nullable=False)
