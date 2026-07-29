"""Abonelik mutabakatı (Tur 6 / madde 2) — kritik yolun yedeği.

Checkout erişimi AÇMAZ; yetkilendirmeyi açan tek mekanizma webhook. Webhook hiç
gelmezse "ödeme alındı ama erişim açılmadı" hâli sessizce kalıcı olur. Bu
testler, o hâlin gerçekten onarıldığını ve **ters yönde otomatik kapatma
yapılmadığını** sabitler.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tenderiq_core.billing.fake import FakeBillingProvider
from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.billing.provider import ProviderSubscriptionState
from tenderiq_core.config import get_settings
from tenderiq_core.db import create_engine, create_session_factory
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.models import SubscriptionStatus
from tenderiq_core.services import billing as billing_service
from tenderiq_core.services import quota

pytestmark = pytest.mark.integration


@pytest.fixture
def reconcile_client(api_client: TestClient) -> Iterator[TestClient]:
    os.environ["BILLING_PROVIDER"] = "fake"
    get_settings.cache_clear()
    yield api_client
    get_settings.cache_clear()


def _register(client: TestClient, slug: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "org_name": slug,
            "org_slug": slug,
            "email": f"{slug}@org.com",
            "password": "sifre-12345",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["user"]["tenant_id"])


async def _seed_subscription(
    tenant_id: uuid.UUID, *, plan: PlanTier, status: SubscriptionStatus, reference: str
) -> None:
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        # RLS: kiracı bağlamı kurulmadan INSERT politikayı ihlal eder — bu
        # doğrudur ve testin kendisi o sözleşmeye uymalıdır.
        await set_tenant_context(session, tenant_id)
        await billing_service.apply_plan_change(
            session,
            tenant_id=tenant_id,
            plan=plan,
            status=status,
            provider="fake",
            provider_subscription_id=reference,
        )
    await engine.dispose()


async def _read_plan(tenant_id: uuid.UUID) -> tuple[PlanTier, SubscriptionStatus]:
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        await set_tenant_context(session, tenant_id)
        subscription = await quota.get_or_create_subscription(session, tenant_id)
        result = (subscription.plan, subscription.status)
    await engine.dispose()
    return result


async def _reconcile(
    provider: FakeBillingProvider, tenant_id: uuid.UUID
) -> billing_service.ReconcileReport:
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    async with factory() as session, session.begin():
        report = await billing_service.reconcile_subscriptions(
            session, provider, tenant_ids=[tenant_id]
        )
    await engine.dispose()
    return report


async def test_kayip_webhook_erisimi_acar(reconcile_client: TestClient) -> None:
    """Ödeme alınmış ama webhook gelmemiş: mutabakat erişimi AÇAR."""
    tenant_id = uuid.UUID(_register(reconcile_client, f"mut-ac-{uuid.uuid4().hex[:6]}"))
    await _seed_subscription(
        tenant_id, plan=PlanTier.FREE, status=SubscriptionStatus.ACTIVE, reference="sub-ac"
    )
    provider = FakeBillingProvider(
        remote_state={
            "sub-ac": ProviderSubscriptionState(
                status=SubscriptionStatus.ACTIVE, plan_tier=PlanTier.PRO
            )
        }
    )

    report = await _reconcile(provider, tenant_id)

    assert report.repaired == 1
    assert report.drift == 1
    assert (await _read_plan(tenant_id))[0] is PlanTier.PRO


async def test_kapatma_sapmasi_otomatik_uygulanmaz(reconcile_client: TestClient) -> None:
    """Yanlış kapatma müşteriye DOĞRUDAN zarar verir; yalnız raporlanır."""
    tenant_id = uuid.UUID(_register(reconcile_client, f"mut-kap-{uuid.uuid4().hex[:6]}"))
    await _seed_subscription(
        tenant_id, plan=PlanTier.PRO, status=SubscriptionStatus.ACTIVE, reference="sub-kap"
    )
    provider = FakeBillingProvider(
        remote_state={
            "sub-kap": ProviderSubscriptionState(
                status=SubscriptionStatus.CANCELED, plan_tier=PlanTier.FREE
            )
        }
    )

    report = await _reconcile(provider, tenant_id)

    assert report.needs_review == 1
    assert report.repaired == 0
    # Erişim KAPATILMADI: plan hâlâ pro ve durum aktif.
    plan, status = await _read_plan(tenant_id)
    assert plan is PlanTier.PRO
    assert status is SubscriptionStatus.ACTIVE


async def test_saglayicida_bulunamayan_abonelik_cozulmemis_sayilir(
    reconcile_client: TestClient,
) -> None:
    tenant_id = uuid.UUID(_register(reconcile_client, f"mut-yok-{uuid.uuid4().hex[:6]}"))
    await _seed_subscription(
        tenant_id, plan=PlanTier.PRO, status=SubscriptionStatus.ACTIVE, reference="sub-yok"
    )

    report = await _reconcile(FakeBillingProvider(), tenant_id)

    assert report.unresolved == 1
    assert report.repaired == 0


async def test_uyumlu_durumda_sapma_yok(reconcile_client: TestClient) -> None:
    """Mutabakat gürültü üretmemeli: her şey yerindeyse drift sıfır."""
    tenant_id = uuid.UUID(_register(reconcile_client, f"mut-ok-{uuid.uuid4().hex[:6]}"))
    await _seed_subscription(
        tenant_id, plan=PlanTier.PRO, status=SubscriptionStatus.ACTIVE, reference="sub-ok"
    )
    provider = FakeBillingProvider(
        remote_state={
            "sub-ok": ProviderSubscriptionState(
                status=SubscriptionStatus.ACTIVE, plan_tier=PlanTier.PRO
            )
        }
    )

    report = await _reconcile(provider, tenant_id)

    assert report.checked == 1
    assert report.drift == 0
