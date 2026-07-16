"""Denetim kaydı servisi — kritik işlemlerde AuditLog satırı ekler."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from tenderiq_core.models import AuditAction, AuditLog


def record_audit(
    session: AsyncSession | Session,
    *,
    tenant_id: uuid.UUID,
    action: AuditAction,
    resource_type: str,
    resource_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> AuditLog:
    """Oturuma bir denetim kaydı ekler (flush/commit çağıranın sorumluluğudur)."""
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action.value,
        resource_type=resource_type,
        resource_id=resource_id,
        meta=meta,
    )
    session.add(entry)
    return entry
