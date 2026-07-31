"""Abonelik yaşam döngüsü (Tur 7 / madde 1) — iptal, geri alma, plan değişimi.

`/sartlar` §3 üç şey taahhüt eder ve bu dosya üçünün de GERÇEKTEN olduğunu
sabitler:

1. Yükseltme anında etkilidir,
2. Düşürme dönem sonunda uygulanır,
3. İptal dönem sonunda erişimi keser — ondan ÖNCE kesmez.

Üçüncüsü yayın engelinin kendisidir: kullanıcının kendi iptal edebildiği bir yol
olmadan `/sartlar`ın 14 gün koşulsuz cayma taahhüdü tutulamaz.

Gerçek HTTP (TestClient) + gerçek DB (testcontainers) + RLS. Sağlayıcı olarak
``manual`` (test-modu) kullanılır: ağ geçidi olmadan tüm yaşam döngüsü bizim
aynamızda döner. Sağlayıcıya HANGİ operasyonun HANGİ argümanla gittiği ise
``fake`` sağlayıcıyla servis seviyesinde doğrulanır (aşağıdaki son bölüm) —
HTTP katmanı her istekte yeni bir sağlayıcı ürettiği için çağrılar oradan
gözlenemez.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.orm import Session

from tenderiq_core.billing.fake import FakeBillingProvider
from tenderiq_core.billing.plans import PLANS, PlanTier
from tenderiq_core.config import get_settings
from tenderiq_core.db import create_engine, create_session_factory
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.models import Membership, Role, SubscriptionStatus
from tenderiq_core.services import billing as billing_service
from tenderiq_core.services import quota

pytestmark = pytest.mark.integration


@pytest.fixture
def lifecycle_client(api_client: TestClient) -> Iterator[TestClient]:
    """``BILLING_PROVIDER=manual`` sabitlenmiş istemci.

    Açıkça sabitlenir çünkü ``Settings`` ``.env``i de okur: geliştirici
    makinesinde gerçek bir sağlayıcı seçiliyse bu testler onun yapılandırmasına
    düşer ve sınamak istedikleri semantiği hiç görmezler.
    """
    previous = os.environ.get("BILLING_PROVIDER")
    os.environ["BILLING_PROVIDER"] = "manual"
    get_settings.cache_clear()
    try:
        yield api_client
    finally:
        if previous is None:
            os.environ.pop("BILLING_PROVIDER", None)
        else:
            os.environ["BILLING_PROVIDER"] = previous
        get_settings.cache_clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient, *, slug: str) -> tuple[str, str, str]:
    """Kayıt + giriş; (kiracı_id, kullanıcı_id, token) döndürür."""
    email = f"{slug}@org.com"
    register = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert register.status_code == 201, register.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert login.status_code == 200, login.text
    user = register.json()["user"]
    return user["tenant_id"], user["id"], login.json()["access_token"]


def _upgrade(client: TestClient, token: str, plan: str) -> dict[str, object]:
    response = client.post("/api/v1/billing/checkout", json={"plan": plan}, headers=_auth(token))
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def _subscription(client: TestClient, token: str) -> dict[str, object]:
    response = client.get("/api/v1/billing/subscription", headers=_auth(token))
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def _slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


def test_ucretli_abonelikte_siradaki_tahsilat_tarihi_vardir(
    lifecycle_client: TestClient,
) -> None:
    """Ücretli bir aboneliğin yenileme tarihi OLMAK zorunda.

    Arayüz "sıradaki tahsilat"ı bu alandan gösterir; tarihsiz bir abonelikte
    iptal edildiğinde erişimin ne zaman biteceği de söylenemezdi.
    """
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("tah"))

    free = _subscription(lifecycle_client, token)
    assert free["next_charge_at"] is None  # ücretsiz planda tahsilat yok
    assert free["can_cancel"] is False

    _upgrade(lifecycle_client, token, "pro")
    paid = _subscription(lifecycle_client, token)
    assert paid["next_charge_at"] is not None
    assert paid["current_period_end"] == paid["next_charge_at"]
    assert paid["can_cancel"] is True


# ── İptal: dönem sonunda biter, ÖNCESİNDE erişim sürer ───────────────────────


def test_iptal_erisimi_hemen_kesmez_donem_sonuna_kadar_surer(
    lifecycle_client: TestClient,
) -> None:
    """Yayın engelinin çekirdeği: kullanıcı kendi iptal edebilir, erişim sürer."""
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("ipt"))
    _upgrade(lifecycle_client, token, "pro")

    response = lifecycle_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["cancel_at_period_end"] is True
    # Plan ve durum DEĞİŞMEDİ: müşteri ödediği dönemin hakkını kullanır.
    assert body["plan"] == "pro"
    assert body["status"] == "active"
    # Kullanıcıya gösterilecek tarih var; olmadan "erişiminiz şu tarihe kadar"
    # denemezdi ve dönem sonu görevi de aboneliği hiç bitiremezdi.
    assert body["current_period_end"] is not None
    # İptal edene "sıradaki tahsilat" göstermek yanlış olurdu.
    assert body["next_charge_at"] is None
    assert body["can_resume"] is True
    assert body["can_cancel"] is False

    # Kota katmanı da hâlâ PRO limitlerini veriyor.
    usage = lifecycle_client.get("/api/v1/usage", headers=_auth(token)).json()
    assert usage["plan"] == "pro"
    assert usage["documents"]["limit"] == PLANS[PlanTier.PRO].documents_per_month


def test_iptal_geri_alinabilir(lifecycle_client: TestClient) -> None:
    """İptal, başlatmak kadar kolay geri alınabilmeli (karanlık desen yok)."""
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("geri"))
    _upgrade(lifecycle_client, token, "pro")
    lifecycle_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))

    response = lifecycle_client.post("/api/v1/billing/subscription/resume", headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["cancel_at_period_end"] is False
    assert body["plan"] == "pro"
    assert body["next_charge_at"] is not None  # yenileme yeniden gündemde
    assert body["can_cancel"] is True
    assert body["can_resume"] is False


def test_ucretsiz_planda_iptal_edilecek_bir_sey_yok(lifecycle_client: TestClient) -> None:
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("uc"))

    response = lifecycle_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "conflict"


def test_ikinci_iptal_cakisma_dondurur(lifecycle_client: TestClient) -> None:
    """Tekrarlanan iptal sessizce başarılı görünmemeli — durum değişmediği hâlde
    kullanıcı bir şey olduğunu sanır."""
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("iki"))
    _upgrade(lifecycle_client, token, "pro")
    first = lifecycle_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))
    assert first.status_code == 200

    second = lifecycle_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))
    assert second.status_code == 409, second.text


def test_iptal_edilmemis_abonelik_geri_alinamaz(lifecycle_client: TestClient) -> None:
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("gerihata"))
    _upgrade(lifecycle_client, token, "pro")

    response = lifecycle_client.post("/api/v1/billing/subscription/resume", headers=_auth(token))
    assert response.status_code == 409, response.text


# ── Plan değişimi: yükseltme anında, düşürme dönem sonunda ───────────────────


def test_yukseltme_aninda_etkilidir(lifecycle_client: TestClient) -> None:
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("yuk"))
    _upgrade(lifecycle_client, token, "pro")

    body = _upgrade(lifecycle_client, token, "enterprise")
    assert body["activated"] is True
    assert body["effective_at"] is None

    usage = lifecycle_client.get("/api/v1/usage", headers=_auth(token)).json()
    assert usage["plan"] == "enterprise"
    assert usage["documents"]["limit"] is None  # sınırsız


def test_dusurme_donem_sonunda_uygulanir_kota_bu_donem_degismez(
    lifecycle_client: TestClient,
) -> None:
    """Ödenmiş dönemin ortasında kotayı kısmak, satın alınan hizmeti geri almaktır."""
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("dus"))
    _upgrade(lifecycle_client, token, "enterprise")

    body = _upgrade(lifecycle_client, token, "pro")
    assert body["activated"] is False
    assert body["effective_at"] is not None  # dönem sonuna yazıldı

    subscription = _subscription(lifecycle_client, token)
    assert subscription["plan"] == "enterprise"  # BU dönem hâlâ kurumsal
    assert subscription["pending_plan"] == "pro"
    assert subscription["pending_plan_name"] == "Pro"

    usage = lifecycle_client.get("/api/v1/usage", headers=_auth(token)).json()
    assert usage["documents"]["limit"] is None  # kota kısılmadı


def test_ucretsiz_plana_gecis_iptale_yonlenir(lifecycle_client: TestClient) -> None:
    """Ücretsiz plana düşmek tahsilatı tümden durdurur; bu bir iptaldir.

    İki ayrı yolun aynı sonucu farklı üretmesi, ikisinin zamanla ayrışması demek.
    """
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("free"))
    _upgrade(lifecycle_client, token, "pro")

    body = _upgrade(lifecycle_client, token, "free")
    assert body["effective_at"] is not None

    subscription = _subscription(lifecycle_client, token)
    assert subscription["cancel_at_period_end"] is True
    assert subscription["plan"] == "pro"  # erişim dönem sonuna kadar sürüyor


def test_bekleyen_iptalde_plan_degisimi_reddedilir(lifecycle_client: TestClient) -> None:
    """İki niyet çakışıyor; plan seçimini örtük "iptali geri al" saymak
    kullanıcının beklemediği bir tahsilat üretirdi."""
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("cak"))
    _upgrade(lifecycle_client, token, "pro")
    lifecycle_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))

    response = lifecycle_client.post(
        "/api/v1/billing/checkout", json={"plan": "enterprise"}, headers=_auth(token)
    )
    assert response.status_code == 409, response.text


def test_ayni_plana_gecis_cakisma_dondurur(lifecycle_client: TestClient) -> None:
    _tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("ayni"))
    _upgrade(lifecycle_client, token, "pro")

    response = lifecycle_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token)
    )
    assert response.status_code == 409, response.text


# ── Yetkilendirme ve kiracı sınırı ───────────────────────────────────────────


def test_uye_iptal_edemez_ama_gorebilir(
    lifecycle_client: TestClient, app_database_url: str
) -> None:
    """Görüntüleme herkese açık, değiştirme yalnız kiracı yöneticisine."""
    tenant, _admin_user, admin_token = _register_and_login(lifecycle_client, slug=_slug("rol"))
    _upgrade(lifecycle_client, admin_token, "pro")

    member_slug = _slug("uye")
    _member_tenant, member_user, _member_token = _register_and_login(
        lifecycle_client, slug=member_slug
    )
    # Aynı kullanıcıyı ilk kiracıya ÜYE olarak ekle (Membership RLS'siz).
    engine = create_sync_engine(app_database_url)
    try:
        with Session(engine) as session, session.begin():
            session.add(
                Membership(
                    user_id=uuid.UUID(member_user),
                    organization_id=uuid.UUID(tenant),
                    role=Role.MEMBER,
                )
            )
    finally:
        engine.dispose()

    login = lifecycle_client.post(
        "/api/v1/auth/login",
        json={"email": f"{member_slug}@org.com", "password": "sifre-12345"},
    )
    member_token = login.json()["access_token"]
    switch = lifecycle_client.post(
        "/api/v1/auth/switch-org",
        json={"organization_id": tenant},
        headers=_auth(member_token),
    )
    assert switch.status_code == 200, switch.text
    member_token = switch.json()["access_token"]

    # Görebilir…
    view = lifecycle_client.get("/api/v1/billing/subscription", headers=_auth(member_token))
    assert view.status_code == 200
    assert view.json()["plan"] == "pro"

    # …ama iptal edemez.
    cancel = lifecycle_client.post(
        "/api/v1/billing/subscription/cancel", headers=_auth(member_token)
    )
    assert cancel.status_code == 403, cancel.text


def test_iptal_yalnizca_kendi_kiracisini_etkiler(lifecycle_client: TestClient) -> None:
    """Kiracı sızıntısı: A'nın iptali B'nin aboneliğine DOKUNMAZ.

    Uçlar gövdeden/yoldan abonelik kimliği almadığı için "başka kiracının
    aboneliğini iptal et" isteği ifade bile edilemez; bu test o yapısal sınırın
    gerçekten tuttuğunu — ve bir gün parametre eklenirse kırılacağını — sabitler.
    """
    _tenant_a, _user_a, token_a = _register_and_login(lifecycle_client, slug=_slug("kir-a"))
    _tenant_b, _user_b, token_b = _register_and_login(lifecycle_client, slug=_slug("kir-b"))
    _upgrade(lifecycle_client, token_a, "pro")
    _upgrade(lifecycle_client, token_b, "pro")

    assert (
        lifecycle_client.post(
            "/api/v1/billing/subscription/cancel", headers=_auth(token_a)
        ).status_code
        == 200
    )

    a = _subscription(lifecycle_client, token_a)
    b = _subscription(lifecycle_client, token_b)
    assert a["cancel_at_period_end"] is True
    assert b["cancel_at_period_end"] is False
    assert b["next_charge_at"] is not None  # B'nin yenilemesi duruyor


def test_kimliksiz_istek_reddedilir(lifecycle_client: TestClient) -> None:
    assert lifecycle_client.post("/api/v1/billing/subscription/cancel").status_code == 401
    assert lifecycle_client.get("/api/v1/billing/subscription").status_code == 401


# ── Dönem sonu: değişiklikler GERÇEKTEN uygulanıyor mu ───────────────────────
#
# Zamanlanmış görev olmadan iptal hiçbir şey yapmaz: kiracı ücretsiz plana hiç
# düşmez ve ödemediği kotayı kullanmaya devam eder.


async def _read_subscription(tenant_id: uuid.UUID) -> dict[str, object]:
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            subscription = await quota.get_or_create_subscription(session, tenant_id)
            return {
                "plan": subscription.plan,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "pending_plan": subscription.pending_plan,
                "current_period_end": subscription.current_period_end,
            }
    finally:
        await engine.dispose()


async def _apply_due(tenant_id: uuid.UUID, now: datetime) -> billing_service.DueChangesReport:
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            return await billing_service.apply_due_subscription_changes(
                session, tenant_ids=[tenant_id], now=now
            )
    finally:
        await engine.dispose()


async def test_donem_sonu_gelmeden_hicbir_sey_uygulanmaz(lifecycle_client: TestClient) -> None:
    tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("erken"))
    _upgrade(lifecycle_client, token, "pro")
    lifecycle_client.post("/api/v1/billing/subscription/cancel", headers=_auth(token))

    report = await _apply_due(uuid.UUID(tenant), datetime.now(UTC))

    assert report.applied == 0
    state = await _read_subscription(uuid.UUID(tenant))
    assert state["plan"] is PlanTier.PRO  # erişim sürüyor


async def test_donem_sonunda_iptal_erisimi_keser(lifecycle_client: TestClient) -> None:
    tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("son"))
    _upgrade(lifecycle_client, token, "pro")
    cancel = lifecycle_client.post(
        "/api/v1/billing/subscription/cancel", headers=_auth(token)
    ).json()
    period_end = datetime.fromisoformat(str(cancel["current_period_end"]))

    report = await _apply_due(uuid.UUID(tenant), period_end + timedelta(seconds=1))

    assert report.ended == 1
    state = await _read_subscription(uuid.UUID(tenant))
    assert state["plan"] is PlanTier.FREE
    assert state["status"] is SubscriptionStatus.CANCELED
    assert state["cancel_at_period_end"] is False
    assert state["current_period_end"] is None

    # Kota da düştü.
    usage = lifecycle_client.get("/api/v1/usage", headers=_auth(token)).json()
    assert usage["plan"] == "free"
    assert usage["documents"]["limit"] == PLANS[PlanTier.FREE].documents_per_month


async def test_donem_sonunda_dusurme_uygulanir(lifecycle_client: TestClient) -> None:
    tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("dsson"))
    _upgrade(lifecycle_client, token, "enterprise")
    change = lifecycle_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token)
    ).json()
    effective_at = datetime.fromisoformat(str(change["effective_at"]))

    report = await _apply_due(uuid.UUID(tenant), effective_at + timedelta(seconds=1))

    assert report.downgraded == 1
    state = await _read_subscription(uuid.UUID(tenant))
    assert state["plan"] is PlanTier.PRO
    assert state["pending_plan"] is None
    assert state["status"] is SubscriptionStatus.ACTIVE  # düşürme iptal değildir


async def test_donem_sonu_gorevi_idempotenttir(lifecycle_client: TestClient) -> None:
    """İkinci koşu bir şey daha uygulamamalı; aksi hâlde saatlik görev her
    koşuda aynı düşürmeyi yeniden "vakti gelmiş" sayardı."""
    tenant, _user, token = _register_and_login(lifecycle_client, slug=_slug("idem"))
    _upgrade(lifecycle_client, token, "enterprise")
    change = lifecycle_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token)
    ).json()
    after = datetime.fromisoformat(str(change["effective_at"])) + timedelta(seconds=1)

    assert (await _apply_due(uuid.UUID(tenant), after)).applied == 1
    assert (await _apply_due(uuid.UUID(tenant), after)).applied == 0


# ── Sağlayıcıya ne gidiyor (fake sağlayıcı, servis seviyesi) ─────────────────


async def _seed_provider_subscription(tenant_id: uuid.UUID, plan: PlanTier, reference: str) -> None:
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            await billing_service.apply_plan_change(
                session,
                tenant_id=tenant_id,
                plan=plan,
                status=SubscriptionStatus.ACTIVE,
                provider="fake",
                provider_subscription_id=reference,
            )
    finally:
        await engine.dispose()


async def test_iptal_saglayicidaki_tahsilati_durdurur(lifecycle_client: TestClient) -> None:
    """İptal eden müşteriden bir kez daha para çekmek, erken durdurmanın
    maliyetiyle kıyaslanamaz — bu yüzden sağlayıcı çağrısı ANINDA yapılır."""
    tenant, _user, _token = _register_and_login(lifecycle_client, slug=_slug("sag-ipt"))
    tenant_id = uuid.UUID(tenant)
    await _seed_provider_subscription(tenant_id, PlanTier.PRO, "sub-ipt")
    provider = FakeBillingProvider()

    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            await billing_service.schedule_cancellation(session, provider, tenant_id=tenant_id)
    finally:
        await engine.dispose()

    calls = provider.calls_for("cancel_subscription")
    assert len(calls) == 1
    assert calls[0].arguments["subscription_id"] == "sub-ipt"


async def test_yukseltme_ve_dusurme_saglayiciya_dogru_zamanlamayi_gonderir(
    lifecycle_client: TestClient,
) -> None:
    """`immediate` bayrağı `/sartlar` §3'ün sağlayıcıya giden hâlidir."""
    tenant, _user, _token = _register_and_login(lifecycle_client, slug=_slug("sag-plan"))
    tenant_id = uuid.UUID(tenant)
    await _seed_provider_subscription(tenant_id, PlanTier.PRO, "sub-plan")
    provider = FakeBillingProvider()

    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            await billing_service.request_plan_change(
                session, provider, tenant_id=tenant_id, target_tier=PlanTier.ENTERPRISE
            )
            await billing_service.request_plan_change(
                session, provider, tenant_id=tenant_id, target_tier=PlanTier.PRO
            )
    finally:
        await engine.dispose()

    calls = provider.calls_for("change_plan")
    assert len(calls) == 2
    assert calls[0].arguments["target_tier"] is PlanTier.ENTERPRISE
    assert calls[0].arguments["immediate"] is True  # yükseltme: anında
    assert calls[1].arguments["target_tier"] is PlanTier.PRO
    assert calls[1].arguments["immediate"] is False  # düşürme: dönem sonunda


async def test_bekleyen_iptal_mutabakatla_geri_alinmaz(lifecycle_client: TestClient) -> None:
    """Mutabakat, müşterinin iptal kararını EZMEMELİ.

    İptal penceresinde sağlayıcı "canceled" derken biz erişimi sürdürüyoruz.
    Bu bilerek yapılan ayrışma bir sapma sayılsaydı, mutabakat aboneliği
    "onarır" ve bir sonraki dönem tahsil edilirdi.
    """
    tenant, _user, _token = _register_and_login(lifecycle_client, slug=_slug("mut-ipt"))
    tenant_id = uuid.UUID(tenant)
    await _seed_provider_subscription(tenant_id, PlanTier.PRO, "sub-mut")
    provider = FakeBillingProvider()

    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            await billing_service.schedule_cancellation(session, provider, tenant_id=tenant_id)
        async with factory() as session, session.begin():
            report = await billing_service.reconcile_subscriptions(
                session, provider, tenant_ids=[tenant_id]
            )
    finally:
        await engine.dispose()

    assert report.drift == 0  # gürültü de yok, "onarım" da
    state = await _read_subscription(tenant_id)
    assert state["cancel_at_period_end"] is True
    assert state["plan"] is PlanTier.PRO
