"""Bağlanmamış artefakt denetimi — tanımlanmış ama hiçbir yere takılmamış kod.

## Neden bu dosya var

Tur 10'da iki **ölü artefakt** bulundu ve ikisi de haftalarca sessiz kaldı:

1. `email_webhook.router` — modülü, mantığı ve gerekçesi yazılmış ama
   `routers/v1/__init__.py`ye eklenmemişti. Sağlayıcının her bounce bildirimi
   404 alıyordu; hiçbir adres bastırılmıyordu.
2. CI'ın `e2e` + `image-scan` job'ları — tanımlıydı ama push edilmemiş bir
   commit'te olduğu için hiç koşmamıştı.

Ortak kalıp: **artefakt var, kayıt yok.** Böyle bir kusur test kırmaz (kimse o
kodu çağırmıyor), tip denetimi kırmaz (kod geçerli), lint kırmaz (import
edilmiş). Yalnız üretimde, sessizce, hiçbir şey yapmayarak görünür.

Bu dosya o SINIFI kapatır: her artefakt türü için "kayıtlı mı" değişmezi
kurulur. Kasıtlı istisnalar aşağıdaki listelerde **gerekçesiyle** durur —
listeye eklemek bir karardır, refleks değil.

## Neden dosya adına göre değil, IMPORT ederek

Keşif `pkgutil.walk_packages` ile modülleri gerçekten import eder ve modül
düzeyindeki nesneleri inceler. Dosya adı taramak ya da `grep` yapmak, adı
beklenen kalıba uymayan (`routers/v1/email_webhook.py` gibi) bir artefaktı
kaçırırdı — kaçan artefakt tam olarak buydu.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType

import pytest
from fastapi import APIRouter, FastAPI

import tenderiq_api.routers as routers_package
from tenderiq_api.main import create_app

# ── Kasıtlı istisnalar ───────────────────────────────────────────────────────

#: Uygulamaya kayıtlı OLMAMASI beklenen router'lar (ad → gerekçe).
#: Boş bırakmak da bir karar: şu an her router kayıtlı.
ROUTER_EXCEPTIONS: dict[str, str] = {
    # Toplayıcı: kendi rotası yok, diğer router'ları içerir. `create_app` onu
    # `/api/v1` önekiyle bağlar; rotasız olduğu için denetime girmez.
    "tenderiq_api.routers.v1": "toplayıcı router (kendi rotası yok)",
}

#: Rotası olmayan router'ı denetlemek anlamsız (bağlı olsa da kanıtı yok).
#: Bu yüzden rotasızlar otomatik atlanır; istisna listesine gerek kalmaz.


def _iter_modules(package: ModuleType) -> list[ModuleType]:
    """Paketi ve tüm alt modüllerini IMPORT ederek döndürür."""
    modules = [package]
    for info in pkgutil.walk_packages(package.__path__, prefix=f"{package.__name__}."):
        modules.append(importlib.import_module(info.name))
    return modules


def _discovered_routers() -> dict[str, APIRouter]:
    """Modül düzeyinde tanımlı tüm `APIRouter` nesneleri (modül adına göre)."""
    found: dict[str, APIRouter] = {}
    for module in _iter_modules(routers_package):
        for _, value in vars(module).items():
            if isinstance(value, APIRouter) and value.routes:
                # Aynı router birden çok modülde re-export edilebilir; ilk
                # tanımlandığı modül adıyla kaydedilir.
                found.setdefault(module.__name__, value)
    return found


#: Rotanın gerçekten aranacağı önekler. `create_app` iki şema kullanıyor:
#: köke bağlananlar (health/ops/_test) ve `/api/v1` altına bağlananlar.
#: Üçüncü bir önek eklenirse bu liste büyümeli — büyümezse denetim o router'ı
#: "bağlanmamış" sayar, yani sessiz kalmaz.
PREFIX_CANDIDATES = ("", "/api/v1")

#: Yol parametreleri için yer tutucular. Değerin geçerli olması gerekmez:
#: aranan şey 404-YÖNLENDİRME hatasının olmaması, işin başarısı değil.
_PARAM_STUB = "00000000-0000-0000-0000-000000000000"


def _concrete_path(path: str) -> str:
    """`/tenders/{tender_id}/x` → `/tenders/<uuid>/x`."""
    out: list[str] = []
    for segment in path.split("/"):
        out.append(_PARAM_STUB if segment.startswith("{") and segment.endswith("}") else segment)
    return "/".join(out)


def _is_routing_404(response: object) -> bool:
    """Yanıt "böyle bir rota yok" 404'ü mü (yetki/doğrulama hatası değil)?"""
    status = getattr(response, "status_code", None)
    if status != 404:
        return False
    try:
        body = response.json()  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - gövdesiz 404
        return True
    # Uygulamanın kendi `NotFoundError`u Türkçe mesaj taşır; Starlette'in
    # yönlendirme 404'ü "Not Found" der. Ayrım tam olarak buradadır.
    return bool(body.get("error", {}).get("message") == "Not Found")


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return create_app()


@pytest.fixture(scope="module")
def client(app: FastAPI):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    # `raise_server_exceptions=False`: rota kayıtlı ama DB/Redis yoksa uç 500
    # verir. 500 bu denetim için BAŞARIDIR (rota bulundu); istisnanın testi
    # patlatması aranan şeyi gizlerdi.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_her_router_uygulamaya_kayitli(client) -> None:  # type: ignore[no-untyped-def]
    """Tanımlı her router GERÇEKTEN erişilebilir olmalı.

    Denetim rota tablosunu okumak yerine **istek atar**. Sebebi: FastAPI
    `include_router`ı tembel `_IncludedRouter` nesneleriyle tutuyor ve
    `app.routes` üzerinden yolları düzleştirmek özel API'ye bağımlı olurdu (bu
    dosya bir kez öyle yazıldı ve her router'ı "bağlanmamış" sandı). Erişilebilirlik
    zaten sormak istediğimiz sorunun kendisi: sağlayıcı bu yola POST ettiğinde
    404 mü alıyor?
    """
    baglanmamis: list[str] = []

    for module_name, router in _discovered_routers().items():
        if module_name in ROUTER_EXCEPTIONS:
            continue
        erisilebilir = False
        denenen: list[str] = []
        for route in router.routes:
            path = getattr(route, "path", "")
            if not path:
                continue
            method = next(iter(sorted(getattr(route, "methods", {"GET"}) - {"HEAD", "OPTIONS"})))
            for prefix in PREFIX_CANDIDATES:
                url = _concrete_path(f"{prefix}{path}")
                denenen.append(f"{method} {url}")
                if not _is_routing_404(client.request(method, url)):
                    erisilebilir = True
                    break
            if erisilebilir:
                break
        if not erisilebilir:
            baglanmamis.append(f"{module_name} — denenen: {denenen[:4]}")

    assert not baglanmamis, (
        "Tanımlı ama ERİŞİLEMEYEN router var — `include_router` çağrısı eksik. "
        "Kasıtlıysa ROUTER_EXCEPTIONS'a gerekçesiyle ekle:\n  " + "\n  ".join(baglanmamis)
    )


def test_router_istisnalari_gerekcesiz_olamaz() -> None:
    """İstisna listesi gerekçesiz büyümesin — boş gerekçe kabul edilmez."""
    gerekcesiz = [name for name, reason in ROUTER_EXCEPTIONS.items() if not reason.strip()]
    assert not gerekcesiz, f"gerekçesiz istisna: {gerekcesiz}"


def test_webhook_uclari_erisilebilir(client) -> None:  # type: ignore[no-untyped-def]
    """Her webhook rotası GERÇEKTEN erişilebilir olmalı.

    Webhook'lar bu kusura en açık uçlardır: kimliksizdirler, bir insan onları
    tarayıcıda açmaz ve sağlayıcı 404'ü sessizce yutar. Ayrıca çoğu "sır
    yapılandırılmamışsa 404 dön" kalıbını kullanır — yani rotanın hiç
    olmaması ile kapalı olması AYNI durum koduna düşer. Tur 10'da bounce
    webhook'u tam bu yüzden haftalarca ölü kaldı.
    """
    webhook_paths = sorted(
        getattr(route, "path", "")
        for router in _discovered_routers().values()
        for route in router.routes
        if "webhook" in getattr(route, "path", "")
    )
    # Bilinen iki webhook: ödeme ve e-posta. Liste küçülürse bir uç kaybolmuş,
    # büyürse yeni bir webhook eklenmiş demektir (ikisi de görünür olmalı).
    assert any(p.endswith("/billing/webhook") for p in webhook_paths), webhook_paths
    assert any(p.endswith("/email/webhook") for p in webhook_paths), webhook_paths

    erisilemeyen = [
        path
        for path in webhook_paths
        if all(_is_routing_404(client.post(f"{prefix}{path}")) for prefix in PREFIX_CANDIDATES)
    ]
    assert not erisilemeyen, (
        "Webhook rotası tanımlı ama ERİŞİLEMİYOR (sağlayıcının her bildirimi "
        f"404 alır): {erisilemeyen}"
    )


def test_rota_yok_ile_sir_yok_ayirt_edilebilir(app: FastAPI) -> None:
    """404 gövdesi "rota yok" ile "sır yapılandırılmamış"ı ayırt ETMELİ.

    Tur 10'un kusuru tam burada saklandı: `email/webhook` kayıtlı değildi,
    Starlette 404 döndürdü ve bu, sır yapılandırılmamış kurulumun BEKLENEN
    yanıtıyla aynı durum koduydu. Uygulamanın hata zarfı ikisinde de aynı
    (`{"error": {...}}`), fark yalnız MESAJDA: bizim `NotFoundError`umuz Türkçe
    mesaj taşır, Starlette'in yönlendirme 404'ü "Not Found" der.

    Bu test o ayrımın DURDUĞUNU sabitler; kaybolursa aynı kusur yeniden
    görünmez hâle gelir.
    """
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yok = client.post("/api/v1/kesinlikle-olmayan-bir-yol")
        assert yok.status_code == 404
        assert yok.json()["error"]["message"] == "Not Found", (
            "Yönlendirme 404'ünün mesajı değişmiş; bu testin ayırt etme "
            f"dayanağı kalmadı: {yok.text}"
        )


# ── Sağlayıcı/adaptör ↔ fabrika bağlantısı ───────────────────────────────────

#: Fabrikaya bağlı OLMAMASI beklenen sağlayıcı sınıfları (ad → gerekçe).
ADAPTER_EXCEPTIONS: dict[str, str] = {}


def _provider_implementations(package_name: str, suffix: str) -> dict[str, type]:
    """Paketteki `*<suffix>` sınıflarını bulur (protokolün kendisi hariç)."""
    package = importlib.import_module(package_name)
    found: dict[str, type] = {}
    for module in _iter_modules(package):
        for name, value in vars(module).items():
            if (
                inspect.isclass(value)
                and name.endswith(suffix)
                and name != suffix
                and value.__module__.startswith(package_name)
            ):
                found[name] = value
    return found


@pytest.mark.parametrize(
    ("package_name", "suffix", "factory_path"),
    [
        (
            "tenderiq_core.email",
            "EmailProvider",
            "tenderiq_core.email.provider:create_email_provider",
        ),
        (
            "tenderiq_core.billing",
            "BillingProvider",
            "tenderiq_core.billing.provider:create_billing_provider",
        ),
    ],
)
def test_her_adaptor_fabrikaya_bagli(package_name: str, suffix: str, factory_path: str) -> None:
    """Yazılmış her sağlayıcı adaptörü fabrikada ADI GEÇMELİ.

    Fabrikalar dizeye göre dallanıyor (`if provider == "iyzico": ...`). Yeni bir
    adaptör yazıp fabrikaya eklemeyi unutmak, tam olarak Tur 10'daki router
    kusurunun ikizidir: sınıf vardır, hiçbir yapılandırma onu üretemez.

    Denetim fabrikanın KAYNAĞINDA sınıf adını arar. Davranışı sınamaz (o, her
    adaptörün kendi testinin işi) — yalnız bağlantının varlığını sınar; bu,
    kaçan kusurun tam olarak eksik olduğu şeydir.
    """
    module_name, _, func_name = factory_path.partition(":")
    factory = getattr(importlib.import_module(module_name), func_name)
    source = inspect.getsource(factory)

    baglanmamis = [
        name
        for name in _provider_implementations(package_name, suffix)
        if name not in ADAPTER_EXCEPTIONS and name not in source
    ]

    assert not baglanmamis, (
        f"{suffix} adaptörü yazılmış ama {func_name} onu üretemiyor "
        "(fabrikada adı geçmiyor). Kasıtlıysa ADAPTER_EXCEPTIONS'a gerekçesiyle "
        f"ekle:\n  {baglanmamis}"
    )
