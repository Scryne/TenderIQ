"""/api/v1/members — organizasyon üye yönetimi (liste / rol / çıkarma) — 3.3-E.

Aktif organizasyon ``principal.tenant_id``'dir. ``Membership``/``User`` RLS'siz
kimlik tablolarıdır; sorgular aktif org'a **elle** filtrelenir. Yazma işlemleri
admin gerektirir ve AuditLog'lanır (tenant bağlamı ayarlı oturumda). "Son
yönetici" korumaları org'u yönetici olmadan bırakmayı engeller.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from pydantic import BaseModel
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_api.dependencies import PrincipalDep, RedisDep, TenantSessionDep, require_role
from tenderiq_api.errors import ConflictError, NotFoundError
from tenderiq_core.logging import get_logger
from tenderiq_core.models import AuditAction, Membership, Role, User
from tenderiq_core.services import refresh_tokens
from tenderiq_core.services.audit import record_audit

logger = get_logger("tenderiq.api.members")

router = APIRouter(prefix="/members", tags=["members"])

_admin = Depends(require_role(Role.ADMIN))


class MemberResponse(BaseModel):
    """Aktif organizasyonun bir üyesi."""

    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: Role
    email_verified: bool


class RoleUpdate(BaseModel):
    """Üye rolü güncelleme."""

    role: Role


async def _admin_count(session: AsyncSession, organization_id: uuid.UUID) -> int:
    """Bir organizasyondaki yönetici (admin) üye sayısı."""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == organization_id,
                Membership.role == Role.ADMIN,
            )
        )
        or 0
    )


def _member_response(membership: Membership, user: User) -> MemberResponse:
    return MemberResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        email_verified=user.email_verified,
    )


@router.get("", response_model=list[MemberResponse])
async def list_members(session: TenantSessionDep, principal: PrincipalDep) -> list[MemberResponse]:
    """Aktif organizasyonun üyelerini listeler (her rol görebilir)."""
    rows = (
        await session.execute(
            select(Membership, User)
            .join(User, Membership.user_id == User.id)
            .where(Membership.organization_id == principal.tenant_id)
            .order_by(Membership.created_at)
        )
    ).all()
    return [_member_response(membership, user) for membership, user in rows]


@router.patch("/{user_id}", response_model=MemberResponse, dependencies=[_admin])
async def update_member_role(
    user_id: uuid.UUID,
    body: RoleUpdate,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> MemberResponse:
    """Bir üyenin rolünü değiştirir (admin). Son yönetici düşürülemez."""
    membership: Membership | None = await session.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == principal.tenant_id,
        )
    )
    if membership is None:
        raise NotFoundError("Üye bulunamadı.")
    user = await session.get(User, user_id)
    if user is None:  # pragma: no cover - FK bütünlüğü gereği olmamalı
        raise NotFoundError("Üye bulunamadı.")

    old_role = membership.role
    if old_role == body.role:
        return _member_response(membership, user)  # idempotent no-op

    # Son yönetici koruması: bir admini düşürmek org'u yöneticisiz bırakamaz.
    if (
        old_role is Role.ADMIN
        and body.role is not Role.ADMIN
        and await _admin_count(session, principal.tenant_id) <= 1
    ):
        raise ConflictError("Organizasyonun en az bir yöneticisi olmalı.")

    membership.role = body.role
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.ROLE_CHANGED,
        resource_type="membership",
        resource_id=membership.id,
        actor_user_id=principal.user_id,
        meta={"user_id": str(user_id), "old_role": old_role.value, "new_role": body.role.value},
    )
    return _member_response(membership, user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def remove_member(
    user_id: uuid.UUID,
    session: TenantSessionDep,
    principal: PrincipalDep,
    redis: RedisDep,
) -> Response:
    """Bir üyeyi organizasyondan çıkarır (admin). Son yönetici çıkarılamaz.

    Çıkarılan kullanıcının bu org'a olan erişimi kesilir; oturumları (refresh
    token'ları) da iptal edilir (en-iyi-çaba — kısa erişim token'ı doğal süresinde
    biter). Kullanıcı başka org'lara üyse onlardaki erişimi etkilenmez.
    """
    membership: Membership | None = await session.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == principal.tenant_id,
        )
    )
    if membership is None:
        raise NotFoundError("Üye bulunamadı.")
    if membership.role is Role.ADMIN and await _admin_count(session, principal.tenant_id) <= 1:
        raise ConflictError("Organizasyonun son yöneticisi çıkarılamaz.")

    # Denetim değerleri silmeden ÖNCE yakalanır (silinen nesnenin alanlarına güvenme).
    membership_id = membership.id
    removed_role = membership.role
    await session.delete(membership)
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.MEMBERSHIP_REMOVED,
        resource_type="membership",
        resource_id=membership_id,
        actor_user_id=principal.user_id,
        meta={"user_id": str(user_id), "role": removed_role.value},
    )
    # Çıkarılan kullanıcının oturumlarını iptal et (mevcut refresh token'ları ölür).
    try:
        await refresh_tokens.revoke_all_for_user(redis, user_id)
    except RedisError as exc:
        logger.warning("uye_oturumlari_iptal_edilemedi", error=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
