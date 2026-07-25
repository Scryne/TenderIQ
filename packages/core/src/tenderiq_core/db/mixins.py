"""Ortak ORM mixin'leri: UUID birincil anahtar, kiracı kolonu ve yumuşak silme."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPKMixin:
    """UUID birincil anahtar (DB tarafında ``gen_random_uuid()`` ile üretilir)."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )


class TenantMixin:
    """Kiracıya-özel tablolar için ``tenant_id`` (PostgreSQL RLS ile zorlanır)."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """İki fazlı silme için ``deleted_at`` (KVKK kalıcı silme akışı, §8.3).

    Kullanıcının "sil" demesi veriyi ANINDA yok etmez: satır işaretlenir, tüm
    okuma yollarından düşer (bkz. ``tenderiq_core.db.soft_delete``) ve saklama
    penceresi (``DATA_RETENTION_DAYS``) dolunca zamanlanmış iş satırı ve nesne
    depolamadaki dosyayı KALICI olarak siler.

    Pencere bilinçlidir: yanlışlıkla silinen bir ihalenin geri alınabilmesi
    gerekir; öte yandan KVKK "silme talebi" için sınırsız bekleme kabul edilemez,
    bu yüzden pencere sonunda silme otomatiktir ve elle onay istemez.
    """

    # İndeks burada DEĞİL migration'da tanımlıdır ve KISMİDİR
    # (``WHERE deleted_at IS NOT NULL``): süpürme işi yalnız silinmiş satırları
    # tarar. `index=True` demek tam indeks üretir ve her canlı satıra gereksiz
    # yazma maliyeti bindirirdi.
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
