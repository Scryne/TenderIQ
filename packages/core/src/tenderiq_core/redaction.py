"""Hassas alan adları ve gövde redaksiyonu — **tek tanım noktası**.

Bu liste iki kapıyı birden besler ve bilerek tek yerde durur:

1. **Statik kapı** (``packages/core/tests/test_log_pii.py``): kaynak ağacındaki
   ``logger.*`` çağrılarında bu adlarla anahtar sözcük kullanılamaz.
2. **Çalışma zamanı redaksiyonu** (bu modüldeki ``redact``): dışarıdan gelen bir
   gövdeyi **saklamadan önce** temizler.

İkincisi Tur 8'de gerekti: ölü mektup kuyruğu, uygulanamayan webhook gövdesini
**veritabanında saklıyor** ve o gövde sağlayıcıdan geliyor. Kart verisi bize
gelmemeli (ADR-0014: PAN/CVV sağlayıcının formunda kalır) ama bir gövdeyi
"gelmemeli" varsayımıyla olduğu gibi saklamak, varsayım yanlışsa PCI kapsamına
girmek demektir. Log kapısıyla aynı listeyi kullanmak ayrıca şu tuzağı kapatır:
biri listeye yeni bir alan eklediğinde iki kapı da aynı anda kapanır, biri
unutulmaz.

Redaksiyon **anahtarı silmez, değeri değiştirir**: kuyruğa düşen olayı inceleyen
kişi hangi alanların geldiğini görmeli (asıl teşhis bilgisi budur), yalnız
değerlerini görmemeli.
"""

from __future__ import annotations

from typing import Any

#: Değeri kişisel veri, müşteri içeriği ya da kimlik bilgisi taşıyabilecek
#: alan adları. Küçük harfe indirgenerek karşılaştırılır.
#:
#: Liste bilerek kısadır; uzarsa kapı anlamını yitirir. Yeni bir ad eklemeden
#: önce sor: bu alanın DEĞERİ 30 gün saklanan bir kayıtta durursa zarar var mı?
SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "address",
        "adres",
        # ── Ödeme ── Kart verisi bize hiç GELMEZ (sağlayıcı tokenize eder).
        # Yine de yasaklanır: bir adaptör yazarken sağlayıcı yanıtını olduğu
        # gibi loglamak/saklamak en kolay hatadır ve kart verisinin kayda
        # düşmesi PCI kapsamına girmek demektir.
        "card",
        "card_number",
        "cardholder",
        "cvc",
        "cvv",
        "expiry",
        "iban",
        "iyzico_api_key",
        "iyzico_secret_key",
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

#: Redakte edilmiş değerin yerine yazılan işaret. Boş dize DEĞİL: kaydı okuyan
#: kişi "alan boş geldi" ile "alan gizlendi" arasındaki farkı görmeli.
REDACTED = "«gizlendi»"

#: Saklanacak gövde için üst sınır. Uçları imzasız da çağrılabilen bir yüzeyde
#: (webhook) sınırsız gövde saklamak, depolamayı şişirmenin bedava yoludur.
MAX_STORED_BODY_CHARS = 8_000


def is_sensitive(name: str) -> bool:
    """Alan adı hassas listesinde mi (büyük/küçük harf duyarsız)."""
    return name.lower() in SENSITIVE_FIELDS


def redact(value: Any, *, depth: int = 0) -> Any:
    """Bir JSON değerini saklanabilir hâle getirir (özyinelemeli).

    Sözlük anahtarları korunur, hassas olanların DEĞERİ ``REDACTED`` ile
    değiştirilir. Derinlik sınırı, kendine referans veren ya da patolojik
    derinlikte bir gövdenin özyinelemeyi patlatmasını önler.
    """
    if depth > 12:
        return REDACTED
    if isinstance(value, dict):
        return {
            str(key): (REDACTED if is_sensitive(str(key)) else redact(item, depth=depth + 1))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, depth=depth + 1) for item in value]
    return value


def redact_raw_body(raw_body: bytes) -> tuple[dict[str, Any] | None, str | None]:
    """Ham gövdeyi saklanabilir hâle getirir.

    Dönen ikili: (redakte edilmiş JSON nesnesi, çözülemeyen gövdenin kırpılmış
    metni). JSON olarak ayrıştırılamayan gövde de saklanır — ayrıştırılamaması
    zaten teşhis edilecek şeyin ta kendisi olabilir (ör. sağlayıcı biçimi
    beklediğimizden farklı) — ama kırpılarak ve alan bazlı redaksiyon
    uygulanamadan; bu yüzden metin dalı yalnız son çare içindir.
    """
    import json

    try:
        parsed = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        text = raw_body.decode("utf-8", errors="replace")[:MAX_STORED_BODY_CHARS]
        return None, text
    if not isinstance(parsed, dict):
        return None, str(parsed)[:MAX_STORED_BODY_CHARS]
    redacted = redact(parsed)
    assert isinstance(redacted, dict)  # noqa: S101 - dict girdi ⇒ dict çıktı
    return redacted, None
