"""Webhook imza BİÇİMİ — tek tanım noktası.

İmza biçimi (hangi başlık, hangi kodlama, ne imzalanıyor) sağlayıcıya göre
değişir ve **iyzico için hâlâ dokümantasyondan yazılmış bir varsayımdır**:
merchant hesabında abonelik modülü kapalı olduğu için gerçek bir olay
alınamadı, dolayısıyla biçim canlıya karşı doğrulanamadı
(bkz. `docs/ops/billing-setup.md`, `docs/ops/DURUM.md`).

Bu yüzden biçim **veri olarak** burada durur, üç ayrı yere kopyalanmış kod
olarak değil. Gerçek bir olay ele geçtiğinde düzeltilecek yer tek: aşağıdaki
``SCHEMES`` sözlüğü. Doğrulayan uç (``billing/iyzico.py``, ``billing/provider.py``)
ve tekrar oynatma betiği (``scripts/replay_billing_webhook.py``) aynı tanımı
okur — betik "imza geçerli" derken ucun "geçersiz" demesi imkânsızdır, çünkü
ikisi de aynı hesabı yapar.

Varsayım burada **tek satırda** işaretlidir; kod okuyan biri neyin doğrulanmış
neyin tahmin olduğunu aramak zorunda kalmaz.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

Encoding = Literal["hex", "base64"]


@dataclass(frozen=True)
class WebhookSignatureScheme:
    """Bir sağlayıcının webhook imzasını nasıl ürettiği/doğruladığı.

    ``header`` imzanın taşındığı HTTP başlığı, ``encoding`` HMAC-SHA256
    özetinin metne çevrilme biçimi. ``verified`` biçimin GERÇEK bir olaya karşı
    doğrulanıp doğrulanmadığını söyler — ``False`` ise bu bir borçtur, üretimde
    ilk gerçek olayla sınanmalıdır.
    """

    provider: str
    header: str
    encoding: Encoding
    verified: bool

    def compute(self, *, secret: str, raw_body: bytes) -> str:
        """Ham gövde için beklenen imza metnini üretir."""
        digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256)
        if self.encoding == "hex":
            return digest.hexdigest()
        return base64.b64encode(digest.digest()).decode("utf-8")

    def extract(self, headers: Mapping[str, str]) -> str:
        """İmzayı başlıklardan okur (başlık adı büyük/küçük harfe duyarsız).

        Starlette'in ``Headers``ı zaten duyarsızdır ama düz ``dict`` de
        (betikler, testler) desteklenmelidir — aksi hâlde betik ucu doğru
        sınayamaz.
        """
        direct = headers.get(self.header)
        if direct is not None:
            return direct
        target = self.header.lower()
        for key, value in headers.items():
            if key.lower() == target:
                return value
        return ""

    def matches(self, *, secret: str, raw_body: bytes, headers: Mapping[str, str]) -> bool:
        """İmzayı SABİT ZAMANLI karşılaştırır.

        Sabit zamanlı karşılaştırma şart: sıradan ``==`` ilk farklı baytta döner
        ve yanıt süresi üzerinden imza bayt bayt tahmin edilebilir hâle gelir.
        """
        return hmac.compare_digest(
            self.extract(headers), self.compute(secret=secret, raw_body=raw_body)
        )


#: Manual/test-modu sağlayıcı — kendi biçimimiz, tanımı gereği doğrulanmıştır.
_MANUAL_HEADER = "x-tenderiq-signature"

SCHEMES: dict[str, WebhookSignatureScheme] = {
    "manual": WebhookSignatureScheme(
        provider="manual", header=_MANUAL_HEADER, encoding="hex", verified=True
    ),
    "fake": WebhookSignatureScheme(
        provider="fake", header=_MANUAL_HEADER, encoding="hex", verified=True
    ),
    # ── DOĞRULANMADI ────────────────────────────────────────────────────────
    # Başlık adı ve base64 kodlaması iyzico dokümantasyonundan alındı; gerçek
    # bir olayla sınanmadı (abonelik modülü kapalı). İlk gerçek olay geldiğinde
    # `scripts/replay_billing_webhook.py --record` ile kaydedilip burası
    # düzeltilir ve `verified=True` yapılır.
    "iyzico": WebhookSignatureScheme(
        provider="iyzico", header="x-iyz-signature-v3", encoding="base64", verified=False
    ),
}


def get_scheme(provider: str) -> WebhookSignatureScheme:
    """Sağlayıcının imza biçimini döndürür; tanımsızsa hata.

    Sessizce bir varsayılana düşmek, imzasız bir sağlayıcıyı "doğrulandı"
    saymak demek olurdu.
    """
    try:
        return SCHEMES[provider]
    except KeyError:
        raise KeyError(
            f"'{provider}' için webhook imza biçimi tanımlı değil (billing/signature.py)."
        ) from None
