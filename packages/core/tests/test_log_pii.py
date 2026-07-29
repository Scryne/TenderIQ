"""Log PII denetimi (J.4 · saklama matrisi §5.2) — statik kapı.

Loglar merkezî bir toplayıcıda **≥30 gün** saklanır. Oraya bir kez sızan kişisel
veri, silme talebinin (KVKK md. 7) ulaşamadığı bir kopya üretir: silme akışımız
veritabanını ve nesne depolamayı temizler, log arşivini değil. Bu yüzden kural
"loglara PII yazmayalım" temennisi değil, **derleme zamanı kapısı** olmalıdır.

Denetim iki şeye bakar:

1. Log çağrılarının anahtar sözcük adları — ``email=``, ``body=``, ``text=`` gibi
   bir ad, değerinin ne olduğunu okumadan da riski ele verir.
2. Olay adının sabit olması — f-string bir olay adı, PII'ın en sık sızma yolu
   (``logger.info(f"kullanıcı {email} giriş yaptı")``) ve aynı zamanda logların
   toplanabilirliğini bitirir.

Yeni bir alan gerçekten gerekiyorsa: ya maskele (``logging.mask_email``), ya
korelasyon kimliği yaz (``user_id``/``tenant_id``), ya da bilinçli bir istisnayı
aşağıdaki listeye **gerekçesiyle** ekle. Liste bilerek kısadır; uzarsa kapı
anlamını yitirir.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tenderiq_core.logging import mask_email

# Depo köküne göre çözülür: tarama, pytest'in çalışma dizinine bağlı olmamalı —
# yanlış dizinde "hiç çağrı bulunamadı" sessiz bir GEÇTİ üretirdi.
REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOTS = ("packages/core/src", "apps/api/src", "apps/worker/src")

_LOG_METHODS = frozenset({"debug", "info", "warning", "error", "exception", "critical"})
_LOGGER_NAMES = frozenset({"logger", "log", "_logger"})

#: Değeri kişisel veri veya müşteri içeriği taşıyabilecek alan adları.
FORBIDDEN_LOG_FIELDS = frozenset(
    {
        "address",
        "adres",
        # ── Ödeme (Tur 3) ── Kart verisi bize hiç GELMEZ (sağlayıcı tokenize
        # eder). Yine de log alanı olarak yasaklanır: bir adaptör yazarken
        # sağlayıcı yanıtını olduğu gibi loglamak en kolay hatadır ve kart
        # verisinin loga düşmesi PCI kapsamına girmek demektir.
        "card",
        "card_number",
        "cardholder",
        "cvc",
        "cvv",
        "expiry",
        "iban",
        "kart",
        "pan",
        "alinti",
        "api_key",
        "authorization",
        "baslik",
        "body",
        "completion",
        "content",
        "dosya_adi",
        "e_posta",
        "email",
        "filename",
        "full_name",
        "icerik",
        "ip",
        "metin",
        "parola",
        "password",
        "phone",
        "prompt",
        "quote",
        "recipient",
        "secret",
        "telefon",
        "text",
        "title",
        "to",
        "token",
    }
)

#: (dosya son eki, olay adı) → gerekçe. Yalnız PRODUCTION'da erişilemeyen yollar.
ALLOWED_EXCEPTIONS: dict[tuple[str, str], str] = {
    (
        "email/provider.py",
        "hesap_epostasi",
    ): (
        "LoggingEmailProvider yalnız dev'dir (EMAIL_PROVIDER=logging) ve production'da "
        "açılışta reddedilir "
        "(config._enforce_production_hardening). Bu dalın TEK amacı doğrulama/sıfırlama "
        "bağlantısını geliştiriciye ulaştırmaktır; gövde zaten kasten loglanır."
    ),
}


def _iter_log_calls() -> list[tuple[Path, ast.Call]]:
    """Kaynak ağacındaki tüm ``logger.<seviye>(...)`` çağrılarını toplar."""
    calls: list[tuple[Path, ast.Call]] = []
    for root in SOURCE_ROOTS:
        for path in (REPO_ROOT / root).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute) or func.attr not in _LOG_METHODS:
                    continue
                if isinstance(func.value, ast.Name) and func.value.id in _LOGGER_NAMES:
                    calls.append((path, node))
    return calls


def _event_name(call: ast.Call) -> str | None:
    if not call.args:
        return None
    first = call.args[0]
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None


def _exception_reason(path: Path, event: str | None) -> str | None:
    posix = path.as_posix()
    for (suffix, allowed_event), reason in ALLOWED_EXCEPTIONS.items():
        if posix.endswith(suffix) and event == allowed_event:
            return reason
    return None


def test_kaynak_agaci_taranabiliyor() -> None:
    """Tarama kaynağı bulamazsa kapı sessizce 'geçti' derdi — bu, en tehlikeli hâl."""
    assert len(_iter_log_calls()) > 20


def test_log_alanlari_pii_tasimiyor() -> None:
    violations = [
        f"{path.as_posix()}:{call.lineno} → {keyword.arg}="
        for path, call in _iter_log_calls()
        for keyword in call.keywords
        if keyword.arg in FORBIDDEN_LOG_FIELDS
        and _exception_reason(path, _event_name(call)) is None
    ]

    assert not violations, "Loglara PII sızabilir:\n" + "\n".join(violations)


def test_olay_adlari_sabit() -> None:
    """Dinamik (f-string) olay adı hem PII sızdırır hem logları toplanamaz kılar."""
    violations = [
        f"{path.as_posix()}:{call.lineno}"
        for path, call in _iter_log_calls()
        if call.args and _event_name(call) is None
    ]

    assert not violations, "Olay adı sabit string olmalı:\n" + "\n".join(violations)


def test_istisna_listesi_gerekcelendirilmis() -> None:
    """Gerekçesiz istisna, istisna değil sessiz bir delik olurdu."""
    assert all(len(reason) > 40 for reason in ALLOWED_EXCEPTIONS.values())


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("berkay@tenderiq.com", "b***@tenderiq.com"),
        ("a@b.co", "a***@b.co"),
        ("bozuk-adres", "***"),
        ("@alansiz.com", "***"),
    ],
)
def test_eposta_maskeleme(value: str, expected: str) -> None:
    assert mask_email(value) == expected


def test_maskelenen_adres_yerel_kismi_sizdirmaz() -> None:
    address = "cok-uzun-kurumsal-adres@musteri.com.tr"

    masked = mask_email(address)

    assert address.split("@")[0] not in masked
    assert masked.endswith("@musteri.com.tr")
