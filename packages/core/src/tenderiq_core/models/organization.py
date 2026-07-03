"""Organization (Tenant) modeli — kiracı kökü."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import UUIDPKMixin


class Organization(UUIDPKMixin, TimestampMixin, Base):
    """Kiracı (firma). Tüm kiracı-özel veriler ``tenant_id`` ile buna bağlanır."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
