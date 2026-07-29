"""Subscription — kiracının abonelik planı ve durumu (kiracı-özel, RLS)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
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
    #: İşlenmiş SON olayın sağlayıcıdaki zamanı. Sırasız gelen webhook'larda
    #: eski bir olayın yeni durumu ezmesini engeller (bkz. services.billing).
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Yaşam döngüsü: iptal ve planlanmış plan değişimi (/sartlar §3) ────────
    #
    # `/sartlar` §3 üç kural taahhüt eder: yükseltme ANINDA, düşürme DÖNEM
    # SONUNDA, iptal DÖNEM SONUNDA erişimi keser. İlki mevcut alanlara yazılarak
    # uygulanır; diğer ikisi bir GELECEK tarih ve o tarihte uygulanacak bir hedef
    # gerektirir — bu üç alan onu tutar. Kayıt olmadan "dönem sonunda" sözü
    # tutulamaz: ne kullanıcıya erişimin ne zamana kadar sürdüğü söylenebilir,
    # ne de değişim uygulanabilir.

    #: Ödenmiş dönemin bittiği (ve iptal edilmemişse sıradaki tahsilatın
    #: yapılacağı) an. Sağlayıcıdan aynalanır; bilinmiyorsa kota dönemi
    #: (takvim ayı) sonuna düşülür — bkz. ``services.billing``.
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: İptal EDİLDİ ama erişim ``current_period_end``e kadar sürüyor.
    #: Durum bu sürede ACTIVE kalır: müşteri ödediği dönemin hakkını kullanır ve
    #: kota katmanı (``services.quota``) tek bir alana bakmak zorunda kalmaz.
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    #: Dönem sonunda geçilecek kademe (düşürme). Yükseltmede kullanılmaz.
    pending_plan: Mapped[PlanTier | None] = mapped_column(
        SAEnum(PlanTier, native_enum=False, length=20)
    )
