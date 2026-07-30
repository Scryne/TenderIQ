"""ADR-0015: bastırma listesi kiracı-dışıdır — ama uçlardan GÖZLENEMEZ.

`email_suppression` bilinçli olarak global bir tablodur: teslim edilemezlik
adresin özelliğidir, kiracı ilişkisinin değil, ve korunan kaynak (gönderen alan
adının itibarı) tüm kiracılar için ortaktır. Bedeli şudur: tablo doğası gereği
kiracı sınırını aşan bilgi taşır.

**Bu dosya o bedeli sınırlayan kuralı kilitler:** bir kiracı, başka bir kiracının
gönderiminde bounce almış bir adresin teslim edilemez olduğunu uçlar üzerinden
öğrenemez.

Kural şu an DOĞRU ama kazara doğru: `create_invitation`, `send_email`in dönüş
değerini kullanmıyor. Biri `InvitationResponse`a teslim durumu eklediğinde ya da
davet ucunu bastırılmış adreste 4xx döndürecek şekilde "iyileştirdiğinde" sızıntı
sessizce açılır — hiçbir mevcut test bunu görmez. Buradaki testler görür.

Tek istisna `POST /auth/register`in `email_delivery` alanıdır: çağıran kendi
adresini kaydediyor, dolayısıyla kiracılar arası bir gözlem değil. O istisna da
burada AÇIKÇA doğrulanıyor — ADR'deki gerekçenin kodda karşılığı var mı diye.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tenderiq_core.email import EmailMessage, MemoryEmailProvider
from tenderiq_core.models import EmailSuppression, SuppressionReason

pytestmark = pytest.mark.integration

#: A kiracısının gönderiminde kalıcı bounce almış adres. B kiracısı bunu
#: öğrenememeli.
#:
#: Adres ADI bilinçli olarak "bounce"/"suppress" içermez: aşağıdaki testlerden
#: biri yanıt gövdesinde bu kelimeleri arıyor ve adresin kendisi yanıtta
#: göründüğü için isim eşleşmesi yanlış KIRMIZI üretirdi.
BOUNCED_EMAIL = "teslim-edilemez@dıs-alan.com"

#: Teslim durumunu ele verebilecek alan adları. Davet yanıtında hiçbiri olmamalı.
_DELIVERY_FIELDS = frozenset(
    {"email_delivery", "delivery", "suppressed", "email_status", "delivered", "bounced"}
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, *, slug: str, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["user"]["tenant_id"])


def _login(client: TestClient, *, email: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["access_token"])


@pytest.fixture
def captured_emails(api_client: TestClient) -> list[EmailMessage]:
    """Uygulamanın e-posta sağlayıcısını bellek sağlayıcısıyla değiştirir."""
    provider = MemoryEmailProvider()
    api_client.app.state.email_provider = provider
    return provider.sent


@pytest.fixture
def suppressed_address(app_database_url: str) -> str:
    """`BOUNCED_EMAIL`i bastırma listesine koyar (A kiracısının bounce'u gibi).

    Kayıt doğrudan ORM ile atılıyor: burada sınanan şey webhook'un yazma yolu
    değil (o `test_email_webhook_flow.py`de), bastırılmış bir adresin BAŞKA bir
    kiracıya görünüp görünmediği.
    """
    engine = create_engine(app_database_url)
    try:
        with Session(engine) as session, session.begin():
            session.add(
                EmailSuppression(
                    email=BOUNCED_EMAIL,
                    reason=SuppressionReason.HARD_BOUNCE,
                    detail="test kurulumu",
                )
            )
        yield BOUNCED_EMAIL
        with Session(engine) as session, session.begin():
            existing = session.scalar(
                select(EmailSuppression).where(EmailSuppression.email == BOUNCED_EMAIL)
            )
            if existing is not None:
                session.delete(existing)
    finally:
        engine.dispose()


def test_davet_yaniti_bastirmayi_ele_vermez(
    api_client: TestClient, captured_emails: list[EmailMessage], suppressed_address: str
) -> None:
    """B kiracısı bastırılmış bir adresi davet eder: yanıt normal 201, ipucu yok.

    Üç şey birden doğrulanıyor:
    1. Uç bastırılmış adreste FARKLI davranmıyor (4xx/409 dönmüyor) — durum kodu
       tek başına bir gözlem kanalıdır.
    2. Yanıt gövdesinde teslim durumu taşıyan hiçbir alan yok.
    3. Davet GERÇEKTEN oluşmuş (yani uç sessizce hiçbir şey yapmamış değil) —
       aksi hâlde test "sızıntı yok" derken asıl işlevin kırıldığını gizlerdi.
    """
    _register(api_client, slug="sup-b", email="admin@sup-b.com")
    admin_token = _login(api_client, email="admin@sup-b.com")

    resp = api_client.post(
        "/api/v1/invitations",
        json={"email": suppressed_address, "role": "member"},
        headers=_auth(admin_token),
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    leaked = _DELIVERY_FIELDS.intersection(body)
    assert not leaked, f"davet yanıtı teslim durumu sızdırıyor: {sorted(leaked)} · {body}"
    # Gövdenin hiçbir değerinde "suppress"/"bounce" geçmemeli (mesaj alanıyla
    # sızdırmak da sızdırmaktır).
    serialized = str(body).lower()
    for ipucu in ("suppress", "bounce", "bastır", "teslim edilemez"):
        assert ipucu not in serialized, f"yanıt '{ipucu}' kelimesini sızdırıyor: {body}"

    # Davet gerçekten kaydedildi mi?
    listed = api_client.get("/api/v1/invitations", headers=_auth(admin_token)).json()
    assert [item["email"] for item in listed] == [suppressed_address]

    # ...ve e-posta bilinçli olarak GÖNDERİLMEDİ (bastırma çalıştı).
    assert not [m for m in captured_emails if m.to == suppressed_address]


def test_bastirilmamis_adreste_davet_yaniti_ayni_bicimde(
    api_client: TestClient, captured_emails: list[EmailMessage], suppressed_address: str
) -> None:
    """Bastırılmış ve bastırılmamış adres AYNI yanıtı üretir.

    Sızıntı testinin asıl kanıtı budur: tek bir yanıta bakıp "ipucu yok" demek
    yetmez, iki durumun **ayırt edilemez** olduğu gösterilmeli. Aksi hâlde
    alan adları değişmeden de (ör. farklı `status`) kanal açık kalabilir.
    """
    _register(api_client, slug="sup-c", email="admin@sup-c.com")
    admin_token = _login(api_client, email="admin@sup-c.com")

    temiz = "temiz-adres@dıs-alan.com"
    resp_temiz = api_client.post(
        "/api/v1/invitations",
        json={"email": temiz, "role": "member"},
        headers=_auth(admin_token),
    )
    resp_bastirilmis = api_client.post(
        "/api/v1/invitations",
        json={"email": suppressed_address, "role": "member"},
        headers=_auth(admin_token),
    )

    assert resp_temiz.status_code == resp_bastirilmis.status_code == 201
    # Anahtar kümesi birebir aynı olmalı; değerler (id, e-posta, tarih) farklı.
    assert set(resp_temiz.json()) == set(resp_bastirilmis.json())

    # Fark yalnız GÖNDERİMDE: temiz adrese e-posta gitti, bastırılmışa gitmedi.
    assert [m.to for m in captured_emails if m.to == temiz] == [temiz]
    assert not [m for m in captured_emails if m.to == suppressed_address]


def test_kayit_ucu_kendi_adresi_icin_bastirmayi_soyler(
    api_client: TestClient, suppressed_address: str
) -> None:
    """ADR-0015'in TEK istisnası: çağıran kendi adresini kaydediyorsa söylenir.

    Bu bilinçli: doğrulama e-postası hiç gitmeyecekse arayüz "adresini güncelle"
    demek zorunda, yoksa kullanıcı asla gelmeyecek bir e-postayı bekler. Bilgi
    çağıranın kendi hesabına ait olduğu için kiracılar arası gözlem değildir.

    Test bu istisnanın DURDUĞUNU doğrular — kaybolursa kullanıcı sonsuza kadar
    bekler; genişlerse (ör. davet ucuna da yayılırsa) yukarıdaki testler kırılır.
    """
    resp = api_client.post(
        "/api/v1/auth/register",
        json={
            "org_name": "sup-d",
            "org_slug": "sup-d",
            "email": suppressed_address,
            "password": "sifre-12345",
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["email_delivery"] == "suppressed"


def test_bastirma_tablosu_rls_disi_ve_tenant_id_tasimaz(app_database_url: str) -> None:
    """Yapısal kapı: tablo kiracı-dışı KALMALI (ADR-0015).

    Biri `tenant_id` + RLS eklerse karar sessizce tersine döner ve gönderen
    itibarı korumasız kalır (ADR'nin reddettiği alternatif). Bu test o değişikliği
    ADR'yi güncellemeye zorlar.
    """
    engine = create_engine(app_database_url)
    try:
        with engine.connect() as connection:
            columns = set(
                connection.exec_driver_sql(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'email_suppression'"
                )
                .scalars()
                .all()
            )
            rls_enabled = connection.exec_driver_sql(
                "SELECT relrowsecurity FROM pg_class WHERE relname = 'email_suppression'"
            ).scalar_one()
    finally:
        engine.dispose()

    assert "tenant_id" not in columns, (
        "email_suppression `tenant_id` kazandı — ADR-0015 kararı değişiyorsa ADR de "
        "güncellenmeli (gerekçe: gönderen itibarı ortak kaynaktır)."
    )
    assert rls_enabled is False, "email_suppression RLS'ye alındı — bkz. ADR-0015."
