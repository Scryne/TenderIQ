"""Organization (Tenant) modeli — kiracı kökü."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import SoftDeleteMixin, UUIDPKMixin


class Organization(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Kiracı (firma). Tüm kiracı-özel veriler ``tenant_id`` ile buna bağlanır.

    Yumuşak silinebilir (KVKK md. 7 hesap kapatma) ama satırı **kalıcı silinmez**:
    ``TenantMixin`` her şeyi buraya CASCADE ile bağladığından satırı silmek VUK
    gereği saklanması gereken ``subscription``/``usage_record`` ve denetim izini
    de götürürdü. Süpürme kiracı verisini siler, bu satırı anonimleştirip bırakır.
    """

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
