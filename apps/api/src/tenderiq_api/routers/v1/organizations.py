"""/api/v1/organizations — hesap (kiracı) yaşam döngüsü ve veri sahibi hakları.

İki KVKK yükümlülüğünü karşılar:
- **md. 7 (silme):** ``POST /current/close`` — hesabı ve tüm içeriğini siler.
- **md. 11 (erişim):** ``GET /current/export`` — kişisel verinin makine-okunur kopyası.

Kapatma yüzeyi bilinçli olarak dardır: geri dönüşü olmayan bir işlemin yüzeyi ne
kadar küçükse yanlışlıkla tetiklenmesi o kadar zordur.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update

from tenderiq_api.dependencies import (
    PrincipalDep,
    RedisDep,
    SettingsDep,
    TenantSessionDep,
    require_role,
)
from tenderiq_api.errors import ConflictError, NotFoundError, ValidationFailedError
from tenderiq_core.db.soft_delete import INCLUDE_DELETED
from tenderiq_core.models import (
    AuditAction,
    AuditLog,
    Document,
    FindingComment,
    Membership,
    Organization,
    Role,
    Tender,
    User,
)
from tenderiq_core.services import refresh_tokens
from tenderiq_core.services.audit import record_audit

router = APIRouter(prefix="/organizations", tags=["organizations"])

_admin = Depends(require_role(Role.ADMIN))


class OrganizationResponse(BaseModel):
    """Aktif organizasyon özeti."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class CloseAccountRequest(BaseModel):
    """Hesap kapatma onayı.

    Slug'ın elle yazılması istenir: tek tıkla geri alınamaz bir silme tetiklenmesin.
    """

    model_config = ConfigDict(extra="forbid")

    confirm_slug: str = Field(min_length=1, max_length=255)


class CloseAccountResponse(BaseModel):
    """Kapatma sonucu ve kalıcı silmenin ne zaman olacağı."""

    tenders_deleted: int
    purge_after_days: int


@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(
    session: TenantSessionDep, principal: PrincipalDep
) -> OrganizationResponse:
    """Aktif organizasyonu döndürür."""
    organization = await session.get(Organization, principal.tenant_id)
    if organization is None:
        raise NotFoundError("Organizasyon bulunamadı.")
    return OrganizationResponse.model_validate(organization)


@router.post(
    "/current/close",
    response_model=CloseAccountResponse,
    dependencies=[_admin],
)
async def close_current_organization(
    body: CloseAccountRequest,
    session: TenantSessionDep,
    principal: PrincipalDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> CloseAccountResponse:
    """Hesabı kapatır: organizasyon ve tüm içeriği silinmek üzere işaretlenir (KVKK md. 7).

    Yalnız **yönetici** çağırabilir ve organizasyonun slug'ını doğru yazması
    gerekir. Kapatma sonrası:

    - Organizasyon ve tüm ihaleler/dokümanlar anında görünmez olur.
    - Tüm üyelerin oturumları iptal edilir; bu organizasyona giriş yapılamaz.
      (Üyenin BAŞKA bir organizasyonu varsa oraya girmeye devam eder.)
    - ``DATA_RETENTION_DAYS`` sonunda içerik ve dosyalar KALICI silinir.

    **Fatura kayıtları ve denetim izi silinmez:** VUK gereği saklanması zorunlu
    olduğundan organizasyon satırı anonimleştirilmiş hâlde kalır. Bu, KVKK md. 7'nin
    kanuni saklama yükümlülüğü istisnasıdır ve aydınlatma metninde beyan edilir.

    Geri alma ucu **bilinçli olarak yoktur**: hesap kapatma nadir ve ağır bir
    işlemdir, yanlışlıkla yapıldıysa saklama penceresi içinde destek kanalından
    elle geri alınır (`organization.deleted_at = NULL`).
    """
    # ``include_deleted``: kapatılmış organizasyon varsayılan filtreyle görünmez
    # olurdu ve ikinci çağrı "bulunamadı" (404) derdi. Doğru cevap "zaten
    # kapatılmış" (409) — kullanıcıya ne olduğunu söylemek gerekir.
    organization = (
        await session.execute(
            select(Organization)
            .where(Organization.id == principal.tenant_id)
            .execution_options(**{INCLUDE_DELETED: True})
        )
    ).scalar_one_or_none()
    if organization is None:
        raise NotFoundError("Organizasyon bulunamadı.")
    if organization.deleted_at is not None:
        raise ConflictError("Bu organizasyon zaten kapatılmış.")
    if body.confirm_slug != organization.slug:
        raise ValidationFailedError(
            "Onay için organizasyon kısa adını (slug) birebir yazmalısınız."
        )

    now = datetime.now(UTC)
    # İhaleler ve dokümanlar da işaretlenir. Yalnız organizasyonu işaretlemek,
    # elinde geçerli (≤60 dk) erişim token'ı olan bir üyenin veriyi görmeye devam
    # etmesi demek olurdu; içerik işaretlenince o pencerede bile ortada veri kalmaz.
    organization.deleted_at = now
    tender_ids = list(
        (await session.execute(select(Tender.id).where(Tender.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    if tender_ids:
        await session.execute(
            update(Tender).where(Tender.id.in_(tender_ids)).values(deleted_at=now)
        )
    await session.execute(
        update(Document)
        .where(Document.deleted_at.is_(None))
        .values(deleted_at=now, deleted_with_tender=True)
    )
    tenders_deleted = len(tender_ids)

    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.ORGANIZATION_CLOSED,
        resource_type="organization",
        resource_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        meta={
            "slug": organization.slug,
            "tenders_deleted": tenders_deleted,
            "retention_days": settings.data_retention_days,
        },
    )
    await session.flush()

    # Oturumlar iptal: kapatılan hesabın üyeleri elindeki refresh token'la
    # devam edememeli. Erişim token'ı (≤60 dk) kendiliğinden ölür ve o pencerede
    # zaten görünecek veri kalmamıştır (içerik işaretlendi).
    member_ids = list(
        (
            await session.execute(
                select(Membership.user_id).where(Membership.organization_id == principal.tenant_id)
            )
        )
        .scalars()
        .all()
    )
    for user_id in member_ids:
        await refresh_tokens.revoke_all_for_user(redis, user_id)

    return CloseAccountResponse(
        tenders_deleted=tenders_deleted,
        purge_after_days=settings.data_retention_days,
    )


class ExportedAccount(BaseModel):
    """Kullanıcının hesap verisi."""

    id: uuid.UUID
    email: str
    full_name: str | None
    email_verified: bool
    is_active: bool
    created_at: datetime


class ExportedMembership(BaseModel):
    """Kullanıcının bir organizasyondaki üyeliği."""

    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    role: str
    joined_at: datetime


class ExportedComment(BaseModel):
    """Kullanıcının bir bulguya yazdığı yorum (kişisel veri: yazar + metin)."""

    id: uuid.UUID
    tender_id: uuid.UUID
    finding_kind: str
    finding_id: uuid.UUID
    body: str
    created_at: datetime


class ExportedDocument(BaseModel):
    """Doküman ENVANTERİ — dosyanın kendisi değil.

    Dosya içeriği bu dışa aktarmaya konmaz: yüzlerce megabaytlık PDF'leri JSON'a
    gömmek ne taşınabilir ne de yararlıdır. Kullanıcı dosyalarına inceleme
    ekranından zaten erişebilir; buradaki liste "hangi dosyalar işleniyor"
    sorusunu cevaplar (KVKK md. 11/b).
    """

    id: uuid.UUID
    tender_id: uuid.UUID
    filename: str
    content_type: str
    kind: str
    status: str
    size_bytes: int | None
    page_count: int | None
    created_at: datetime


class ExportedTender(BaseModel):
    """İhale envanteri."""

    id: uuid.UUID
    title: str
    status: str
    created_at: datetime


class ExportedAuditEntry(BaseModel):
    """Kullanıcının KENDİ yaptığı işlemlerin denetim kaydı."""

    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    created_at: datetime


class DataExportResponse(BaseModel):
    """KVKK md. 11 veri sahibi erişim hakkı — yapılandırılmış kopya.

    Kapsam bilinçli olarak "kişisel veri + envanter"dir. Çıkarılmış bulguların
    tamamı (binlerce satır) burada DEĞİLDİR: onlar kişisel veri değil, kullanıcının
    yüklediği dokümandan üretilen iş çıktısıdır ve Word/Excel export'uyla zaten
    alınabilir. Bu ayrım aydınlatma metninde de aynı şekilde anlatılmalıdır.
    """

    generated_at: datetime
    account: ExportedAccount
    memberships: list[ExportedMembership]
    active_organization_id: uuid.UUID
    tenders: list[ExportedTender]
    documents: list[ExportedDocument]
    comments: list[ExportedComment]
    audit_trail: list[ExportedAuditEntry]


@router.get("/current/export", response_model=DataExportResponse)
async def export_my_data(session: TenantSessionDep, principal: PrincipalDep) -> DataExportResponse:
    """Veri sahibinin kendi verisinin makine-okunur kopyasını döndürür (KVKK md. 11).

    Kapsam **aktif organizasyondur**: kullanıcı birden çok organizasyona üyeyse
    her biri için ayrı ayrı çağırır (org değiştirip tekrar ister). Bu bilinçlidir —
    RLS kiracı bağlamı tek org'a bağlıdır ve onu delip geçmek, izolasyonun tek
    dayanağını istisnaya çevirirdi.

    Yumuşak silinmiş kayıtlar dışa aktarmada GÖRÜNMEZ: kullanıcı onları zaten
    silmiştir, "işlenen veri" değildirler.
    """
    user = await session.get(User, principal.user_id)
    if user is None:
        raise NotFoundError("Kullanıcı bulunamadı.")

    membership_rows = (
        await session.execute(
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(Membership.user_id == principal.user_id)
            .order_by(Membership.created_at)
        )
    ).all()

    tenders = list(
        (await session.execute(select(Tender).order_by(Tender.created_at))).scalars().all()
    )
    documents = list(
        (await session.execute(select(Document).order_by(Document.created_at))).scalars().all()
    )
    comments = list(
        (
            await session.execute(
                select(FindingComment)
                .where(FindingComment.author_user_id == principal.user_id)
                .order_by(FindingComment.created_at)
            )
        )
        .scalars()
        .all()
    )
    audit_rows = list(
        (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.actor_user_id == principal.user_id)
                .order_by(AuditLog.created_at)
            )
        )
        .scalars()
        .all()
    )

    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.DATA_EXPORTED,
        resource_type="user_account",
        resource_id=principal.user_id,
        actor_user_id=principal.user_id,
    )
    await session.flush()

    return DataExportResponse(
        generated_at=datetime.now(UTC),
        account=ExportedAccount(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            email_verified=user.email_verified,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        memberships=[
            ExportedMembership(
                organization_id=organization.id,
                organization_name=organization.name,
                organization_slug=organization.slug,
                role=membership.role.value,
                joined_at=membership.created_at,
            )
            for membership, organization in membership_rows
        ],
        active_organization_id=principal.tenant_id,
        tenders=[
            ExportedTender(
                id=tender.id,
                title=tender.title,
                status=tender.status.value,
                created_at=tender.created_at,
            )
            for tender in tenders
        ],
        documents=[
            ExportedDocument(
                id=document.id,
                tender_id=document.tender_id,
                filename=document.filename,
                content_type=document.content_type,
                kind=document.kind.value,
                status=document.status.value,
                size_bytes=document.size_bytes,
                page_count=document.page_count,
                created_at=document.created_at,
            )
            for document in documents
        ],
        comments=[
            ExportedComment(
                id=comment.id,
                tender_id=comment.tender_id,
                finding_kind=comment.finding_kind.value,
                finding_id=comment.finding_id,
                body=comment.body,
                created_at=comment.created_at,
            )
            for comment in comments
        ],
        audit_trail=[
            ExportedAuditEntry(
                action=entry.action,
                resource_type=entry.resource_type,
                resource_id=entry.resource_id,
                created_at=entry.created_at,
            )
            for entry in audit_rows
        ],
    )
