"""Kimlik doğrulama servisi: kayıt ve giriş (kiracı + kullanıcı + üyelik).

E-posta, hesabın kimlik anahtarıdır ve **her zaman normalize edilmiş** (kırpılmış +
küçük harfe indirgenmiş) biçimde saklanır/aranır — bkz. ``normalize_email``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tenderiq_core.models import Membership, Organization, Role, User
from tenderiq_core.security.passwords import hash_password, verify_password

_dummy_hash_cache: str | None = None


def normalize_email(email: str) -> str:
    """E-postayı hesap kimliği olarak kullanılacak kanonik biçime indirger.

    RFC'ye göre local-part teorik olarak büyük/küçük harfe duyarlıdır, ama hiçbir
    yaygın sağlayıcı ayırt etmez; ayırt etmek pratikte iki soruna yol açar:
    ``A@x.com`` ve ``a@x.com`` AYRI hesap olarak kaydolabilir ve kullanıcı
    parolasını sıfırlayamaz (arama normalize edilmiş değerle yapılırdı, kayıt
    ham değerle). Bu yüzden tek kanonik biçim kullanılır — davet akışı
    (``services.invitations``) ve oran sınırlama anahtarları da aynı kuralı izler.
    """
    return email.strip().lower()


def _dummy_hash() -> str:
    """Kullanıcı bulunamadığında da özet doğrulaması koşmak için sabit özet.

    E-posta var/yok durumları arasındaki yanıt süresi farkını (kullanıcı
    numaralandırma yan-kanalı) kapatır. İlk çağrıda üretilir, sonra önbellekte.
    """
    global _dummy_hash_cache
    if _dummy_hash_cache is None:
        _dummy_hash_cache = hash_password("tenderiq-timing-equalizer")
    return _dummy_hash_cache


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
    gerektirmez. E-posta normalize edilerek saklanır (``normalize_email``).
    """
    email = normalize_email(email)
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
    """E-posta/parola doğrular; başarılıysa (kullanıcı, üyelik) döndürür.

    Pasif (``is_active=False``) kullanıcılar da parola doğru olsa bile reddedilir;
    çağırana tüm başarısızlıklar tek tip ``None`` döner (bilgi sızdırmaz).
    Arama normalize edilmiş e-posta ile yapılır: kullanıcı kayıttakinden farklı
    büyük/küçük harfle yazsa da girişi çalışır.
    """
    email = normalize_email(email)
    user: User | None = await session.scalar(select(User).where(User.email == email))
    if user is None or user.hashed_password is None:
        verify_password(password, _dummy_hash())
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    # Çoklu-org: giriş varsayılan olarak EN ERKEN katılınan üyeliği seçer
    # (deterministik; eskiden sırasız `first()` rastgele org seçebiliyordu).
    # Kullanıcı sonra `POST /auth/switch-org` ile aktif org'u değiştirebilir.
    membership: Membership | None = await session.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
    )
    if membership is None:
        return None
    return user, membership
