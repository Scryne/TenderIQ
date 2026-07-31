"""Sprint 3.3-B uçtan uca: planlar + checkout (test modu) + webhook (imza + idempotency).

Gerçek HTTP (TestClient) + gerçek DB (testcontainers) + RLS + gerçek Redis (idempotency).
Manual (test-modu) sağlayıcı: checkout planı anında etkinleştirir → /usage yeni limitleri
yansıtır; webhook HMAC imzayla doğrulanır ve tekrarlanan olay durumu bir kez uygular.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tenderiq_core.billing.plans import PLANS, PlanTier

pytestmark = pytest.mark.integration

WEBHOOK_SECRET = "test-webhook-secret"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient, *, slug: str, email: str) -> tuple[str, str]:
    register = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert register.status_code == 201, register.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert login.status_code == 200
    return register.json()["user"]["tenant_id"], login.json()["access_token"]


@pytest.fixture
def billing_client(api_client: TestClient) -> Iterator[TestClient]:
    """api_client + webhook sırrı + **manual sağlayıcı** (per-request SettingsDep okur).

    ``BILLING_PROVIDER`` açıkça sabitlenir: ``Settings`` ``.env`` dosyasını da okur,
    dolayısıyla geliştirici makinesinde gerçek bir sağlayıcı (ör. iyzico)
    seçiliyse bu testler onun yapılandırmasına düşer ve sınamak istedikleri
    test-modu semantiğini hiç görmezler. Testler geliştiricinin yerel
    ayarlarından bağımsız olmalıdır.
    """
    from tenderiq_core.config import get_settings

    previous_provider = os.environ.get("BILLING_PROVIDER")
    os.environ["BILLING_WEBHOOK_SECRET"] = WEBHOOK_SECRET
    os.environ["BILLING_PROVIDER"] = "manual"
    get_settings.cache_clear()
    try:
        yield api_client
    finally:
        os.environ.pop("BILLING_WEBHOOK_SECRET", None)
        if previous_provider is None:
            os.environ.pop("BILLING_PROVIDER", None)
        else:
            os.environ["BILLING_PROVIDER"] = previous_provider
        get_settings.cache_clear()


def _sign(payload: dict[str, object]) -> tuple[str, dict[str, str]]:
    raw = json.dumps(payload)
    sig = hmac.new(WEBHOOK_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw, {"x-tenderiq-signature": sig, "content-type": "application/json"}


def test_planlar_listelenir_free_gecerli(billing_client: TestClient) -> None:
    _tenant, token = _register_and_login(billing_client, slug="bil-1", email="b1@org.com")
    resp = billing_client.get("/api/v1/billing/plans", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    plans = {p["tier"]: p for p in resp.json()}
    assert set(plans) == {"free", "pro", "enterprise"}
    assert plans["free"]["is_current"] is True
    assert plans["pro"]["is_current"] is False
    assert plans["pro"]["monthly_price_try"] == 1500


def test_checkout_test_modu_plani_aninda_yukseltir(billing_client: TestClient) -> None:
    _tenant, token = _register_and_login(billing_client, slug="bil-2", email="b2@org.com")

    # Yükseltmeden önce FREE limitleri.
    before = billing_client.get("/api/v1/usage", headers=_auth(token)).json()
    assert before["plan"] == "free"
    assert before["documents"]["limit"] == PLANS[PlanTier.FREE].documents_per_month

    checkout = billing_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token)
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["activated"] is True
    assert body["checkout_url"] is None
    assert body["plan"] == "pro"

    # /usage artık PRO limitlerini yansıtır.
    after = billing_client.get("/api/v1/usage", headers=_auth(token)).json()
    assert after["plan"] == "pro"
    assert after["documents"]["limit"] == PLANS[PlanTier.PRO].documents_per_month
    assert after["pages"]["limit"] == PLANS[PlanTier.PRO].pages_per_month


def test_webhook_imza_dogrular_ve_idempotent(billing_client: TestClient) -> None:
    tenant_id, token = _register_and_login(billing_client, slug="bil-4", email="b4@org.com")
    event_id = f"evt_{uuid.uuid4()}"  # her koşuda benzersiz (Redis dedup anahtarı kalıcı)

    raw, headers = _sign(
        {
            "event_id": event_id,
            "event_type": "subscription.activated",
            "tenant_id": tenant_id,
            "plan": "pro",
            "status": "active",
        }
    )

    # İlk teslim: uygulanır.
    first = billing_client.post("/api/v1/billing/webhook", content=raw, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "applied"
    assert billing_client.get("/api/v1/usage", headers=_auth(token)).json()["plan"] == "pro"

    # Tekrar teslim (aynı olay): idempotent — durum bir kez uygulanır.
    second = billing_client.post("/api/v1/billing/webhook", content=raw, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "duplicate"
    assert billing_client.get("/api/v1/usage", headers=_auth(token)).json()["plan"] == "pro"


def test_webhook_gecersiz_imza_reddedilir(billing_client: TestClient) -> None:
    tenant_id, _token = _register_and_login(billing_client, slug="bil-5", email="b5@org.com")
    raw = json.dumps(
        {
            "event_id": f"evt_{uuid.uuid4()}",
            "event_type": "subscription.activated",
            "tenant_id": tenant_id,
            "plan": "pro",
        }
    )
    resp = billing_client.post(
        "/api/v1/billing/webhook",
        content=raw,
        headers={"x-tenderiq-signature": "deadbeef", "content-type": "application/json"},
    )
    assert resp.status_code == 400, resp.text


def test_webhook_bilinmeyen_kiracida_500_donmez(billing_client: TestClient) -> None:
    """İmzalı ama tanınmayan bir kiracı KALICI olarak reddedilmeli, çökmemeli.

    `scripts/replay_billing_webhook.py` bunu canlı uçta yakaladı: abonelik
    INSERT'i yabancı anahtar kısıtına takılıyor, ``get_or_create_subscription``
    bunu eşzamanlılık yarışı sanıp yeniden okuyor, bulamayınca ``assert``
    patlıyordu → HTTP 500. Sağlayıcı 500'ü GEÇİCİ hata sayar ve asla başarılı
    olamayacak bir olayı saatlerce yeniden dener.
    """
    raw, headers = _sign(
        {
            "event_id": f"evt_{uuid.uuid4()}",
            "event_type": "subscription.activated",
            "tenant_id": str(uuid.uuid4()),  # hiç var olmayan kiracı
            "plan": "pro",
            "status": "active",
        }
    )
    resp = billing_client.post("/api/v1/billing/webhook", content=raw, headers=headers)
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "validation_error"


# ── Kiracı izolasyonu (Tur 3 / A6) ───────────────────────────────────────────
# Ödeme ve kota tabloları paranın ve hakkın kaydıdır: buradaki bir sızıntı
# yalnız gizlilik değil, YETKİLENDİRME sorunudur (başkasının planını görmek ya
# da değiştirmek). RLS bunu zaten kapatıyor; testler o kapının açık kaldığını
# bir sonraki değişiklikte fark etsin diye var.


def test_abonelik_baska_kiraciya_sizmaz(billing_client: TestClient) -> None:
    """A'nın planı yükseldiğinde B hâlâ kendi (ücretsiz) planını görmeli."""
    _, token_a = _register_and_login(billing_client, slug="bill-iz-a", email="iz-a@org.com")
    _, token_b = _register_and_login(billing_client, slug="bill-iz-b", email="iz-b@org.com")

    upgrade = billing_client.post(
        "/api/v1/billing/checkout", json={"plan": "pro"}, headers=_auth(token_a)
    )
    assert upgrade.status_code == 200, upgrade.text

    usage_a = billing_client.get("/api/v1/usage", headers=_auth(token_a))
    usage_b = billing_client.get("/api/v1/usage", headers=_auth(token_b))

    assert usage_a.status_code == 200
    assert usage_b.status_code == 200
    assert usage_a.json()["plan"] == "pro"
    assert usage_b.json()["plan"] == "free"


def test_webhook_yalnizca_govdedeki_kiraciyi_etkiler(billing_client: TestClient) -> None:
    """Olay gövdesi İMZALIDIR; kiracı kimliği oradan gelir ve başkasına taşmaz."""
    tenant_a, token_a = _register_and_login(billing_client, slug="bill-wh-a", email="wh-a@org.com")
    _, token_b = _register_and_login(billing_client, slug="bill-wh-b", email="wh-b@org.com")

    raw, headers = _sign(
        {
            # Dedup anahtarı Redis'te KALICIDIR; sabit kimlik ikinci koşuda
            # olayı "mükerrer" yapar ve test sessizce yanlış şey ölçer.
            "event_id": f"evt-izolasyon-{uuid.uuid4()}",
            "event_type": "subscription.activated",
            "tenant_id": tenant_a,
            "plan": "pro",
            "status": "active",
        }
    )
    response = billing_client.post("/api/v1/billing/webhook", content=raw, headers=headers)
    assert response.status_code == 200, response.text

    assert billing_client.get("/api/v1/usage", headers=_auth(token_a)).json()["plan"] == "pro"
    assert billing_client.get("/api/v1/usage", headers=_auth(token_b)).json()["plan"] == "free"


def test_kullanim_kaydi_kiracilar_arasi_toplanmaz(billing_client: TestClient) -> None:
    """Kota sayacı kiracıya özeldir; B'nin tüketimi A'nın kotasını yemez."""
    _, token_a = _register_and_login(billing_client, slug="bill-kt-a", email="kt-a@org.com")
    _, token_b = _register_and_login(billing_client, slug="bill-kt-b", email="kt-b@org.com")

    for token in (token_a, token_b):
        created = billing_client.post(
            "/api/v1/tenders", json={"title": "Kota testi"}, headers=_auth(token)
        )
        assert created.status_code == 201

    usage_a = billing_client.get("/api/v1/usage", headers=_auth(token_a)).json()
    usage_b = billing_client.get("/api/v1/usage", headers=_auth(token_b)).json()

    assert usage_a["documents"]["used"] == usage_b["documents"]["used"] == 0


# ── Sırasız webhook teslimi (Tur 5 / madde 1) ────────────────────────────────


def _iso(offset_seconds: int) -> str:
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) + timedelta(seconds=offset_seconds)).isoformat()


def test_gec_gelen_eski_olay_yeni_durumu_ezmez(billing_client: TestClient) -> None:
    """Webhook'lar sıra garantisi vermez.

    Damga olmadan, geç gelen bir "iptal edildi" olayı sonradan gelmiş
    "yeniden etkinleşti"yi ezer ve müşterinin ÖDEDİĞİ erişimi kapatırdı —
    sessizce, ancak müşteri şikâyet edince fark edilecek biçimde.
    """
    tenant_id, token = _register_and_login(billing_client, slug="bill-sira", email="sira@org.com")

    # Yeni olay: pro'ya geçiş.
    raw_new, headers_new = _sign(
        {
            "event_id": f"evt-yeni-{uuid.uuid4()}",
            "event_type": "subscription.activated",
            "tenant_id": tenant_id,
            "plan": "pro",
            "status": "active",
            "occurred_at": _iso(0),
        }
    )
    assert (
        billing_client.post("/api/v1/billing/webhook", content=raw_new, headers=headers_new).json()[
            "status"
        ]
        == "applied"
    )

    # ESKİ olay sonradan geliyor (sağlayıcı yeniden denemesi).
    raw_old, headers_old = _sign(
        {
            "event_id": f"evt-eski-{uuid.uuid4()}",
            "event_type": "subscription.canceled",
            "tenant_id": tenant_id,
            "plan": "free",
            "status": "canceled",
            "occurred_at": _iso(-60),
        }
    )
    late = billing_client.post("/api/v1/billing/webhook", content=raw_old, headers=headers_old)

    assert late.json()["status"] == "stale"
    assert billing_client.get("/api/v1/usage", headers=_auth(token)).json()["plan"] == "pro"


def test_damgasiz_olay_yok_sayilmaz(billing_client: TestClient) -> None:
    """Koruma ancak KARŞILAŞTIRILABİLİR iki damga varken devreye girmeli.

    Aksi hâlde damga taşımayan sağlayıcı gövdeleri sessizce işlenmez olurdu.
    """
    tenant_id, token = _register_and_login(
        billing_client, slug="bill-damgasiz", email="damgasiz@org.com"
    )
    raw, headers = _sign(
        {
            "event_id": f"evt-damgasiz-{uuid.uuid4()}",
            "event_type": "subscription.activated",
            "tenant_id": tenant_id,
            "plan": "pro",
            "status": "active",
        }
    )

    response = billing_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert response.json()["status"] == "applied"
    assert billing_client.get("/api/v1/usage", headers=_auth(token)).json()["plan"] == "pro"
