"""AuditLog — kritik işlemlerin kim-ne-zaman kaydı (append-only, kiracı-özel).

RLS politikaları yalnızca SELECT/INSERT'e izin verir: uygulama rolü mevcut
kayıtları değiştiremez ve silemez (denetim izinin bütünlüğü, §10.5).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin


class AuditAction(StrEnum):
    """Denetlenen işlem türleri."""

    TENDER_CREATED = "tender.created"
    TENDER_EXPORTED = "tender.exported"
    DOCUMENT_CREATED = "document.created"
    DOCUMENT_UPLOAD_COMPLETED = "document.upload_completed"
    DOCUMENT_UPLOAD_REJECTED = "document.upload_rejected"
    DOCUMENT_DELETED = "document.deleted"
    JOB_RETRIED = "job.retried"
    ROLE_CHANGED = "role.changed"
    MEMBERSHIP_REMOVED = "membership.removed"
    # Üye daveti yaşam döngüsü (Sprint 3.3-E-2): resource_type = "invitation",
    # resource_id = davet id'si; accept'te ayrıca yeni üyelik oluşur.
    MEMBER_INVITED = "member.invited"
    INVITATION_REVOKED = "invitation.revoked"
    INVITATION_ACCEPTED = "invitation.accepted"
    # İnsan-döngüde inceleme (Sprint 3.2): resource_type = FindingKind değeri,
    # resource_id = bulgu id'si — bulgu başına düzenleme geçmişinin kaynağıdır.
    FINDING_APPROVED = "finding.approved"
    FINDING_REJECTED = "finding.rejected"
    FINDING_EDITED = "finding.edited"
    FINDING_REVIEW_RESET = "finding.review_reset"
    FINDING_COMMENTED = "finding.commented"


class AuditLog(UUIDPKMixin, TenantMixin, Base):
    """Tek bir denetim kaydı (değiştirilemez)."""

    __tablename__ = "audit_log"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
