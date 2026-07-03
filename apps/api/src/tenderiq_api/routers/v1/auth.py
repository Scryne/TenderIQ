"""/api/v1/auth — kayıt, giriş ve mevcut kullanıcı."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr, Field

from tenderiq_api.dependencies import PrincipalDep, SessionDep, SettingsDep
from tenderiq_api.errors import ConflictError, UnauthorizedError
from tenderiq_core.models import Role, User
from tenderiq_core.security.tokens import create_access_token
from tenderiq_core.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    """Yeni organizasyon + admin kullanıcı kaydı."""

    org_name: str = Field(min_length=1, max_length=255)
    org_slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """E-posta/parola ile giriş."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT erişim token'ı."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105  (token türü, parola değil)


class UserResponse(BaseModel):
    """Kullanıcı + aktif kiracı + rol."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    tenant_id: uuid.UUID
    role: Role


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: SessionDep) -> UserResponse:
    """Yeni bir organizasyon ve admin kullanıcı oluşturur."""
    try:
        async with session.begin():
            user, membership = await auth_service.register(
                session,
                org_name=body.org_name,
                org_slug=body.org_slug,
                email=body.email,
                password=body.password,
                full_name=body.full_name,
            )
    except auth_service.EmailAlreadyExistsError as exc:
        raise ConflictError("Bu e-posta ile bir kullanıcı zaten var.") from exc
    except auth_service.SlugAlreadyExistsError as exc:
        raise ConflictError("Bu slug ile bir organizasyon zaten var.") from exc
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        tenant_id=membership.organization_id,
        role=membership.role,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: SessionDep, settings: SettingsDep) -> TokenResponse:
    """Kimlik doğrular ve bir JWT erişim token'ı döndürür."""
    if settings.auth_secret is None:
        raise UnauthorizedError("Sunucu kimlik doğrulaması yapılandırılmamış (AUTH_SECRET).")
    result = await auth_service.authenticate(session, email=body.email, password=body.password)
    if result is None:
        raise UnauthorizedError("E-posta veya parola hatalı.")
    user, membership = result
    token = create_access_token(
        user_id=user.id,
        tenant_id=membership.organization_id,
        role=membership.role,
        secret=settings.auth_secret,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(principal: PrincipalDep, session: SessionDep) -> UserResponse:
    """Geçerli token'a karşılık gelen kullanıcıyı döndürür."""
    user: User | None = await session.get(User, principal.user_id)
    if user is None:
        raise UnauthorizedError("Kullanıcı bulunamadı.")
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        tenant_id=principal.tenant_id,
        role=principal.role,
    )
