"""E2E test verisi tohumlar: incelemeye-hazır bir ihale + tohumlanmış bulgular.

Playwright E2E'si (``apps/web/e2e``) için deterministik, taşınabilir bir başlangıç
durumu kurar: bilinen parolalı bir admin kullanıcı + incele→onayla→export akışının
gerektirdiği bulgular (2 gereksinim + 1 risk, hepsi kaynağa bağlı [grounded]).

Uygulamanın ``DATABASE_URL``'ini (RLS'ye tabi ``tenderiq_app`` rolü) kullanır; tam
yığın ayaktayken (``docker compose up``) çalıştırılır:

    uv run python scripts/seed_e2e.py

Çıktı: kiracı/ihale kimlikleri + giriş bilgileri (E2E bunları ``E2E_*`` ortam
değişkenlerinden okur; script varsayılanlarla eşleşir). Yeniden çalıştırmak
güvenlidir (idempotent): var olan kayıtlar yeniden kullanılır.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tenderiq_core.db import (
    create_sync_engine,
    create_sync_session_factory,
    set_tenant_context_sync,
)
from tenderiq_core.findings import (
    GroundingResolution,
    RequirementKind,
    RiskCategory,
    RiskSeverity,
)
from tenderiq_core.models import (
    Document,
    DocumentKind,
    DocumentStatus,
    Membership,
    Organization,
    ParsedElement,
    Requirement,
    RiskFlag,
    Role,
    Tender,
    TenderStatus,
    User,
)
from tenderiq_core.parsing.types import ElementKind, ParseSource
from tenderiq_core.security.passwords import hash_password

# E2E ile paylaşılan sabitler (apps/web/e2e/review-export.spec.ts ile eşleşir).
E2E_EMAIL = "e2e@tenderiq.local"
E2E_PASSWORD = "e2e-password-123"  # noqa: S105  (yalnız yerel E2E tohum parolası)
E2E_ORG_NAME = "E2E Test Org"
E2E_ORG_SLUG = "tiq-e2e"
E2E_TENDER_TITLE = "E2E İnceleme İhalesi"
QUOTE = "Yüklenici tüm idari maddeleri eksiksiz karşılamak zorundadır."


def _seed_identity(factory: sessionmaker[Session]) -> tuple[uuid.UUID, uuid.UUID]:
    """Org + admin kullanıcı + üyelik (RLS'siz kimlik tabloları). (tenant_id, user_id)."""
    with factory() as session, session.begin():
        org = session.scalar(select(Organization).where(Organization.slug == E2E_ORG_SLUG))
        if org is None:
            org = Organization(name=E2E_ORG_NAME, slug=E2E_ORG_SLUG)
            session.add(org)
            session.flush()
        user = session.scalar(select(User).where(User.email == E2E_EMAIL))
        if user is None:
            user = User(
                email=E2E_EMAIL,
                full_name="E2E Test Kullanıcısı",
                hashed_password=hash_password(E2E_PASSWORD),
                email_verified=True,
            )
            session.add(user)
            session.flush()
        membership = session.scalar(
            select(Membership).where(
                Membership.user_id == user.id, Membership.organization_id == org.id
            )
        )
        if membership is None:
            session.add(
                Membership(user_id=user.id, organization_id=org.id, role=Role.ADMIN)
            )
        return org.id, user.id


def _seed_findings(
    factory: sessionmaker[Session], tenant_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    """İncelemeye-hazır ihale + doküman + parsed element + bulgular. tender_id döner."""
    with factory() as session, session.begin():
        set_tenant_context_sync(session, tenant_id)
        tender = session.scalar(select(Tender).where(Tender.title == E2E_TENDER_TITLE))
        if tender is not None:
            existing = session.scalar(select(Requirement).where(Requirement.tender_id == tender.id))
            if existing is not None:
                return tender.id  # zaten tohumlanmış
        else:
            tender = Tender(
                tenant_id=tenant_id,
                title=E2E_TENDER_TITLE,
                status=TenderStatus.REVIEW_READY,
                created_by=user_id,
            )
            session.add(tender)
            session.flush()

        document = Document(
            tenant_id=tenant_id,
            tender_id=tender.id,
            filename="sartname.pdf",
            content_type="application/pdf",
            storage_key=f"{tenant_id}/{tender.id}/{uuid.uuid4()}/sartname.pdf",
            kind=DocumentKind.ADMINISTRATIVE,
            status=DocumentStatus.UPLOADED,
            size_bytes=2048,
        )
        session.add(document)
        session.flush()

        element = ParsedElement(
            tenant_id=tenant_id,
            document_id=document.id,
            seq=0,
            page=4,
            kind=ElementKind.PARAGRAPH,
            source=ParseSource.DIGITAL,
            text=QUOTE,
            section="Madde 7.2",
            bbox_x0=72.0,
            bbox_y0=120.0,
            bbox_x1=480.0,
            bbox_y1=150.0,
        )
        session.add(element)
        session.flush()

        common = {
            "tenant_id": tenant_id,
            "tender_id": tender.id,
            "document_id": document.id,
            "source_element_id": element.id,
            "grounding_resolution": GroundingResolution.ELEMENT,
            "source_quote": QUOTE,
        }
        session.add(
            Requirement(
                seq=0,
                text="Yüklenici tüm idari maddeleri karşılamalıdır.",
                kind=RequirementKind.ADMINISTRATIVE,
                is_mandatory=True,
                **common,
            )
        )
        session.add(
            Requirement(
                seq=1,
                text="Geçici teminat mektubu sunulmalıdır.",
                kind=RequirementKind.FINANCIAL,
                is_mandatory=True,
                **common,
            )
        )
        session.add(
            RiskFlag(
                seq=0,
                text="Gecikme cezası oranı yüksektir.",
                severity=RiskSeverity.HIGH,
                category=RiskCategory.PENALTY,
                **common,
            )
        )
        return tender.id


def main() -> None:
    engine = create_sync_engine()
    factory = create_sync_session_factory(engine)
    tenant_id, user_id = _seed_identity(factory)
    tender_id = _seed_findings(factory, tenant_id, user_id)
    engine.dispose()

    print("E2E tohumlama tamam.")
    print(f"  E2E_EMAIL={E2E_EMAIL}")
    print(f"  E2E_PASSWORD={E2E_PASSWORD}")
    print(f"  tenant_id={tenant_id}")
    print(f"  tender_id={tender_id}")


if __name__ == "__main__":
    main()
