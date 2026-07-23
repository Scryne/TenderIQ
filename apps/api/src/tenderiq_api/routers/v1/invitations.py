"""/api/v1/invitations — üye daveti (oluştur/listele/iptal + kabul) — 3.3-E-2.

Yönetici uçları (oluştur/listele/iptal) aktif organizasyona (``principal.tenant_id``)
elle filtreler; ``invitation`` RLS'siz kimlik tablosudur (bkz. members.py deseni).
Kabul (accept) ve önizleme (lookup) **kimliksizdir**: davet edilen kişi henüz hesap
sahibi olmayabilir. Ham token yalnız e-postayla iletilir; API yanıtlarında dönmez.
Yeni hesap kabulde parola belirleyip otomatik giriş yapar; **mevcut** kullanıcı
otomatik giriş YAPMAZ (davet linki sızarsa hesap ele geçirilemesin — yalnız üyelik
eklenir, kullanıcı normal giriş yapar).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from tenderiq_api.dependencies import (
    PrincipalDep,
    RedisDep,
    SessionDep,
    SettingsDep,
    TenantSessionDep,
    require_role,
)
from tenderiq_api.errors import ConflictError, NotFoundError, ValidationFailedError
from tenderiq_api.routers.v1.auth import (
    TokenResponse,
    _issue_access_token,
    _issue_refresh_token,
)
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.logging import get_logger
from tenderiq_core.models import AuditAction, Invitation, InvitationStatus, Role
from tenderiq_core.services import email as email_service
from tenderiq_core.services import invitations as invitation_service
from tenderiq_core.services.audit import record_audit

logger = get_logger("tenderiq.api.invitations")

router = APIRouter(prefix="/invitations", tags=["invitations"])

_admin = Depends(require_role(Role.ADMIN))


def _is_expired(expires_at: datetime) -> bool:
    """Süresi geçmiş bekleyen davet mi (DB timezone-aware döner; savunmacı normalize)."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


class CreateInvitationRequest(BaseModel):
    """Yeni davet: e-posta + verilecek rol."""

    email: EmailStr
    role: Role = Role.MEMBER


class InvitationResponse(BaseModel):
    """Bir davet kaydı (token DÖNMEZ — yalnız e-postayla iletilir)."""

    id: uuid.UUID
    email: str
    role: Role
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
    expired: bool


class AcceptInvitationRequest(BaseModel):
    """Daveti kabul: token + (yeni hesap için) parola/ad."""

    token: str = Field(min_length=1, max_length=512)
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AcceptInvitationResponse(BaseModel):
    """Kabul sonucu; yeni hesap için otomatik-giriş token'ları eşlik eder."""

    organization_id: uuid.UUID
    account_created: bool
    tokens: TokenResponse | None = None


class InvitationPreviewResponse(BaseModel):
    """Kabul ekranı için kimliksiz davet önizlemesi."""

    organization_id: uuid.UUID
    organization_name: str
    email: str
    role: Role
    account_exists: bool


def _invitation_response(invitation: Invitation) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        expired=_is_expired(invitation.expires_at),
    )


@router.post(
    "",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_admin],
)
async def create_invitation(
    body: CreateInvitationRequest,
    session: TenantSessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
) -> InvitationResponse:
    """Aktif organizasyona bir üye davet eder (admin). E-posta zaten üyeyse 409.

    Aynı e-posta için bekleyen bir davet varsa yenisiyle süperse edilir ("yeniden
    gönder" etkisi). Davet bağlantısı e-posta seam'iyle gönderilir (dev'de loglanır).
    """
    try:
        invitation, token = await invitation_service.create_invitation(
            session,
            organization_id=principal.tenant_id,
            email=body.email,
            role=body.role,
            invited_by_user_id=principal.user_id,
            ttl_hours=settings.invitation_token_ttl_hours,
        )
    except invitation_service.EmailAlreadyMemberError as exc:
        raise ConflictError("Bu e-posta zaten organizasyonun bir üyesi.") from exc

    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.MEMBER_INVITED,
        resource_type="invitation",
        resource_id=invitation.id,
        actor_user_id=principal.user_id,
        meta={"email": invitation.email, "role": invitation.role.value},
    )
    # Davet bağlantısı (commit henüz TenantSessionDep sonunda; e-posta best-effort).
    link = f"{settings.app_base_url}/accept-invitation?token={token}"
    await email_service.send_account_email(
        settings,
        to=invitation.email,
        subject="TenderIQ — Bir organizasyona davet edildiniz",
        body=f"Daveti kabul etmek için bağlantıya gidin: {link}",
    )
    return _invitation_response(invitation)


@router.get("", response_model=list[InvitationResponse], dependencies=[_admin])
async def list_invitations(
    session: TenantSessionDep, principal: PrincipalDep
) -> list[InvitationResponse]:
    """Aktif organizasyonun bekleyen (PENDING) davetlerini listeler (admin)."""
    invitations = (
        await session.scalars(
            select(Invitation)
            .where(
                Invitation.organization_id == principal.tenant_id,
                Invitation.status == InvitationStatus.PENDING,
            )
            .order_by(Invitation.created_at.desc())
        )
    ).all()
    return [_invitation_response(inv) for inv in invitations]


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def revoke_invitation(
    invitation_id: uuid.UUID,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> Response:
    """Bekleyen bir daveti iptal eder (admin). Kabul edilmiş davet iptal edilemez (409)."""
    invitation = await session.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.organization_id == principal.tenant_id,
        )
    )
    if invitation is None:
        raise NotFoundError("Davet bulunamadı.")
    if invitation.status is InvitationStatus.ACCEPTED:
        raise ConflictError("Kabul edilmiş bir davet iptal edilemez.")
    if invitation.status is InvitationStatus.PENDING:
        invitation.status = InvitationStatus.REVOKED
        record_audit(
            session,
            tenant_id=principal.tenant_id,
            action=AuditAction.INVITATION_REVOKED,
            resource_type="invitation",
            resource_id=invitation.id,
            actor_user_id=principal.user_id,
            meta={"email": invitation.email},
        )
    # Zaten REVOKED ise idempotent (204).
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/lookup", response_model=InvitationPreviewResponse)
async def lookup_invitation(
    session: SessionDep, token: str = Query(min_length=1)
) -> InvitationPreviewResponse:
    """Bir daveti kimliksiz önizler (kabul ekranı için). Geçersiz/süresi dolmuş → 400."""
    try:
        preview = await invitation_service.lookup_invitation(session, token=token)
    except invitation_service.InvitationError as exc:
        raise ValidationFailedError("Geçersiz veya süresi dolmuş davet bağlantısı.") from exc
    return InvitationPreviewResponse(
        organization_id=preview.organization_id,
        organization_name=preview.organization_name,
        email=preview.email,
        role=preview.role,
        account_exists=preview.account_exists,
    )


@router.post("/accept", response_model=AcceptInvitationResponse)
async def accept_invitation(
    body: AcceptInvitationRequest,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> AcceptInvitationResponse:
    """Bir daveti kabul eder (kimliksiz): kullanıcıyı bulur/oluşturur ve üyelik ekler.

    Yeni hesapta parola zorunludur ve otomatik giriş token'ları döner; mevcut
    kullanıcı otomatik giriş yapmaz (yalnız üyelik eklenir). Geçersiz/süresi dolmuş
    /kullanılmış davet → 400.
    """
    async with session.begin():
        try:
            result = await invitation_service.accept_invitation(
                session,
                token=body.token,
                full_name=body.full_name,
                password=body.password,
            )
        except invitation_service.PasswordRequiredError as exc:
            raise ValidationFailedError(
                "Bu davet için bir hesap oluşturmak üzere parola belirlemelisiniz."
            ) from exc
        except invitation_service.InvitationError as exc:
            raise ValidationFailedError("Geçersiz veya süresi dolmuş davet bağlantısı.") from exc
        # Denetim kaydı kiracı bağlamı gerektirir (audit_log RLS'lidir); org davetten
        # (güvenilir kayıttan) türetilir — kullanıcı girdisinden değil.
        await set_tenant_context(session, result.organization_id)
        record_audit(
            session,
            tenant_id=result.organization_id,
            action=AuditAction.INVITATION_ACCEPTED,
            resource_type="invitation",
            resource_id=result.invitation_id,
            actor_user_id=result.user.id,
            meta={"account_created": result.account_created, "role": result.role.value},
        )
        # Token üretimi için ilkel değerleri transaction içinde yakala (commit sonrası
        # ORM nesneleri expire olur).
        user_id = result.user.id
        organization_id = result.organization_id
        role_value = result.role.value
        account_created = result.account_created

    tokens: TokenResponse | None = None
    if account_created:
        # Yeni hesap: az önce parola belirledi → otomatik giriş güvenli.
        access_token, expires_in = _issue_access_token(
            settings, user_id=user_id, tenant_id=organization_id, role=role_value
        )
        refresh_token = await _issue_refresh_token(
            redis, settings, user_id=user_id, tenant_id=organization_id, role=role_value
        )
        tokens = TokenResponse(
            access_token=access_token, expires_in=expires_in, refresh_token=refresh_token
        )
    return AcceptInvitationResponse(
        organization_id=organization_id, account_created=account_created, tokens=tokens
    )
