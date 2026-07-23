"""Üye daveti servisi (Sprint 3.3-E-2) — oluşturma, önizleme (lookup) ve kabul.

Davet, ``Invitation`` (RLS'siz kimlik tablosu) satırıdır; ham token e-postayla
gider, DB'de yalnız SHA-256 **özeti** tutulur. Kabul (accept) kimliksiz çalışır:
davet edilen e-postaya karşılık bir kullanıcı yoksa parola belirlenerek yeni hesap
açılır (davet linki e-posta sahipliğini kanıtladığından ``email_verified=True``),
varsa yalnızca üyelik eklenir. İş orkestrasyonu buradadır; HTTP/e-posta/oran-sınırı
ve denetim (audit) bağlamı router'ın sorumluluğundadır.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.models import (
    Invitation,
    InvitationStatus,
    Membership,
    Organization,
    Role,
    User,
)
from tenderiq_core.security.passwords import hash_password

_TOKEN_BYTES = 32  # 256-bit entropi


class InvitationError(Exception):
    """Davet iş kuralı hatalarının temeli."""


class InvitationNotFoundError(InvitationError):
    """Token'a karşılık gelen davet yok."""


class InvitationNotPendingError(InvitationError):
    """Davet zaten kabul edilmiş veya iptal edilmiş (tek-kullanımlık)."""


class InvitationExpiredError(InvitationError):
    """Davetin süresi dolmuş."""


class EmailAlreadyMemberError(InvitationError):
    """Bu e-posta zaten organizasyonun üyesi."""


class PasswordRequiredError(InvitationError):
    """Yeni hesap için parola gerekli (davet edilen kullanıcı henüz kayıtlı değil)."""


def _hash_token(token: str) -> str:
    """Ham token'ın SHA-256 hex özeti (DB'de saklanan biçim)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def _find_active_member(
    session: AsyncSession, *, organization_id: uuid.UUID, email: str
) -> User | None:
    """E-posta bu organizasyonda aktif üye mi? (case-insensitive) — üyeyse User döner."""
    member: User | None = await session.scalar(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.organization_id == organization_id,
            func.lower(User.email) == email,
        )
    )
    return member


async def create_invitation(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    email: str,
    role: Role,
    invited_by_user_id: uuid.UUID | None,
    ttl_hours: int,
) -> tuple[Invitation, str]:
    """Bir davet oluşturur ve (davet, ham_token) döndürür.

    E-posta zaten üyeyse ``EmailAlreadyMemberError``. Aynı e-posta için bekleyen
    (PENDING) bir davet varsa süperse edilir (eskisi REVOKED, yenisi üretilir) —
    bu davranış aynı zamanda "yeniden gönder" işlevi görür.
    """
    normalized = _normalize_email(email)
    if await _find_active_member(session, organization_id=organization_id, email=normalized):
        raise EmailAlreadyMemberError(normalized)

    # Aynı (org, e-posta) için bekleyen davetleri süperse et (tek aktif davet).
    stale = (
        await session.scalars(
            select(Invitation).where(
                Invitation.organization_id == organization_id,
                func.lower(Invitation.email) == normalized,
                Invitation.status == InvitationStatus.PENDING,
            )
        )
    ).all()
    for old in stale:
        old.status = InvitationStatus.REVOKED

    token = secrets.token_urlsafe(_TOKEN_BYTES)
    invitation = Invitation(
        organization_id=organization_id,
        email=normalized,
        role=role,
        token_hash=_hash_token(token),
        status=InvitationStatus.PENDING,
        expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
        invited_by_user_id=invited_by_user_id,
    )
    session.add(invitation)
    await session.flush()
    return invitation, token


async def _load_pending(session: AsyncSession, *, token: str) -> Invitation:
    """Token'a karşılık gelen daveti yükler ve PENDING + süresi geçmemiş olduğunu doğrular."""
    invitation: Invitation | None = await session.scalar(
        select(Invitation).where(Invitation.token_hash == _hash_token(token))
    )
    if invitation is None:
        raise InvitationNotFoundError
    if invitation.status is not InvitationStatus.PENDING:
        raise InvitationNotPendingError
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:  # DB timezone-aware döner; savunmacı normalize
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise InvitationExpiredError
    return invitation


@dataclass(frozen=True)
class InvitationPreview:
    """Kabul ekranı için davetin kimliksiz önizlemesi."""

    organization_id: uuid.UUID
    organization_name: str
    email: str
    role: Role
    account_exists: bool  # e-postanın zaten bir hesabı var mı (parola istenmez)


async def lookup_invitation(session: AsyncSession, *, token: str) -> InvitationPreview:
    """Geçerli bir daveti önizler (kimliksiz). Geçersiz/süresi dolmuş → hata yükseltir."""
    invitation = await _load_pending(session, token=token)
    org = await session.get(Organization, invitation.organization_id)
    if org is None:  # pragma: no cover - FK bütünlüğü gereği olmamalı
        raise InvitationNotFoundError
    account: User | None = await session.scalar(
        select(User).where(func.lower(User.email) == invitation.email)
    )
    return InvitationPreview(
        organization_id=org.id,
        organization_name=org.name,
        email=invitation.email,
        role=invitation.role,
        account_exists=account is not None,
    )


@dataclass(frozen=True)
class AcceptResult:
    """Kabul sonucu: kullanıcı, oluşan/var olan üyelik ve yeni-hesap işareti."""

    user: User
    membership: Membership
    invitation_id: uuid.UUID
    organization_id: uuid.UUID
    role: Role
    account_created: bool


async def accept_invitation(
    session: AsyncSession,
    *,
    token: str,
    full_name: str | None,
    password: str | None,
) -> AcceptResult:
    """Bir daveti kabul eder: kullanıcıyı bulur/oluşturur ve üyelik ekler.

    Kullanıcı yoksa ``password`` zorunludur (``PasswordRequiredError``); yeni hesap
    ``email_verified=True`` açılır (davet linki e-posta sahipliğini kanıtlar). Kullanıcı
    zaten üyeyse mevcut üyelik korunur (rol değişmez), davet yine de tüketilir.
    """
    invitation = await _load_pending(session, token=token)

    user: User | None = await session.scalar(
        select(User).where(func.lower(User.email) == invitation.email)
    )
    account_created = False
    if user is None:
        if not password:
            raise PasswordRequiredError
        user = User(
            email=invitation.email,
            full_name=full_name,
            hashed_password=hash_password(password),
            email_verified=True,
        )
        session.add(user)
        await session.flush()
        account_created = True

    membership: Membership | None = await session.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == invitation.organization_id,
        )
    )
    if membership is None:
        membership = Membership(
            user_id=user.id,
            organization_id=invitation.organization_id,
            role=invitation.role,
        )
        session.add(membership)
        await session.flush()

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = datetime.now(UTC)
    await session.flush()
    return AcceptResult(
        user=user,
        membership=membership,
        invitation_id=invitation.id,
        organization_id=invitation.organization_id,
        role=membership.role,
        account_created=account_created,
    )
