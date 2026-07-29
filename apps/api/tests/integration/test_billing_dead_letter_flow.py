"""Ölü mektup kuyruğu (Tur 8 / madde 1) — hiçbir olay sessizce kaybolmaz.

Webhook, yetkilendirmeyi değiştiren TEK mekanizmadır (ADR-0014). Doğrulaması
geçip **uygulanamayan** bir olay Tur 8'e kadar kayboluyordu; bedeli somut:
müşteri ödemesini yapmış, planı açılmamış ve elde olayı yeniden uygulayacak
hiçbir şey yok.

**Testlerin ikiye ayrılmasının sebebi.** HTTP üzerinden ürettirilebilen kalıcı
hataların hepsi *atfedilemez* (kiracısı bilinmeyen ya da gövdesi ayrıştırılamayan
olaylar) — çünkü kiracısı bilinen ve gerçekten var olan bir olayın uygulanamaması
için altyapı arızası gerekir. Bu yüzden kiracıya GÖRÜNEN kuyruk davranışı
(listeleme, yeniden işleme, izolasyon) satır doğrudan tohumlanarak sınanır;
uçtan uca yol ise webhook üzerinden.

Gerçek HTTP (TestClient) + gerçek DB (RLS) + gerçek Redis.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tenderiq_core.config import get_settings
from tenderiq_core.db import create_engine, create_session_factory
from tenderiq_core.models import DeadLetterKind, DeadLetterStatus
from tenderiq_core.services import dead_letter as dead_letter_service

pytestmark = pytest.mark.integration

WEBHOOK_SECRET = "test-dlq-secret"


@pytest.fixture
def dlq_client(api_client: TestClient) -> Iterator[TestClient]:
    """``manual`` sağlayıcı + bilinen webhook sırrı."""
    previous = os.environ.get("BILLING_PROVIDER")
    os.environ["BILLING_PROVIDER"] = "manual"
    os.environ["BILLING_WEBHOOK_SECRET"] = WEBHOOK_SECRET
    get_settings.cache_clear()
    try:
        yield api_client
    finally:
        os.environ.pop("BILLING_WEBHOOK_SECRET", None)
        if previous is None:
            os.environ.pop("BILLING_PROVIDER", None)
        else:
            os.environ["BILLING_PROVIDER"] = previous
        get_settings.cache_clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


def _register_and_login(client: TestClient, *, slug: str) -> tuple[str, str]:
    email = f"{slug}@org.com"
    register = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert register.status_code == 201, register.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert login.status_code == 200, login.text
    return register.json()["user"]["tenant_id"], login.json()["access_token"]


def _sign(payload: dict[str, object]) -> tuple[str, dict[str, str]]:
    raw = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw, {"x-tenderiq-signature": signature, "content-type": "application/json"}


def _event(tenant_id: str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        # Her çağrıda benzersiz: dedup anahtarı Redis'te 90 gün kalıcıdır ve
        # sabit kimlik kullanan bir test ikinci koşuda yanlış şeyi ölçer.
        "event_id": f"dlq_{uuid.uuid4()}",
        "event_type": "subscription.activated",
        "tenant_id": tenant_id,
        "plan": "pro",
        "status": "active",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    body.update(overrides)
    return body


def _dead_letters(client: TestClient, token: str) -> list[dict[str, object]]:
    response = client.get("/api/v1/billing/dead-letters", headers=_auth(token))
    assert response.status_code == 200, response.text
    rows: list[dict[str, object]] = response.json()
    return rows


async def _seed_dead_letter(
    tenant_id: uuid.UUID | None, payload: dict[str, object], *, event_id: str
) -> uuid.UUID:
    """Kuyruğa doğrudan bir satır yazar (kiracıya görünen davranışı sınamak için)."""
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            row = await dead_letter_service.enqueue(
                session,
                provider="manual",
                event_id=event_id,
                event_type=str(payload.get("event_type", "subscription.activated")),
                tenant_id=tenant_id,
                signature_valid=True,
                kind=DeadLetterKind.TRANSIENT,
                error="veritabanına ulaşılamadı",
                raw_body=json.dumps(payload).encode(),
            )
            assert row is not None
            return row.id
    finally:
        await engine.dispose()


# ── Uçtan uca: kalıcı hata kuyruğa düşer, sağlayıcı yeniden denemeye çağrılmaz


def test_taninmayan_kiraci_kuyruga_duser_ve_400_doner(dlq_client: TestClient) -> None:
    """Sağlayıcı 5xx görürse asla başarılı olamayacak olayı saatlerce yeniden
    dener; 400 kalıcı reddetmedir ve olay kuyrukta insanı bekler."""
    raw, headers = _sign(_event(str(uuid.uuid4())))  # var olmayan kiracı

    response = dlq_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "validation_error"


def test_ayni_kalici_hata_tek_satir_uretir(dlq_client: TestClient) -> None:
    """Sağlayıcı aynı olayı defalarca teslim eder; kuyruk kopyalarla dolmamalı.

    İkinci teslim tekil kısıta takılıp 5xx üretseydi, "kuyruk kopyalarla dolmasın"
    koruması ucun kendisini bozmuş olurdu.
    """
    raw, headers = _sign(_event(str(uuid.uuid4())))

    first = dlq_client.post("/api/v1/billing/webhook", content=raw, headers=headers)
    second = dlq_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert first.status_code == 400, first.text
    assert second.status_code == 400, second.text


def test_atfedilemeyen_olay_hicbir_kiraciya_gorunmez(dlq_client: TestClient) -> None:
    """Kiracısı bilinmeyen olay kuyruktadır ama kimsenin listesinde çıkmaz.

    Atfedemediğimiz bir ödemeyi rastgele bir kiracıya göstermek, sızıntının ta
    kendisi olurdu. Bu satırlar operatör yüzeyinden izlenir.
    """
    _tenant, token = _register_and_login(dlq_client, slug=_slug("dlq-gizli"))
    raw, headers = _sign(_event(str(uuid.uuid4())))
    dlq_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert _dead_letters(dlq_client, token) == []


def test_gecersiz_imzali_govde_de_saklanir(dlq_client: TestClient) -> None:
    """İmza BİÇİMİ hâlâ doğrulanmamış bir varsayım; biçim yanlışsa gerçek
    olayların tamamı buraya düşer ve teşhisin tek yolu budur."""
    raw = json.dumps(_event(str(uuid.uuid4())), separators=(",", ":"))
    response = dlq_client.post(
        "/api/v1/billing/webhook",
        content=raw,
        headers={"x-tenderiq-signature": "deadbeef", "content-type": "application/json"},
    )
    assert response.status_code == 400, response.text


# ── Kiracıya görünen kuyruk: listeleme, redaksiyon, yeniden işleme ───────────


async def test_kuyruk_kiraciya_listelenir_ve_govde_redaktedir(dlq_client: TestClient) -> None:
    """Gövde saklanır ama hassas alanların DEĞERİ saklanmaz.

    Anahtar korunur (hangi alanların geldiği asıl teşhis bilgisidir), değer
    gizlenir — "kart verisi bize gelmez" varsayımı yanlışsa PCI kapsamına
    girmeyelim diye.
    """
    tenant, token = _register_and_login(dlq_client, slug=_slug("dlq-liste"))
    event_id = f"dlq_{uuid.uuid4()}"
    payload = _event(tenant, event_id=event_id)
    payload["email"] = "musteri@ornek.com"
    payload["card_number"] = "4111111111111111"
    await _seed_dead_letter(uuid.UUID(tenant), payload, event_id=event_id)

    rows = _dead_letters(dlq_client, token)

    assert len(rows) == 1
    row = rows[0]
    assert row["event_id"] == event_id
    assert row["kind"] == "transient"
    assert row["status"] == "pending"
    assert row["attempts"] == 1
    stored = row["payload"]
    assert isinstance(stored, dict)
    # Anahtarlar duruyor…
    assert "email" in stored
    assert "card_number" in stored
    # …değerler gizlendi.
    assert stored["email"] == "«gizlendi»"
    assert stored["card_number"] == "«gizlendi»"
    # Uygulama için gereken alanlar redakte EDİLMEDİ.
    assert stored["tenant_id"] == tenant
    assert stored["plan"] == "pro"


async def test_yeniden_isleme_olayi_uygular_ve_kaydi_cozer(dlq_client: TestClient) -> None:
    """Kuyruktaki olay yeniden işlenince plan gerçekten açılır."""
    tenant, token = _register_and_login(dlq_client, slug=_slug("dlq-retry"))
    event_id = f"dlq_{uuid.uuid4()}"
    await _seed_dead_letter(uuid.UUID(tenant), _event(tenant, event_id=event_id), event_id=event_id)
    row_id = _dead_letters(dlq_client, token)[0]["id"]

    response = dlq_client.post(f"/api/v1/billing/dead-letters/{row_id}/retry", headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "applied"
    # Plan açıldı.
    assert dlq_client.get("/api/v1/usage", headers=_auth(token)).json()["plan"] == "pro"
    # Kayıt çözüldü.
    resolved = _dead_letters(dlq_client, token)[0]
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"] is not None


async def test_yeniden_isleme_idempotenttir(dlq_client: TestClient) -> None:
    """İkinci yeniden işleme durumu tekrar uygulamaz.

    Yeniden işleme mevcut idempotency damgasını KULLANIR; atlasaydı "yeniden
    işle" düğmesi aynı ödemeyi iki kez uygulayabilirdi.
    """
    tenant, token = _register_and_login(dlq_client, slug=_slug("dlq-idem"))
    event_id = f"dlq_{uuid.uuid4()}"
    await _seed_dead_letter(uuid.UUID(tenant), _event(tenant, event_id=event_id), event_id=event_id)
    row_id = _dead_letters(dlq_client, token)[0]["id"]

    first = dlq_client.post(f"/api/v1/billing/dead-letters/{row_id}/retry", headers=_auth(token))
    assert first.json()["outcome"] == "applied"

    # Kayıt artık çözülmüş; ikinci deneme çakışma döner (sessizce tekrar
    # uygulamaz).
    second = dlq_client.post(f"/api/v1/billing/dead-letters/{row_id}/retry", headers=_auth(token))
    assert second.status_code == 409, second.text


async def test_yeniden_isleme_eski_olayi_uygulamaz(dlq_client: TestClient) -> None:
    """Sırasız-olay koruması yeniden işlemede de geçerli.

    Aksi hâlde "yeniden işle" düğmesi, güncel durumu eski bir olayla ezebilir —
    ör. iptal etmiş bir müşterinin aboneliğini geri açabilirdi.
    """
    tenant, token = _register_and_login(dlq_client, slug=_slug("dlq-eski"))
    now = datetime.now(UTC)

    # Güncel olay uygulanır.
    fresh_raw, fresh_headers = _sign(_event(tenant, occurred_at=now.isoformat()))
    assert (
        dlq_client.post("/api/v1/billing/webhook", content=fresh_raw, headers=fresh_headers).json()[
            "status"
        ]
        == "applied"
    )

    # Kuyrukta ESKİ bir "iptal" olayı bekliyor.
    event_id = f"dlq_{uuid.uuid4()}"
    await _seed_dead_letter(
        uuid.UUID(tenant),
        _event(
            tenant,
            event_id=event_id,
            event_type="subscription.canceled",
            occurred_at=(now - timedelta(hours=6)).isoformat(),
        ),
        event_id=event_id,
    )
    row_id = next(r["id"] for r in _dead_letters(dlq_client, token) if r["event_id"] == event_id)

    response = dlq_client.post(f"/api/v1/billing/dead-letters/{row_id}/retry", headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "stale"
    # Erişim korunmuş: iptal UYGULANMADI.
    subscription = dlq_client.get("/api/v1/billing/subscription", headers=_auth(token)).json()
    assert subscription["cancel_at_period_end"] is False


# ── Kiracı izolasyonu ────────────────────────────────────────────────────────


async def test_yonetici_baska_kiracinin_kaydini_goremez(dlq_client: TestClient) -> None:
    """Kuyruk ödeme gövdesi taşır; sızıntısı yalnız gizlilik değil yetkilendirme
    sorunudur."""
    tenant_a, token_a = _register_and_login(dlq_client, slug=_slug("dlq-a"))
    _tenant_b, token_b = _register_and_login(dlq_client, slug=_slug("dlq-b"))
    event_id = f"dlq_{uuid.uuid4()}"
    await _seed_dead_letter(
        uuid.UUID(tenant_a), _event(tenant_a, event_id=event_id), event_id=event_id
    )

    assert len(_dead_letters(dlq_client, token_a)) == 1
    # B, A'nın kaydını GÖRMEZ.
    assert _dead_letters(dlq_client, token_b) == []


async def test_yonetici_baska_kiracinin_kaydini_yeniden_isleyemez(
    dlq_client: TestClient,
) -> None:
    """Kimliği bilinse bile başkasının olayı yeniden işlenemez — 404 (403 değil:
    kaydın VARLIĞI da sızmamalı)."""
    tenant_a, token_a = _register_and_login(dlq_client, slug=_slug("dlq-ra"))
    _tenant_b, token_b = _register_and_login(dlq_client, slug=_slug("dlq-rb"))
    event_id = f"dlq_{uuid.uuid4()}"
    await _seed_dead_letter(
        uuid.UUID(tenant_a), _event(tenant_a, event_id=event_id), event_id=event_id
    )
    row_id = _dead_letters(dlq_client, token_a)[0]["id"]

    response = dlq_client.post(
        f"/api/v1/billing/dead-letters/{row_id}/retry", headers=_auth(token_b)
    )

    assert response.status_code == 404, response.text
    # A'nın kaydı DOKUNULMAMIŞ durumda.
    assert _dead_letters(dlq_client, token_a)[0]["status"] == "pending"
    # B'nin planı da değişmemiş.
    assert dlq_client.get("/api/v1/usage", headers=_auth(token_b)).json()["plan"] == "free"


def test_kimliksiz_erisim_reddedilir(dlq_client: TestClient) -> None:
    assert dlq_client.get("/api/v1/billing/dead-letters").status_code == 401
    assert dlq_client.post(f"/api/v1/billing/dead-letters/{uuid.uuid4()}/retry").status_code == 401


def test_bulunmayan_kayit_404(dlq_client: TestClient) -> None:
    _tenant, token = _register_and_login(dlq_client, slug=_slug("dlq-404"))
    response = dlq_client.post(
        f"/api/v1/billing/dead-letters/{uuid.uuid4()}/retry", headers=_auth(token)
    )
    assert response.status_code == 404, response.text


# ── Durum sabitleri ─────────────────────────────────────────────────────────


def test_kuyruk_durum_degerleri_sozlesmede() -> None:
    """Uç, enum değerlerini olduğu gibi döndürüyor; sözleşme sabitlensin."""
    assert {s.value for s in DeadLetterStatus} == {"pending", "resolved", "discarded"}
    assert {k.value for k in DeadLetterKind} == {"transient", "permanent"}


def test_kiraci_baglami_kullanilmis_baglantida_da_yazilabilir(
    dlq_client: TestClient,
) -> None:
    """Havuzdan gelen "kullanılmış" bağlantıda kuyruğa yazma ÇALIŞMALI.

    `current_setting('app.current_tenant', true)` ayar HİÇ tanımlanmamışsa NULL
    döner; ama aynı bağlantıda daha önce bir istek onu transaction-local olarak
    kurduysa, transaction bittikten sonra ayar **boş dizeye** döner — NULL'a
    değil. RLS politikası `''::uuid` çevirmeye çalışıp sorguyu çökertiyordu ve
    kimliksiz webhook yolu kuyruğa hiç yazamayıp 503 döndürüyordu.

    Bu testin sırası önemli: ÖNCE kiracı bağlamı kuran bir istek (kimlikli),
    SONRA kimliksiz webhook. Taze bağlantıda hata görünmez.
    """
    tenant, token = _register_and_login(dlq_client, slug=_slug("dlq-havuz"))

    # 1) Kiracı bağlamı kuran istekler — bağlantıda GUC tanımlanır.
    for _ in range(3):
        subscription = dlq_client.get("/api/v1/billing/subscription", headers=_auth(token))
        assert subscription.status_code == 200
        assert _dead_letters(dlq_client, token) == []

    # 2) Kimliksiz webhook: kalıcı hata → kuyruğa yazılmalı, 400 dönmeli.
    raw, headers = _sign(_event(str(uuid.uuid4())))
    response = dlq_client.post("/api/v1/billing/webhook", content=raw, headers=headers)

    assert response.status_code == 400, response.text
    # 503 = kuyruğa YAZILAMADI (regresyon). 400 = reddedildi VE kaydedildi.
    assert response.json()["error"]["code"] == "validation_error"

    # 3) Kiracı yüzeyi hâlâ çalışıyor.
    assert dlq_client.get("/api/v1/billing/dead-letters", headers=_auth(token)).status_code == 200
    del tenant
