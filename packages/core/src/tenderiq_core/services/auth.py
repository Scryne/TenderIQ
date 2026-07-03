"""Kimlik doğrulama servisi: kayıt ve giriş (kiracı + kullanıcı + üyelik)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.models import Membership, Organization, Role, User
from tenderiq_core.security.passwords import hash_password, verify_password


class EmailAlreadyExistsError(Exception):
    """Bu e-posta ile bir kullanıcı zaten var."""


class SlugAlreadyExistsError(Exception):
    """Bu slug ile bir organizasyon zaten var."""


async def register(
    session: AsyncSession,
    *,
    org_name: str,
    org_slug: str,
    email: str,
    password: str,
    full_name: str | None = None,
) -> tuple[User, Membership]:
    """Yeni bir organizasyon + admin kullanıcı + üyelik oluşturur.

    Not: organization/user/membership RLS'siz kimlik tablolarıdır; kiracı bağlamı
    gerektirmez.
    """
    existing_user: User | None = await session.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise EmailAlreadyExistsError(email)
    existing_org: Organization | None = await session.scalar(
        select(Organization).where(Organization.slug == org_slug)
    )
    if existing_org is not None:
        raise SlugAlreadyExistsError(org_slug)

    organization = Organization(name=org_name, slug=org_slug)
    session.add(organization)
    await session.flush()

    user = User(email=email, full_name=full_name, hashed_password=hash_password(password))
    session.add(user)
    await session.flush()

    membership = Membership(user_id=user.id, organization_id=organization.id, role=Role.ADMIN)
    session.add(membership)
    await session.flush()
    return user, membership


async def authenticate(
    session: AsyncSession, *, email: str, password: str
) -> tuple[User, Membership] | None:
    """E-posta/parola doğrular; başarılıysa (kullanıcı, üyelik) döndürür."""
    user: User | None = await session.scalar(select(User).where(User.email == email))
    if user is None or user.hashed_password is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    membership: Membership | None = await session.scalar(
        select(Membership).where(Membership.user_id == user.id)
    )
    if membership is None:
        return None
    return user, membership
