"""Subscription — kiracının abonelik planı ve durumu (kiracı-özel, RLS)."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin


class SubscriptionStatus(StrEnum):
    """Abonelik durumu."""

    ACTIVE = "active"
    PAST_DUE = "past_due"  # ödeme başarısız — kota dondurulabilir (3.3-B)
    CANCELED = "canceled"
    TRIALING = "trialing"


class Subscription(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir kiracının tek aktif aboneliği (kiracı başına bir satır).

    Satır yoksa erişim anında varsayılan FREE olarak oluşturulur
    (``services.quota.get_or_create_subscription``); böylece bu migration'dan
    önce açılmış kiracılar da sorunsuz çalışır. Limitler burada tutulmaz —
    ``plan`` kademesinden ``tenderiq_core.billing.plans`` üzerinden okunur.
    Ödeme sağlayıcı alanları (``provider*``) Sprint 3.3-B'de doldurulur; FREE
    abonelikte NULL'dır.
    """

    __tablename__ = "subscription"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_subscription_tenant_id"),)

    plan: Mapped[PlanTier] = mapped_column(
        SAEnum(PlanTier, native_enum=False, length=20), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, native_enum=False, length=20), nullable=False
    )
    provider: Mapped[str | None] = mapped_column(String(50))
    provider_customer_id: Mapped[str | None] = mapped_column(String(255))
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255))
