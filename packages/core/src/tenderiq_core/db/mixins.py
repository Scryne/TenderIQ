"""Ortak ORM mixin'leri: UUID birincil anahtar ve kiracı (tenant) kolonu."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Uuid, func
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
