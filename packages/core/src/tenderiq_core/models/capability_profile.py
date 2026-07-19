"""CapabilityProfile (firma yetkinlik profili) modeli — kiracı-tekil, RLS (§6.7).

Compliance Checker'ın gap analizinde gereksinimlere karşı değerlendirdiği
girdi: firmanın kendi beyan ettiği yetkinlikler, sertifikalar, iş deneyimi,
mali kapasite vb. Diğer bulgu tablolarından farklı olarak dokümandan çıkarılmaz
— kullanıcı girer (``GET/POST /api/v1/capability-profile``). Kiracı başına en
fazla bir profil vardır (``uq_capability_profile_tenant``); POST upsert'tir.
"""

from __future__ import annotations

from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin


class CapabilityProfile(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir kiracının (firmanın) serbest-metin yetkinlik profili."""

    __tablename__ = "capability_profile"
    # Kiracı başına tek profil: compliance gap analizi tek doğruluk kaynağı okur.
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_capability_profile_tenant"),)

    # Firmanın yetkinlikleri/sertifikaları/deneyimi/mali kapasitesi (serbest metin);
    # Compliance Checker bunu gereksinimlere karşı değerlendirir.
    content: Mapped[str] = mapped_column(Text, nullable=False)
