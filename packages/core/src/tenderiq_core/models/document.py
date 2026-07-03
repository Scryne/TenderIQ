"""Document (yüklenen dosya) modeli — kiracı-özel, RLS ile korunur."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base, TimestampMixin
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin


class DocumentKind(StrEnum):
    """İhale dosyası türü."""

    ADMINISTRATIVE = "administrative"  # idari şartname
    TECHNICAL = "technical"  # teknik şartname
    CONTRACT = "contract"  # sözleşme
    ADDENDUM = "addendum"  # zeyilname
    OTHER = "other"


class DocumentStatus(StrEnum):
    """Dosyanın yükleme/işleme durumu."""

    PENDING_UPLOAD = "pending_upload"  # imzalı URL verildi, yükleme bekleniyor
    UPLOADED = "uploaded"  # nesne depolamaya yüklendi
    FAILED = "failed"


class Document(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Bir Tender'a bağlı yüklenen dosya (kiracı-özel)."""

    __tablename__ = "document"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tender.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    kind: Mapped[DocumentKind] = mapped_column(
        SAEnum(DocumentKind, native_enum=False, length=20), nullable=False
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, native_enum=False, length=20), nullable=False
    )
