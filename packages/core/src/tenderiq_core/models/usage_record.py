"""UsageRecord — işlenen doküman başına kullanım kaydı (kota sayımı; RLS)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin


class UsageRecord(UUIDPKMixin, TenantMixin, Base):
    """İşlenen bir doküman için kullanım kaydı (kiracı-özel).

    Kota sayımı bu satırlar üzerinden yapılır: dönem içindeki satır sayısı =
    kullanılan doküman, ``pages`` toplamı = kullanılan sayfa. Bir satır yükleme
    **tamamlandığında** (``pages=0``) eklenir; parsing bitince ``pages`` worker
    tarafından gerçek sayfa sayısıyla güncellenir. Doküman sonradan silinse de
    dönem sayımı bozulmasın diye ``document_id`` FK ``SET NULL``'dır.
    """

    __tablename__ = "usage_record"

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("document.id", ondelete="SET NULL"), index=True
    )
    pages: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
