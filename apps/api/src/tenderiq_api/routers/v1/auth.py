"""/api/v1/auth — kayıt, giriş ve mevcut kullanıcı (oran sınırlamalı)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, EmailStr, Field
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError

from tenderiq_api.dependencies import PrincipalDep, RedisDep, SessionDep, SettingsDep
from tenderiq_api.errors import ConflictError, RateLimitedError, UnauthorizedError
from tenderiq_core.config import Settings
from tenderiq_core.models import Role, User
from tenderiq_core.security.tokens import create_access_token
from tenderiq_core.services import auth as auth_service
from tenderiq_core.services.rate_limit import (
    RateLimitExceededError,
    check_rate_limit,
    reset_rate_limit,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request, trusted_proxy_count: int) -> str:
    """Gerçek istemci IP'si: güvenilir proxy arkasında X-Forwarded-For'dan çözülür.

    ``trusted_proxy_count``, XFF listesinin SONDAN kaç girdisinin güvenilir altyapı
    (Next proxy'si / LB) tarafından eklendiğini söyler; istemcinin sahte öne-ek
    eklemesi bu girdileri etkileyemez. 0 (varsayılan) → XFF yok sayılır.
    """
    if trusted_proxy_count > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [part.strip() for part in forwarded.split(",") if part.strip()]
            if hops:
                return hops[max(len(hops) - trusted_proxy_count, 0)]
    return request.client.host if request.client else "unknown"


def _rate_limit_email(email: str) -> str:
    """E-posta sayaç anahtarı için normalize edilmiş kimlik."""
    return email.strip().lower()


async def _enforce_auth_rate_limit(
    request: Request, redis: Redis, settings: Settings, *, scope: str, email: str
) -> None:
    """IP + e-posta bazlı deneme sınırı (brute-force / kayıt istismarı koruması)."""
    client_ip = _client_ip(request, settings.trusted_proxy_count)
    try:
        await check_rate_limit(
            redis,
            scope=f"{scope}:ip",
            identifier=client_ip,
            limit=settings.auth_rate_limit_ip_attempts,
            window_seconds=settings.auth_rate_limit_window_seconds,
        )
        await check_rate_limit(
            redis,
            scope=f"{scope}:email",
            identifier=_rate_limit_email(email),
            limit=settings.auth_rate_limit_attempts,
            window_seconds=settings.auth_rate_limit_window_seconds,
        )
    except RateLimitExceededError as exc:
        raise RateLimitedError(
            "Çok fazla deneme yapıldı; lütfen daha sonra yeniden deneyin.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


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
async def register(
    body: RegisterRequest,
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> UserResponse:
    """Yeni bir organizasyon ve admin kullanıcı oluşturur."""
    await _enforce_auth_rate_limit(request, redis, settings, scope="register", email=body.email)
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
    except IntegrityError as exc:
        # Ön-kontrol ile INSERT arasındaki yarışta unique kısıt DB'de yakalar;
        # 500 yerine tutarlı 409 dönmeli.
        raise ConflictError("Bu e-posta veya organizasyon slug'ı zaten kayıtlı.") from exc
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        tenant_id=membership.organization_id,
        role=membership.role,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> TokenResponse:
    """Kimlik doğrular ve bir JWT erişim token'ı döndürür."""
    if settings.auth_secret is None:
        raise UnauthorizedError("Sunucu kimlik doğrulaması yapılandırılmamış (AUTH_SECRET).")
    await _enforce_auth_rate_limit(request, redis, settings, scope="login", email=body.email)
    result = await auth_service.authenticate(session, email=body.email, password=body.password)
    if result is None:
        raise UnauthorizedError("E-posta veya parola hatalı.")
    user, membership = result
    # Başarılı giriş e-posta penceresini sıfırlar: meşru kullanıcının ardışık
    # girişleri limiti tüketmez (IP sayacı, dağıtık denemelere karşı korunur).
    await reset_rate_limit(redis, scope="login:email", identifier=_rate_limit_email(body.email))
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
