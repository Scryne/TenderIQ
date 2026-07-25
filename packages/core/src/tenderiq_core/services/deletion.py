"""İki fazlı silme (KVKK §8.3) — yumuşak silme, geri alma ve kalıcı süpürme.

**Faz 1 — yumuşak silme (kullanıcı eylemi).** ``deleted_at`` işaretlenir. Satır
tüm okuma yollarından anında düşer (``tenderiq_core.db.soft_delete``), yani
kullanıcı açısından silinmiştir. Nesne depolamadaki dosyaya bu fazda DOKUNULMAZ:
geri alma mümkün olmalı ve dosyayı silmek geri alınamaz.

**Faz 2 — kalıcı süpürme (zamanlanmış).** ``DATA_RETENTION_DAYS`` dolunca satır
ve dosyalar KALICI silinir. Sıralama önemlidir: **önce nesne depolama, sonra DB**.
Tersi yapılırsa DB satırı gidince ``storage_key`` kaybolur ve dosya depoda
sonsuza dek yetim kalır — KVKK açısından "sildim" demek artık doğru olmaz.
Nesne silme başarısız olursa DB satırı BIRAKILIR ve bir sonraki koşuda yeniden
denenir; yetim dosya bırakmaktansa silmeyi ertelemek yeğdir.

DB tarafında kademeli silme ayrıca kodlanmaz: FK'ler ``ON DELETE CASCADE``
tanımlıdır (tender → document → chunk → embedding, parsed_element, job ve beş
bulgu tablosu). Tek ``DELETE FROM tender`` zinciri götürür.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from tenderiq_core.db.soft_delete import INCLUDE_DELETED
from tenderiq_core.models import (
    CapabilityProfile,
    Document,
    Invitation,
    Membership,
    Organization,
    Tender,
    User,
)

__all__ = [
    "DeleteObject",
    "OrganizationPurgeResult",
    "PurgeResult",
    "collect_purgeable",
    "collect_purgeable_organizations",
    "purge_cutoff",
    "purge_organization_sync",
    "purge_tenant_sync",
]

#: Nesne depolamadan tek anahtar siler; başarılıysa ``True``.
DeleteObject = Callable[[str], bool]

#: Kapatılıp anonimleştirilmiş organizasyonun slug ön eki (mezar taşı işareti).
#: Süpürmenin idempotent olmasını sağlar: bu ön eki taşıyan satır tekrar işlenmez.
_TOMBSTONE_PREFIX = "deleted-"


@dataclass
class PurgeResult:
    """Bir kiracıda süpürülenlerin özeti (loglama ve denetim kaydı için)."""

    tenders: int = 0
    documents: int = 0
    objects_deleted: int = 0
    objects_failed: int = 0
    tender_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def anything(self) -> bool:
        return bool(self.tenders or self.documents or self.objects_deleted)


def purge_cutoff(retention_days: int, *, now: datetime | None = None) -> datetime:
    """Bu andan önce silinmiş işaretlenenler kalıcı silinmeye hak kazanır."""
    return (now or datetime.now(UTC)) - timedelta(days=retention_days)


def collect_purgeable(session: Session, cutoff: datetime) -> tuple[list[Tender], list[Document]]:
    """Saklama penceresi dolmuş ihale ve dokümanları getirir.

    ``include_deleted`` opt-out'u burada ZORUNLUDUR: varsayılan filtre tam da bu
    satırları gizler, dolayısıyla opt-out olmadan süpürme işi hiçbir zaman bir şey
    bulamaz (ve sessizce "temiz" raporlar).
    """
    tenders = list(
        session.scalars(
            select(Tender)
            .where(Tender.deleted_at.is_not(None), Tender.deleted_at < cutoff)
            .execution_options(**{INCLUDE_DELETED: True})
        )
    )
    # Ayrıca ihalesi silinmemiş ama KENDİSİ silinmiş dokümanlar.
    documents = list(
        session.scalars(
            select(Document)
            .where(Document.deleted_at.is_not(None), Document.deleted_at < cutoff)
            .execution_options(**{INCLUDE_DELETED: True})
        )
    )
    return tenders, documents


def _documents_of(session: Session, tender_ids: Sequence[uuid.UUID]) -> list[Document]:
    """Verilen ihalelerin TÜM dokümanları (silinmiş olanlar dâhil).

    Silinmemiş dokümanlar da gelmelidir: ihale kalıcı silindiğinde CASCADE onların
    satırlarını da götürür, dolayısıyla dosyaları da silinmelidir.
    """
    if not tender_ids:
        return []
    return list(
        session.scalars(
            select(Document)
            .where(Document.tender_id.in_(tender_ids))
            .execution_options(**{INCLUDE_DELETED: True})
        )
    )


def purge_tenant_sync(
    session: Session,
    *,
    cutoff: datetime,
    delete_object: DeleteObject,
) -> PurgeResult:
    """Bir kiracının süresi dolmuş silmelerini kalıcılaştırır (senkron/worker).

    ``delete_object`` nesne depolamadan tek bir anahtarı silen çağrılabilirdir;
    ``True`` dönerse silinmiş sayılır. Depolama yapılandırılmamışsa çağıran
    tarafın bunu bilerek geçmesi gerekir — bu fonksiyon depoyu kendisi kurmaz
    (test edilebilirlik ve senkron/async ayrımı için).
    """
    result = PurgeResult()
    tenders, orphan_documents = collect_purgeable(session, cutoff)

    tender_ids = [tender.id for tender in tenders]
    documents = _documents_of(session, tender_ids)

    # Yalnız kendisi silinmiş dokümanlar (ihalesi ayakta) — çift saymayı önle.
    known = {document.id for document in documents}
    documents += [doc for doc in orphan_documents if doc.id not in known]

    # 1) ÖNCE nesne depolama. Başarısız olan anahtarın DB satırı bu turda
    #    silinmez; aksi hâlde depoda erişilemez bir dosya kalırdı.
    failed_documents: set[uuid.UUID] = set()
    for document in documents:
        if delete_object(document.storage_key):
            result.objects_deleted += 1
        else:
            result.objects_failed += 1
            failed_documents.add(document.id)

    blocked_tenders = {
        document.tender_id for document in documents if document.id in failed_documents
    }

    # 2) SONRA DB satırları (CASCADE alt tabloları götürür).
    purgeable_tender_ids = [tid for tid in tender_ids if tid not in blocked_tenders]
    if purgeable_tender_ids:
        session.execute(delete(Tender).where(Tender.id.in_(purgeable_tender_ids)))
        result.tenders = len(purgeable_tender_ids)
        result.tender_ids = purgeable_tender_ids

    orphan_ids = [
        document.id
        for document in orphan_documents
        if document.id not in failed_documents and document.tender_id not in blocked_tenders
    ]
    if orphan_ids:
        session.execute(delete(Document).where(Document.id.in_(orphan_ids)))
        result.documents = len(orphan_ids)

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Organizasyon (hesap) kapatma — KVKK md. 7
#
# Buradaki asıl gerilim: silme hakkı ile KANUNİ SAKLAMA yükümlülüğü çakışır.
# ``TenantMixin`` her kiracı tablosunu ``organization.id``'ye CASCADE ile bağlar,
# dolayısıyla organizasyon satırını silmek ``subscription``, ``usage_record`` ve
# ``audit_log``'u da götürür. Fatura/defter kayıtları VUK gereği 10 yıl saklanır;
# KVKK md. 7 de kanuni saklama yükümlülüğü olan veriyi istisna tutar.
#
# Çözüm: satır **mezar taşı** olarak kalır. Kiracının İÇERİĞİ (ihale, doküman,
# bulgu, dosya, üyelik, davet, yetkinlik profili) kalıcı silinir; organizasyonun
# adı/slug'ı anonimleştirilir; fatura ve denetim kayıtları durur.
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class OrganizationPurgeResult:
    """Bir organizasyon kapatmasında kalıcı silinenlerin özeti."""

    tenders: int = 0
    objects_deleted: int = 0
    objects_failed: int = 0
    memberships: int = 0
    invitations: int = 0
    users_deleted: int = 0
    anonymized: bool = False


def collect_purgeable_organizations(session: Session, cutoff: datetime) -> list[Organization]:
    """Saklama penceresi dolmuş, kapatılmış organizasyonlar.

    Zaten anonimleştirilmiş olanlar (``slug`` mezar taşı biçiminde) tekrar
    işlenmez; süpürme idempotenttir.
    """
    return list(
        session.scalars(
            select(Organization)
            .where(
                Organization.deleted_at.is_not(None),
                Organization.deleted_at < cutoff,
                Organization.slug.not_like(f"{_TOMBSTONE_PREFIX}%"),
            )
            .execution_options(**{INCLUDE_DELETED: True})
        )
    )


def purge_organization_sync(
    session: Session,
    organization: Organization,
    *,
    delete_object: DeleteObject,
) -> OrganizationPurgeResult:
    """Kapatılmış bir organizasyonun içeriğini KALICI siler (kiracı bağlamında çağrılır).

    Silinenler: nesne depolamadaki dosyalar → ihaleler (CASCADE ile doküman,
    öğe, chunk, embedding, iş, bulgular, yorumlar) → yetkinlik profili → davetler
    → üyelikler → başka üyeliği kalmayan kullanıcı hesapları.

    Korunanlar: ``subscription``, ``usage_record``, ``audit_log`` ve
    organizasyon satırının kendisi (anonimleştirilmiş hâlde).
    """
    result = OrganizationPurgeResult()
    opts = {INCLUDE_DELETED: True}

    # 1) Dosyalar önce (bkz. purge_tenant_sync'teki sıra gerekçesi).
    documents = list(session.scalars(select(Document).execution_options(**opts)))
    for document in documents:
        if delete_object(document.storage_key):
            result.objects_deleted += 1
        else:
            result.objects_failed += 1

    # Bir dosya bile silinemediyse DB'ye dokunma: anahtarları kaybedersek dosyalar
    # depoda yetim kalır ve bir daha bulunamaz. Sonraki koşu yeniden dener.
    if result.objects_failed:
        return result

    tender_ids = list(session.scalars(select(Tender.id).execution_options(**opts)))
    if tender_ids:
        session.execute(delete(Tender).where(Tender.id.in_(tender_ids)))
        result.tenders = len(tender_ids)

    session.execute(delete(CapabilityProfile))
    session.execute(delete(Invitation).where(Invitation.organization_id == organization.id))

    member_user_ids = list(
        session.scalars(
            select(Membership.user_id).where(Membership.organization_id == organization.id)
        )
    )
    session.execute(delete(Membership).where(Membership.organization_id == organization.id))
    result.memberships = len(member_user_ids)

    # 2) Başka hiçbir organizasyonda üyeliği kalmayan kullanıcılar: hesabın
    #    varlık sebebi kalmadı, kişisel veri silinir. Denetim kaydındaki
    #    ``actor_user_id`` FK'si ON DELETE SET NULL olduğundan iz kaybolmaz,
    #    yalnız kime ait olduğu anonimleşir — istenen de budur.
    for user_id in member_user_ids:
        remaining = session.scalar(
            select(func.count()).select_from(Membership).where(Membership.user_id == user_id)
        )
        if remaining:
            continue
        session.execute(delete(User).where(User.id == user_id))
        result.users_deleted += 1

    # 3) Mezar taşı: ad ve slug anonimleştirilir, satır durur (fatura/denetim FK'leri).
    organization.name = "Kapatılmış organizasyon"
    organization.slug = f"{_TOMBSTONE_PREFIX}{organization.id}"
    result.anonymized = True
    return result
