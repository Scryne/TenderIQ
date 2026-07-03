"""RLS kiracılar-arası izolasyon testi — Faz 0 çıkış kapısının kalbi.

Bir kiracının diğerinin verisini GÖREMEDİĞİNİ (ve bağlam yokken hiçbir şey
göremediğini) non-superuser app rolüyle doğrular. Container/rol kurulumu kök
`conftest.py`'deki `app_database_url` fixture'ından gelir. `integration` işaretli.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.models import Organization, Tender, TenderStatus

pytestmark = pytest.mark.integration


async def test_tenant_isolation(app_database_url: str) -> None:
    """Bir kiracı yalnızca kendi ihalelerini görür; bağlam yoksa hiçbirini."""
    engine = create_async_engine(app_database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        # İki organizasyon (Organization RLS'siz — serbestçe oluşturulur)
        async with factory() as session, session.begin():
            org_a = Organization(name="Firma A", slug="rls-firma-a")
            org_b = Organization(name="Firma B", slug="rls-firma-b")
            session.add_all([org_a, org_b])
        a_id = org_a.id
        b_id = org_b.id

        # Her kiracı KENDİ bağlamında bir Tender ekler (RLS WITH CHECK doğrular)
        async with factory() as session, session.begin():
            await set_tenant_context(session, a_id)
            session.add(Tender(tenant_id=a_id, title="A İhalesi", status=TenderStatus.DRAFT))
        async with factory() as session, session.begin():
            await set_tenant_context(session, b_id)
            session.add(Tender(tenant_id=b_id, title="B İhalesi", status=TenderStatus.DRAFT))

        # Kiracı A yalnızca kendi ihalesini görür
        async with factory() as session, session.begin():
            await set_tenant_context(session, a_id)
            titles_a = list((await session.execute(select(Tender.title))).scalars().all())
        assert titles_a == ["A İhalesi"]

        # Kiracı B yalnızca kendi ihalesini görür
        async with factory() as session, session.begin():
            await set_tenant_context(session, b_id)
            titles_b = list((await session.execute(select(Tender.title))).scalars().all())
        assert titles_b == ["B İhalesi"]

        # Bağlam yokken (fail-closed) hiçbir satır görünmez
        async with factory() as session, session.begin():
            total = (await session.execute(select(func.count()).select_from(Tender))).scalar_one()
        assert total == 0
    finally:
        await engine.dispose()
