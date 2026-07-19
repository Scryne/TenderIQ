"""/api/v1/capability-profile — firma yetkinlik profili (Sprint 2.3, §6.7).

Compliance gap analizinin girdisi: firmanın kendi beyan ettiği yetkinlikler.
Kiracı başına tekildir (RLS + ``uq_capability_profile_tenant``); ``POST`` upsert'tir
(mevcut profili günceller veya oluşturur). Yazma admin/üye gerektirir; izleyici
yalnız okuyabilir.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from tenderiq_api.dependencies import PrincipalDep, TenantSessionDep, require_role
from tenderiq_api.errors import NotFoundError
from tenderiq_core.models import CapabilityProfile, Role

router = APIRouter(prefix="/capability-profile", tags=["capability-profile"])

_writer = Depends(require_role(Role.ADMIN, Role.MEMBER))


class CapabilityProfileUpsert(BaseModel):
    """Yetkinlik profili girişi (serbest metin)."""

    content: str = Field(min_length=1, max_length=100_000)


class CapabilityProfileResponse(BaseModel):
    """Kiracının yetkinlik profili."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str


@router.get("", response_model=CapabilityProfileResponse)
async def get_capability_profile(session: TenantSessionDep) -> CapabilityProfileResponse:
    """Aktif kiracının yetkinlik profilini döndürür (yoksa 404)."""
    profile = await session.scalar(select(CapabilityProfile))
    if profile is None:
        raise NotFoundError("Yetkinlik profili tanımlı değil.")
    return CapabilityProfileResponse.model_validate(profile)


@router.post(
    "",
    response_model=CapabilityProfileResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[_writer],
)
async def upsert_capability_profile(
    body: CapabilityProfileUpsert,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> CapabilityProfileResponse:
    """Aktif kiracının yetkinlik profilini oluşturur veya günceller (upsert).

    Kiracı başına tek profil olduğundan atomik ``INSERT ... ON CONFLICT DO UPDATE``
    kullanılır. Böylece profili olmayan iki EŞZAMANLI istek de ``uq_capability_
    profile_tenant`` ihlaliyle 500 üretmez — ikisi de başarılı olur (RLS WITH CHECK
    sağlanır: ``tenant_id`` değişmez, aktif kiracıya eşittir).
    """
    stmt = (
        pg_insert(CapabilityProfile)
        .values(tenant_id=principal.tenant_id, content=body.content)
        .on_conflict_do_update(
            constraint="uq_capability_profile_tenant",
            set_={"content": body.content, "updated_at": func.now()},
        )
        .returning(CapabilityProfile.id, CapabilityProfile.content)
    )
    row = (await session.execute(stmt)).one()
    return CapabilityProfileResponse(id=row.id, content=row.content)
