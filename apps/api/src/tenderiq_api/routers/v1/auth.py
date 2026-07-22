"""/api/v1/auth — kayıt, giriş ve mevcut kullanıcı (oran sınırlamalı)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from tenderiq_api.dependencies import PrincipalDep, RedisDep, SessionDep, SettingsDep
from tenderiq_api.errors import (
    ConflictError,
    ForbiddenError,
    RateLimitedError,
    UnauthorizedError,
    ValidationFailedError,
)
from tenderiq_core.config import Settings
from tenderiq_core.logging import get_logger
from tenderiq_core.models import Membership, Organization, Role, User
from tenderiq_core.security.passwords import hash_password
from tenderiq_core.security.tokens import create_access_token
from tenderiq_core.services import auth as auth_service
from tenderiq_core.services import email as email_service
from tenderiq_core.services import one_time_tokens, refresh_tokens
from tenderiq_core.services.one_time_tokens import InvalidOneTimeTokenError
from tenderiq_core.services.rate_limit import (
    RateLimitExceededError,
    check_rate_limit,
    reset_rate_limit,
)

logger = get_logger("tenderiq.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_access_token(
    settings: Settings, *, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str
) -> tuple[str, int]:
    """Kısa ömürlü erişim token'ı + saniye cinsinden ömrü üretir.

    ``settings.auth_secret`` çağıran tarafından None olmadığı doğrulanmış olmalıdır.
    """
    assert settings.auth_secret is not None  # noqa: S101 - çağıran login/refresh guard eder
    minutes = settings.access_token_expire_minutes
    token = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        secret=settings.auth_secret,
        expires_in_minutes=minutes,
    )
    return token, minutes * 60


async def _issue_refresh_token(
    redis: Redis, settings: Settings, *, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str
) -> str | None:
    """Refresh token üretir; Redis kesintisinde None döner (giriş yine de tamamlanır).

    Refresh token yoksa istemci yalnızca kısa erişim token'ıyla çalışır ve ömrü
    dolunca yeniden giriş yapar — kimlik hizmeti Redis'e tam bağımlı olmaz.
    """
    try:
        return await refresh_tokens.issue_refresh_token(
            redis,
            identity=refresh_tokens.RefreshIdentity(
                user_id=user_id, tenant_id=tenant_id, role=role
            ),
            ttl_seconds=settings.refresh_token_expire_days * 86_400,
        )
    except RedisError as exc:
        logger.warning("refresh_token_uretilemedi", error=str(exc))
        return None


async def _send_verification_email(
    redis: Redis, settings: Settings, *, user_id: uuid.UUID, email: str
) -> None:
    """E-posta doğrulama token'ı üretir ve bağlantıyı gönderir (en-iyi-çaba).

    Redis kesintisinde sessizce geçer (kayıt/istek yine tamamlanır; kullanıcı
    yeniden gönderim isteyebilir).
    """
    try:
        token = await one_time_tokens.issue(
            redis,
            purpose=one_time_tokens.EMAIL_VERIFY,
            user_id=user_id,
            ttl_seconds=settings.email_verify_token_ttl_hours * 3600,
        )
    except RedisError as exc:
        logger.warning("dogrulama_epostasi_uretilemedi", error=str(exc))
        return
    link = f"{settings.app_base_url}/verify-email?token={token}"
    await email_service.send_account_email(
        settings,
        to=email,
        subject="TenderIQ — E-posta adresinizi doğrulayın",
        body=f"Hesabınızı doğrulamak için bağlantıya gidin: {link}",
    )


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
    """Kısa ömürlü erişim token'ı + (varsa) rotasyonlu refresh token."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105  (token türü, parola değil)
    expires_in: int  # erişim token'ının ömrü (saniye)
    refresh_token: str | None = None


class RefreshRequest(BaseModel):
    """Refresh token ile yeni erişim token'ı talebi."""

    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    """Oturumu (refresh token ailesini) sonlandırma talebi."""

    refresh_token: str = Field(min_length=1, max_length=512)


class VerifyEmailRequest(BaseModel):
    """E-posta doğrulama token'ı."""

    token: str = Field(min_length=1, max_length=512)


class ForgotPasswordRequest(BaseModel):
    """Parola sıfırlama bağlantısı talebi."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Token ile yeni parola belirleme."""

    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)


class SwitchOrgRequest(BaseModel):
    """Aktif organizasyonu değiştirme talebi."""

    organization_id: uuid.UUID


class MembershipInfo(BaseModel):
    """Kullanıcının bir organizasyondaki üyeliği (çoklu-org seçimi için)."""

    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    role: Role
    is_active: bool  # geçerli token'ın aktif organizasyonu mu


class UserResponse(BaseModel):
    """Kullanıcı + aktif kiracı + rol."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    tenant_id: uuid.UUID
    role: Role
    email_verified: bool


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
    # Doğrulama e-postası (commit SONRASI; en-iyi-çaba — kayıt Redis/e-postaya bağlı değil).
    await _send_verification_email(redis, settings, user_id=user.id, email=user.email)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        tenant_id=membership.organization_id,
        role=membership.role,
        email_verified=False,  # yeni kayıt her zaman doğrulanmamış
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
    access_token, expires_in = _issue_access_token(
        settings, user_id=user.id, tenant_id=membership.organization_id, role=membership.role.value
    )
    refresh_token = await _issue_refresh_token(
        redis,
        settings,
        user_id=user.id,
        tenant_id=membership.organization_id,
        role=membership.role.value,
    )
    return TokenResponse(
        access_token=access_token, expires_in=expires_in, refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> TokenResponse:
    """Refresh token'ı doğrular, rotasyonla yeniler ve yeni erişim token'ı üretir.

    Token tek-kullanımlıktır: her başarılı yenileme yeni bir refresh token döndürür
    ve eskisini geçersizler. Kullanılmış bir token yeniden sunulursa tüm oturum
    ailesi iptal edilir (hırsızlık savunması). Kullanıcı bu arada pasifleştirildiyse
    veya üyeliği kaldırıldıysa yenileme reddedilir (deaktivasyon onurlandırılır).
    """
    if settings.auth_secret is None:
        raise UnauthorizedError("Sunucu kimlik doğrulaması yapılandırılmamış (AUTH_SECRET).")
    try:
        rotated = await refresh_tokens.rotate_refresh_token(
            redis, body.refresh_token, ttl_seconds=settings.refresh_token_expire_days * 86_400
        )
    except refresh_tokens.ReusedRefreshTokenError as exc:
        raise UnauthorizedError(
            "Oturum güvenlik nedeniyle sonlandırıldı; lütfen yeniden giriş yapın."
        ) from exc
    except refresh_tokens.InvalidRefreshTokenError as exc:
        raise UnauthorizedError("Geçersiz veya süresi dolmuş oturum.") from exc
    except RedisError as exc:
        # Redis erişilemezken refresh doğrulanamaz → fail-closed (yeniden giriş gerekir).
        raise UnauthorizedError("Oturum servisi geçici olarak kullanılamıyor.") from exc

    identity = rotated.identity
    user: User | None = await session.get(User, identity.user_id)
    membership: Membership | None = await session.scalar(
        select(Membership).where(
            Membership.user_id == identity.user_id,
            Membership.organization_id == identity.tenant_id,
        )
    )
    if user is None or not user.is_active or membership is None:
        # Kimlik artık geçerli değil: az önce üretilen token'ı da iptal et (aile).
        await refresh_tokens.revoke_refresh_token(redis, rotated.token)
        raise UnauthorizedError("Hesap artık etkin değil; yeniden giriş yapın.")

    access_token, expires_in = _issue_access_token(
        settings,
        user_id=identity.user_id,
        tenant_id=identity.tenant_id,
        role=membership.role.value,
    )
    return TokenResponse(
        access_token=access_token, expires_in=expires_in, refresh_token=rotated.token
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, redis: RedisDep) -> Response:
    """Refresh token ailesini iptal eder (oturumu sonlandırır). Idempotent.

    Erişim token'ı denylist'lenmez; kısa ömürlü olduğundan doğal süresinde biter.
    Redis kesintisinde en-iyi-çaba (best-effort) davranır; yine 204 döner.
    """
    try:
        await refresh_tokens.revoke_refresh_token(redis, body.refresh_token)
    except RedisError as exc:
        logger.warning("logout_iptal_edilemedi", error=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/memberships", response_model=list[MembershipInfo])
async def memberships(principal: PrincipalDep, session: SessionDep) -> list[MembershipInfo]:
    """Geçerli kullanıcının üyeliklerini (organizasyon + rol) listeler.

    İstemci, çoklu-org seçici sunmak için kullanır; ``is_active`` geçerli token'ın
    aktif organizasyonunu işaretler.
    """
    rows = (
        await session.execute(
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(Membership.user_id == principal.user_id)
            .order_by(Membership.created_at)
        )
    ).all()
    return [
        MembershipInfo(
            organization_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            role=membership.role,
            is_active=org.id == principal.tenant_id,
        )
        for membership, org in rows
    ]


@router.post("/switch-org", response_model=TokenResponse)
async def switch_org(
    body: SwitchOrgRequest,
    principal: PrincipalDep,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> TokenResponse:
    """Aktif organizasyonu değiştirir ve hedef org için yeni token'lar üretir.

    Kullanıcının hedef organizasyonda üyeliği yoksa 403. Önceki org'un token'ları
    iptal edilmez (çoklu-org eşzamanlı oturumlara izin verilir).
    """
    if settings.auth_secret is None:
        raise UnauthorizedError("Sunucu kimlik doğrulaması yapılandırılmamış (AUTH_SECRET).")
    membership: Membership | None = await session.scalar(
        select(Membership).where(
            Membership.user_id == principal.user_id,
            Membership.organization_id == body.organization_id,
        )
    )
    if membership is None:
        raise ForbiddenError("Bu organizasyonda üyeliğiniz yok.")
    user: User | None = await session.get(User, principal.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Hesap artık etkin değil.")
    access_token, expires_in = _issue_access_token(
        settings,
        user_id=principal.user_id,
        tenant_id=body.organization_id,
        role=membership.role.value,
    )
    refresh_token = await _issue_refresh_token(
        redis,
        settings,
        user_id=principal.user_id,
        tenant_id=body.organization_id,
        role=membership.role.value,
    )
    return TokenResponse(
        access_token=access_token, expires_in=expires_in, refresh_token=refresh_token
    )


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(body: VerifyEmailRequest, session: SessionDep, redis: RedisDep) -> Response:
    """E-posta doğrulama token'ını tüketir ve kullanıcıyı doğrulanmış işaretler.

    Token tek-kullanımlıktır (atomik GETDEL). Geçersiz/süresi dolmuş → 400.
    """
    try:
        user_id = await one_time_tokens.consume(
            redis, purpose=one_time_tokens.EMAIL_VERIFY, token=body.token
        )
    except InvalidOneTimeTokenError as exc:
        raise ValidationFailedError("Geçersiz veya süresi dolmuş doğrulama bağlantısı.") from exc
    except RedisError as exc:
        raise ValidationFailedError("Doğrulama servisi geçici olarak kullanılamıyor.") from exc
    async with session.begin():
        user = await session.get(User, user_id)
        if user is not None:
            user.email_verified = True
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
async def resend_verification(
    principal: PrincipalDep, session: SessionDep, redis: RedisDep, settings: SettingsDep
) -> Response:
    """Giriş yapmış kullanıcıya yeni bir doğrulama bağlantısı gönderir (idempotent)."""
    user: User | None = await session.get(User, principal.user_id)
    if user is not None and not user.email_verified:
        await _send_verification_email(redis, settings, user_id=user.id, email=user.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> Response:
    """Parola sıfırlama bağlantısı gönderir.

    Kullanıcı bulunmasa bile 204 döner (kullanıcı numaralandırma sızmaz).
    """
    await _enforce_auth_rate_limit(request, redis, settings, scope="forgot", email=body.email)
    normalized = _rate_limit_email(body.email)
    user: User | None = await session.scalar(select(User).where(User.email == normalized))
    if user is not None and user.is_active:
        try:
            token = await one_time_tokens.issue(
                redis,
                purpose=one_time_tokens.PASSWORD_RESET,
                user_id=user.id,
                ttl_seconds=settings.password_reset_token_ttl_hours * 3600,
            )
        except RedisError as exc:
            logger.warning("sifirlama_epostasi_uretilemedi", error=str(exc))
        else:
            link = f"{settings.app_base_url}/reset-password?token={token}"
            await email_service.send_account_email(
                settings,
                to=user.email,
                subject="TenderIQ — Parola sıfırlama",
                body=f"Parolanızı sıfırlamak için bağlantıya gidin: {link}",
            )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    body: ResetPasswordRequest, session: SessionDep, redis: RedisDep
) -> Response:
    """Sıfırlama token'ını tüketir, yeni parolayı ayarlar ve TÜM oturumları iptal eder.

    Parola değişince mevcut refresh token aileleri geçersizlenir (çalınmış oturum
    yeni parolayla yaşayamaz). Geçersiz/süresi dolmuş token → 400.
    """
    try:
        user_id = await one_time_tokens.consume(
            redis, purpose=one_time_tokens.PASSWORD_RESET, token=body.token
        )
    except InvalidOneTimeTokenError as exc:
        raise ValidationFailedError("Geçersiz veya süresi dolmuş sıfırlama bağlantısı.") from exc
    except RedisError as exc:
        raise ValidationFailedError("Sıfırlama servisi geçici olarak kullanılamıyor.") from exc
    async with session.begin():
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Hesap artık etkin değil.")
        user.hashed_password = hash_password(body.new_password)
    # Parola değişti: kullanıcının tüm oturumları iptal (mevcut refresh'ler ölür).
    try:
        await refresh_tokens.revoke_all_for_user(redis, user_id)
    except RedisError as exc:
        logger.warning("oturumlar_iptal_edilemedi", error=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        email_verified=user.email_verified,
    )
