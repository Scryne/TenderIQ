"""FastAPI bağımlılıkları: DB oturumu, kimlik (principal) ve RBAC."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tenderiq_api.errors import AppError, ErrorCode, ForbiddenError, UnauthorizedError
from tenderiq_core.config import Settings, get_settings
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.models import Role
from tenderiq_core.security.tokens import decode_access_token
from tenderiq_core.storage import StorageService


def _session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Kiracı bağlamı OLMAYAN oturum (kayıt/giriş gibi kimlik işlemleri için)."""
    async with _session_factory(request)() as session:
        yield session


@dataclass(frozen=True)
class Principal:
    """Kimliği doğrulanmış istek sahibi."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: Role


def _bearer_token(authorization: str | None) -> str:
    prefix = "bearer "
    if authorization is None or not authorization.lower().startswith(prefix):
        raise UnauthorizedError("Yetkilendirme başlığı eksik veya hatalı.")
    return authorization[len(prefix) :]


async def get_principal(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    """Bearer JWT'yi doğrular ve Principal döndürür."""
    if settings.auth_secret is None:
        raise UnauthorizedError("Sunucu kimlik doğrulaması yapılandırılmamış (AUTH_SECRET).")
    token = _bearer_token(authorization)
    try:
        payload = decode_access_token(token, settings.auth_secret)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Geçersiz veya süresi dolmuş token.") from exc
    return Principal(
        user_id=uuid.UUID(payload.sub),
        tenant_id=uuid.UUID(payload.tenant_id),
        role=Role(payload.role),
    )


async def get_tenant_session(
    request: Request,
    principal: Annotated[Principal, Depends(get_principal)],
) -> AsyncIterator[AsyncSession]:
    """RLS kiracı bağlamı ayarlanmış oturum (kiracı-özel veriler için)."""
    async with _session_factory(request)() as session, session.begin():
        await set_tenant_context(session, principal.tenant_id)
        yield session


def require_role(*roles: Role) -> Callable[..., Coroutine[Any, Any, Principal]]:
    """Belirtilen rollerden birini gerektiren bir bağımlılık üretir."""

    async def _checker(
        principal: Annotated[Principal, Depends(get_principal)],
    ) -> Principal:
        if principal.role not in roles:
            raise ForbiddenError("Bu işlem için yetkiniz yok.")
        return principal

    return _checker


def get_storage(request: Request) -> StorageService:
    """Yapılandırılmış nesne depolama servisini döndürür."""
    storage = request.app.state.storage
    if storage is None:
        raise AppError(
            "Nesne depolama yapılandırılmamış.",
            code=ErrorCode.INTERNAL_ERROR,
            status_code=503,
        )
    resolved: StorageService = storage
    return resolved


# Sık kullanılan tip takma adları (router imzalarını sadeleştirir).
SessionDep = Annotated[AsyncSession, Depends(get_session)]
TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
StorageDep = Annotated[StorageService, Depends(get_storage)]
