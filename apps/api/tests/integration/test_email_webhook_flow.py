"""Bounce/şikâyet webhook'u — imza doğrulama + bastırma mantığı UÇTAN UCA.

Tur 2'den kalan borç: bu uç için hiç test yoktu. Uçta üç savunma üst üste
duruyor ve üçü de birim testinde "çalışıyor" görünüp gerçek bir HTTP isteğinde
çalışmayabilir, çünkü hepsi **ham gövde baytlarına** bağlı:

- İmza, gövdenin baytları üzerinden hesaplanır. `json=` ile gönderip sunucuda
  yeniden serileştirmek imzayı bozar; bu yüzden testler `content=` ile HAM bayt
  gönderir — sağlayıcının yaptığı da budur.
- Sır yapılandırılmamışsa uç **404** döner (varlığı sızmaz), 401 değil.
- Yumuşak bounce bastırılmaz: kutu dolu diye bir kullanıcıyı kalıcı olarak
  iletişim dışına atmak, webhook'un çözdüğü sorundan daha büyük bir sorundur.

Son test bastırmanın **etkisini** ölçüyor: webhook'tan sonra sistem o adrese
gerçekten göndermiyor mu? Yalnız satırın DB'ye yazıldığını doğrulamak, tablonun
okunmadığı bir hâli gözden kaçırırdı.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from tenderiq_core.config import get_settings
from tenderiq_core.email import EmailMessage, MemoryEmailProvider
from tenderiq_core.models import EmailSuppression, SuppressionReason

pytestmark = pytest.mark.integration

WEBHOOK_PATH = "/api/v1/email/webhook"
SIGNATURE_HEADER = "x-tenderiq-email-signature"
SECRET = "test-email-webhook-sirri"


def _sign(raw: bytes, secret: str = SECRET) -> dict[str, str]:
    digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return {SIGNATURE_HEADER: digest, "content-type": "application/json"}


def _raw(payload: dict[str, object]) -> bytes:
    """Gövdeyi bir kez serileştirir — imza ve istek AYNI baytları görmeli."""
    return json.dumps(payload).encode("utf-8")


def _event(
    event_type: str, email: str, *, bounce_type: str | None = None, event_id: str | None = None
) -> dict[str, object]:
    data: dict[str, object] = {"to": [email]}
    if bounce_type is not None:
        data["bounce_type"] = bounce_type
    return {"type": event_type, "id": event_id or f"evt_{uuid.uuid4().hex}", "data": data}


@pytest.fixture
def webhook_secret(app_database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Sırrı yapılandırır ve ayar önbelleğini temizler.

    Ayarlar `lru_cache`li ve istek başına `Depends(get_settings)` ile çözülüyor;
    bu yüzden env'i değiştirip önbelleği temizlemek yeterli — uygulamayı yeniden
    kurmak gerekmez.
    """
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def suppressions(app_database_url: str) -> Iterator[Session]:
    """Bastırma tablosunu okuyup test sonunda temizler (tablo kiracı-dışı)."""
    engine = create_engine(app_database_url)
    try:
        with Session(engine) as session:
            yield session
        with Session(engine) as session, session.begin():
            session.execute(delete(EmailSuppression))
    finally:
        engine.dispose()


def _stored(session: Session, email: str) -> EmailSuppression | None:
    session.expire_all()
    return session.scalar(select(EmailSuppression).where(EmailSuppression.email == email))


def test_sir_yapilandirilmamissa_uc_404_doner(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sır yoksa uç YOK gibi davranır — kapalı kurulumda varlığı bile sızmaz.

    **Durum kodu tek başına yetmez.** Rota hiç kayıtlı olmasa Starlette de 404
    döner ve bu test yeşil kalırdı — Tur 10'da bulunan kusur tam buydu: uç
    modülü ve mantığı vardı, `routers/v1/__init__.py`ye eklenmemişti, yani
    sağlayıcının her bildirimi 404 alıyordu. Bu yüzden GÖVDEDEKİ mesaj da
    doğrulanıyor: bizim `NotFoundError`umuz Türkçe mesaj taşır, Starlette'in
    "route yok" 404'ü taşımaz.
    """
    # `.env`de sır tanımlı olabilir; yokluğu AÇIKÇA kurulur (aksi hâlde test
    # geliştirici makinesinin yapılandırmasına bağlı olurdu).
    monkeypatch.delenv("RESEND_WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        raw = _raw(_event("email.bounced", "kimse@dıs.com"))
        resp = api_client.post(WEBHOOK_PATH, content=raw, headers=_sign(raw))

        assert resp.status_code == 404, resp.text
        assert resp.json()["error"]["message"] == "Bulunamadı.", (
            f"404 bizim uçtan değil Starlette'ten geliyor — rota kayıtlı mı? Gelen: {resp.text}"
        )
    finally:
        get_settings.cache_clear()


def test_gecerli_imza_kalici_bounce_adresi_bastirir(
    api_client: TestClient, webhook_secret: None, suppressions: Session
) -> None:
    email = "kalici-bounce@dıs.com"
    raw = _raw(_event("email.bounced", email, bounce_type="hard"))

    resp = api_client.post(WEBHOOK_PATH, content=raw, headers=_sign(raw))

    assert resp.status_code == 204, resp.text
    stored = _stored(suppressions, email)
    assert stored is not None, "kalıcı bounce bastırma listesine yazılmadı"
    assert stored.reason is SuppressionReason.HARD_BOUNCE


def test_gecersiz_imza_reddedilir_ve_hicbir_sey_yazilmaz(
    api_client: TestClient, webhook_secret: None, suppressions: Session
) -> None:
    """İmza geçmezse 401 VE yan etki yok.

    Yalnız durum kodunu doğrulamak yetmez: uç imzayı doğrulamadan önce yazsaydı
    401 de dönebilir, satır da yazılabilirdi. Yazma yolunun kapalı olduğu ayrıca
    kontrol edilir — asıl risk bu (imzasız biri istediği adresi bastırabilirdi).
    """
    email = "sahte-imza@dıs.com"
    raw = _raw(_event("email.bounced", email, bounce_type="hard"))
    headers = _sign(raw)
    # Tek karakteri boz.
    bozuk = headers[SIGNATURE_HEADER]
    headers[SIGNATURE_HEADER] = ("b" if bozuk[0] != "b" else "c") + bozuk[1:]

    resp = api_client.post(WEBHOOK_PATH, content=raw, headers=headers)

    assert resp.status_code == 401, resp.text
    assert _stored(suppressions, email) is None


def test_imza_basligi_yoksa_reddedilir(
    api_client: TestClient, webhook_secret: None, suppressions: Session
) -> None:
    email = "imzasiz@dıs.com"
    raw = _raw(_event("email.bounced", email, bounce_type="hard"))

    resp = api_client.post(WEBHOOK_PATH, content=raw, headers={"content-type": "application/json"})

    assert resp.status_code == 401, resp.text
    assert _stored(suppressions, email) is None


def test_govde_kurcalanirsa_imza_gecmez(
    api_client: TestClient, webhook_secret: None, suppressions: Session
) -> None:
    """İmza DOĞRU gövde için üretilir, istek BAŞKA gövdeyle gönderilir.

    Saldırganın en doğal denemesi budur: geçerli bir olayı yakalayıp alıcıyı
    değiştirmek. İmza ham baytlara bağlı olduğu için geçmemeli.
    """
    kurban = "kurban@dıs.com"
    imzali = _raw(_event("email.bounced", "gercek@dıs.com", bounce_type="hard"))
    headers = _sign(imzali)
    kurcalanmis = _raw(_event("email.bounced", kurban, bounce_type="hard"))

    resp = api_client.post(WEBHOOK_PATH, content=kurcalanmis, headers=headers)

    assert resp.status_code == 401, resp.text
    assert _stored(suppressions, kurban) is None


def test_yumusak_bounce_bastirilmaz(
    api_client: TestClient, webhook_secret: None, suppressions: Session
) -> None:
    """Kutu dolu / geçici hata: adres geçerlidir, bastırmak kullanıcıyı kaybetmek olur."""
    email = "kutusu-dolu@dıs.com"
    raw = _raw(_event("email.bounced", email, bounce_type="soft"))

    resp = api_client.post(WEBHOOK_PATH, content=raw, headers=_sign(raw))

    assert resp.status_code == 204, resp.text
    assert _stored(suppressions, email) is None


def test_sikayet_olayi_complaint_sebebiyle_bastirir(
    api_client: TestClient, webhook_secret: None, suppressions: Session
) -> None:
    """Spam şikâyeti: yalnız itibar değil, yasal olarak da göndermeyi kesmeliyiz."""
    email = "sikayetci@dıs.com"
    raw = _raw(_event("email.complained", email))

    resp = api_client.post(WEBHOOK_PATH, content=raw, headers=_sign(raw))

    assert resp.status_code == 204, resp.text
    stored = _stored(suppressions, email)
    assert stored is not None
    assert stored.reason is SuppressionReason.COMPLAINT


def test_ilgisiz_olay_yok_sayilir(
    api_client: TestClient, webhook_secret: None, suppressions: Session
) -> None:
    """`email.delivered` gibi olaylara abone olmak ucuz; işlemek gereksiz."""
    email = "teslim-edildi@dıs.com"
    raw = _raw(_event("email.delivered", email))

    resp = api_client.post(WEBHOOK_PATH, content=raw, headers=_sign(raw))

    assert resp.status_code == 204, resp.text
    assert _stored(suppressions, email) is None


def test_ayni_olay_iki_kez_gelirse_tek_satir_kalir(
    api_client: TestClient, webhook_secret: None, suppressions: Session
) -> None:
    """Sağlayıcı 2xx görmezse tekrar dener; uç ikinci teslimde ÇÖKMEMELİ.

    `email` kolonu unique: ön-kontrol olmadan ikinci INSERT bir IntegrityError
    ile 500 üretirdi ve sağlayıcı sonsuza kadar yeniden denerdi.
    """
    email = "iki-kez@dıs.com"
    raw = _raw(_event("email.bounced", email, bounce_type="hard", event_id="evt_sabit_tekrar"))

    first = api_client.post(WEBHOOK_PATH, content=raw, headers=_sign(raw))
    second = api_client.post(WEBHOOK_PATH, content=raw, headers=_sign(raw))

    assert first.status_code == 204, first.text
    assert second.status_code == 204, second.text
    suppressions.expire_all()
    rows = suppressions.scalars(
        select(EmailSuppression).where(EmailSuppression.email == email)
    ).all()
    assert len(rows) == 1


def test_bastirma_sonrasi_sistem_o_adrese_gondermez(
    api_client: TestClient, webhook_secret: None, suppressions: Session
) -> None:
    """Webhook → bastırma → gönderim GERÇEKTEN durdu mu (uçtan uca).

    Zincirin son halkası: satır yazıldı ama okunmuyorsa hiçbir şey değişmemiş
    olur. Bounce sonrası aynı adresle kayıt olunuyor; doğrulama e-postası
    gönderilmemeli ve uç bunu `email_delivery=suppressed` ile bildirmeli
    (ADR-0015'in tek istisnası: çağıran kendi adresi).
    """
    provider = MemoryEmailProvider()
    api_client.app.state.email_provider = provider
    sent: list[EmailMessage] = provider.sent

    email = "bounce-sonra-kayit@dıs.com"
    raw = _raw(_event("email.bounced", email, bounce_type="hard"))
    assert api_client.post(WEBHOOK_PATH, content=raw, headers=_sign(raw)).status_code == 204
    assert _stored(suppressions, email) is not None

    resp = api_client.post(
        "/api/v1/auth/register",
        json={
            "org_name": "bounce-sonrasi",
            "org_slug": "bounce-sonrasi",
            "email": email,
            "password": "sifre-12345",
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["email_delivery"] == "suppressed"
    assert not [m for m in sent if m.to == email], "bastırılmış adrese e-posta gönderildi"
