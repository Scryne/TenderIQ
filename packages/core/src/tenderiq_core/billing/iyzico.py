"""iyzico abonelik adaptörü (ADR-0014).

Abonelik **sağlayıcı tarafında** yönetilir: yenileme, başarısız tahsilatta
yeniden deneme (dunning) ve kart güncelleme iyzico'dadır. Bu adaptörün işi
üç şeydir:

1. Checkout başlatmak (kullanıcı ödeme formuna yönlendirilir),
2. Abonelik operasyonlarını iletmek (iptal, plan değişimi),
3. Webhook'u doğrulayıp **bizim** olay modelimize çevirmek.

**3D Secure zorunludur.** iyzico'nun abonelik ürününde ilk tahsilat müşteri
huzurunda (CIT) 3DS ile alınır; sonraki yenilemeler müşteri yokken (MIT) çekilir
ve bu ayrımı sağlayıcı yönetir. Adaptör non-3DS bir yol **sunmaz** — sunmamak
bir özellik eksikliği değil, bilinçli bir kısıt: 3DS'siz akış sorumluluğu bize
yıkar ve Türkiye'de kart şeması kuralları gereği yenilemeyi kırılgan kılar.

**Kart verisi bu sürece hiç girmez.** PAN/CVV iyzico'nun formunda kalır; biz
yalnız token ve abonelik kimliği görürüz.

> **Sandbox doğrulaması (2026-07-29).** İmza şeması **gerçeğe karşı doğrulandı**:
> yanlış sırla 401 `errorCode:8`, payload'sız imzayla yine 401 → yani imza
> `randomKey + uriPath + payload` üzerinden hesaplanıyor ve payload dâhil.
> `/payment/bin/check` aynı anahtarlarla 200 döndü.
>
> **Ancak `/v2/subscription/*` uçlarının HİÇBİRİ çalışmıyor:** gövde ne olursa
> olsun `422 errorCode:100001`. Merchant hesabında abonelik modülü etkin
> değil (hesap işlemi — bkz. `docs/ops/billing-setup.md`). Bu yüzden abonelik
> istek/yanıt ŞEMASI hâlâ dokümantasyondan yazılmış varsayımdır.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
import string
import uuid
from collections.abc import Mapping
from typing import Any

import httpx

from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.billing.provider import (
    BillingError,
    CheckoutResult,
    ProviderSubscriptionState,
    WebhookEvent,
    WebhookVerificationError,
)
from tenderiq_core.logging import get_logger
from tenderiq_core.models import SubscriptionStatus

logger = get_logger("tenderiq.core.billing.iyzico")

SANDBOX_BASE_URL = "https://sandbox-api.iyzipay.com"
PRODUCTION_BASE_URL = "https://api.iyzipay.com"

#: iyzico webhook imzasının taşındığı başlık.
IYZICO_SIGNATURE_HEADER = "x-iyz-signature-v3"

_TIMEOUT_SECONDS = 20.0
_RANDOM_KEY_LENGTH = 24

#: iyzico'nun jenerik hata kodu. Tek başına neredeyse hiçbir şey söylemez;
#: bağlamla (hangi uç) birleştirildiğinde anlam kazanır.
_GENERIC_ERROR_CODE = "100001"

#: Sağlayıcı abonelik durumu → bizim yetkilendirme durumumuz.
#: Eşlenmeyen bir durum sessizce "aktif" sayılmaz; olay yok sayılır.
_STATUS_MAP: dict[str, SubscriptionStatus] = {
    "ACTIVE": SubscriptionStatus.ACTIVE,
    "PENDING": SubscriptionStatus.ACTIVE,
    "UNPAID": SubscriptionStatus.PAST_DUE,
    "CANCELED": SubscriptionStatus.CANCELED,
    "EXPIRED": SubscriptionStatus.CANCELED,
}


def _random_key() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(_RANDOM_KEY_LENGTH))  # noqa: S311


def build_authorization(
    *, api_key: str, secret_key: str, uri_path: str, payload: str, random_key: str
) -> str:
    """iyzico ``IYZWSv2`` yetkilendirme başlığını üretir.

    İmza, **rastgele anahtar + URI yolu + gövde** üzerinden HMAC-SHA256'dır;
    yani aynı gövdenin farklı bir uca tekrar oynatılması (replay) imzayı
    geçersiz kılar. Başlık base64'lenmiş bir anahtar/değer dizisidir.
    """
    signature = hmac.new(
        secret_key.encode("utf-8"),
        f"{random_key}{uri_path}{payload}".encode(),
        hashlib.sha256,
    ).hexdigest()
    authorization = f"apiKey:{api_key}&randomKey:{random_key}&signature:{signature}"
    encoded = base64.b64encode(authorization.encode("utf-8")).decode("utf-8")
    return f"IYZWSv2 {encoded}"


def verify_webhook_signature(*, secret_key: str, raw_body: bytes, provided: str) -> None:
    """Webhook imzasını sabit zamanlı doğrular."""
    expected = base64.b64encode(
        hmac.new(secret_key.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("utf-8")
    if not hmac.compare_digest(provided, expected):
        raise WebhookVerificationError("iyzico webhook imzası geçersiz.")


class IyzicoBillingProvider:
    """iyzico abonelik adaptörü — aynı ``BillingProvider`` seam'ine takılır."""

    name = "iyzico"

    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        webhook_secret: str | None,
        plan_reference_codes: Mapping[PlanTier, str],
        callback_url: str,
        sandbox: bool = True,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret
        # Plan kademesi → iyzico'daki ödeme planı referans kodu. Kademeyi
        # sağlayıcıya "pro" diye göndermeyiz; eşleme yapılandırmadan gelir.
        self._plan_codes = dict(plan_reference_codes)
        self._callback_url = callback_url
        self._base_url = SANDBOX_BASE_URL if sandbox else PRODUCTION_BASE_URL
        self._client = client

    async def _post(self, uri_path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body, separators=(",", ":"))
        random_key = _random_key()
        headers = {
            "Authorization": build_authorization(
                api_key=self._api_key,
                secret_key=self._secret_key,
                uri_path=uri_path,
                payload=payload,
                random_key=random_key,
            ),
            "x-iyzi-rnd": random_key,
            "content-type": "application/json",
        }
        url = f"{self._base_url}{uri_path}"
        try:
            if self._client is not None:
                response = await self._client.post(
                    url, content=payload, headers=headers, timeout=_TIMEOUT_SECONDS
                )
            else:
                async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                    response = await client.post(url, content=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise BillingError(f"iyzico'ya ulaşılamadı: {type(exc).__name__}") from exc

        data: Any = response.json()
        if not isinstance(data, dict):
            raise BillingError("iyzico beklenmeyen bir yanıt gövdesi döndürdü.")
        # BAŞARI KONTROLÜ HTTP DURUMUNA GÜVENMEZ — sandbox'a karşı doğrulandı:
        # geçersiz imzada `/payment/bin/check` **HTTP 200** döndürüp gövdede
        # `status:"failure", errorCode:"1000", "Geçersiz imza"` diyor; aynı hata
        # `/v2/subscription/*` uçlarında HTTP 401 ile geliyor. Yalnız HTTP
        # durumuna bakan bir adaptör, geçersiz imzalı yanıtı BAŞARI sayardı.
        if data.get("status") != "success":
            error_code = str(data.get("errorCode", ""))
            hint = ""
            if error_code == _GENERIC_ERROR_CODE and uri_path.startswith("/v2/subscription"):
                # Sandbox'ta doğrulandı: abonelik uçları, gövde ne olursa olsun
                # (hatta boş listeleme isteğinde bile) bu kodu döndürüyor;
                # `/payment/bin/check` ise aynı anahtarlarla 200 veriyor. Yani
                # sorun istekte değil, hesapta abonelik modülünün kapalı
                # olmasında. Bu ipucu olmadan hata "gövde yanlış" sanılır.
                hint = (
                    " — abonelik (Abonelik/Subscription) modülü merchant hesabında "
                    "etkin olmayabilir; bkz. docs/ops/billing-setup.md"
                )
            # Yanıt gövdesinde anahtar YOKTUR (yalnız hata kodu/mesajı); yine de
            # tamamı loglanmaz — sağlayıcı ileride alan eklerse sızıntı olurdu.
            raise BillingError(
                f"iyzico isteği reddetti: {error_code} {data.get('errorMessage')}{hint}"
            )
        return data

    async def create_checkout(
        self, *, tenant_id: uuid.UUID, target_tier: PlanTier
    ) -> CheckoutResult:
        """Abonelik başlatma formunu açar (3DS zorunlu, ödeme iyzico'da).

        Kiracı kimliği sağlayıcı metadata'sına yazılır ve webhook'ta geri gelir;
        böylece olayı kiracıya bağlamak için RLS'siz bir sorgu gerekmez.
        """
        plan_code = self._plan_codes.get(target_tier)
        if plan_code is None:
            raise BillingError(
                f"'{target_tier.value}' için iyzico ödeme planı referans kodu yapılandırılmamış."
            )
        data = await self._post(
            "/v2/subscription/checkoutform/initialize",
            {
                "locale": "tr",
                "conversationId": str(tenant_id),
                "pricingPlanReferenceCode": plan_code,
                "callbackUrl": self._callback_url,
                "subscriptionInitialStatus": "ACTIVE",
            },
        )
        nested = data.get("data")
        payload: dict[str, Any] = nested if isinstance(nested, dict) else data
        return CheckoutResult(
            provider=self.name,
            # Gerçek sağlayıcıda etkinleşme ÖDEME SONRASI webhook'la gelir;
            # burada plan asla anında açılmaz.
            activated=False,
            checkout_url=str(payload.get("checkoutFormContent") or payload.get("token") or ""),
            provider_customer_id=None,
            provider_subscription_id=None,
        )

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        """Aboneliği iptal eder; erişim dönem sonuna kadar sürer (ADR-0014)."""
        await self._post(
            "/v2/subscription/subscriptions/cancel",
            {"locale": "tr", "subscriptionReferenceCode": provider_subscription_id},
        )

    async def change_plan(
        self, *, provider_subscription_id: str, target_tier: PlanTier, immediate: bool
    ) -> None:
        """Plan değiştirir.

        ``immediate=True`` (yükseltme) anında geçerlidir; ``False`` (düşürme)
        dönem sonunda uygulanır. Bu ayrım `/sartlar` §3'teki kuralın koddaki
        karşılığıdır: ödenmiş dönemin ortasında kotayı kısmak, satın alınan
        hizmeti geri almaktır.
        """
        plan_code = self._plan_codes.get(target_tier)
        if plan_code is None:
            raise BillingError(
                f"'{target_tier.value}' için iyzico ödeme planı referans kodu yapılandırılmamış."
            )
        await self._post(
            "/v2/subscription/subscriptions/upgrade",
            {
                "locale": "tr",
                "subscriptionReferenceCode": provider_subscription_id,
                "newPricingPlanReferenceCode": plan_code,
                "upgradePeriod": "NOW" if immediate else "NEXT_PERIOD",
                "useTrial": False,
            },
        )

    async def fetch_subscription(
        self, *, provider_subscription_id: str
    ) -> ProviderSubscriptionState | None:
        """Sağlayıcıdaki güncel abonelik durumunu çeker (mutabakat).

        > Uç yolu ve alan adları **dokümantasyondan** alındı; abonelik modülü
        > kapalı olduğu için gerçek yanıtla doğrulanamadı (bkz.
        > `docs/ops/billing-setup.md`).
        """
        data = await self._post(
            "/v2/subscription/subscriptions/detail",
            {"locale": "tr", "subscriptionReferenceCode": provider_subscription_id},
        )
        nested = data.get("data")
        payload: dict[str, Any] = nested if isinstance(nested, dict) else data
        raw_status = str(payload.get("subscriptionStatus", "")).upper()
        status = _STATUS_MAP.get(raw_status)
        if status is None:
            # Tanınmayan durumu "aktif" saymak ödemesiz erişim demektir.
            raise BillingError(f"Eşlenmemiş iyzico abonelik durumu: '{raw_status}'.")
        return ProviderSubscriptionState(
            status=status,
            plan_tier=self._tier_for_code(str(payload.get("pricingPlanReferenceCode", ""))),
        )

    def parse_webhook(self, *, headers: Mapping[str, str], raw_body: bytes) -> WebhookEvent:
        """İmzayı doğrular ve olayı bizim modelimize çevirir."""
        if not self._webhook_secret:
            raise WebhookVerificationError(
                "iyzico webhook sırrı (BILLING_WEBHOOK_SECRET) yapılandırılmamış."
            )
        provided = headers.get(IYZICO_SIGNATURE_HEADER) or headers.get(
            IYZICO_SIGNATURE_HEADER.title(), ""
        )
        verify_webhook_signature(
            secret_key=self._webhook_secret, raw_body=raw_body, provided=provided
        )
        try:
            data = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            raise WebhookVerificationError("Webhook gövdesi ayrıştırılamadı.") from exc
        if not isinstance(data, dict):
            raise WebhookVerificationError("Webhook gövdesi bir nesne olmalı.")
        return self._to_event(data)

    def _to_event(self, data: dict[str, Any]) -> WebhookEvent:
        raw_status = str(data.get("subscriptionStatus", "")).upper()
        status = _STATUS_MAP.get(raw_status)
        if status is None:
            raise WebhookVerificationError(f"Eşlenmemiş iyzico abonelik durumu: '{raw_status}'.")
        # conversationId checkout'ta kiracı kimliğiyle doldurulur ve imzalı
        # gövdede geri gelir — bu yüzden güvenilirdir.
        raw_tenant = data.get("conversationId")
        try:
            tenant_id = uuid.UUID(str(raw_tenant)) if raw_tenant else None
        except ValueError:
            tenant_id = None
        return WebhookEvent(
            event_id=str(data.get("iyziEventType", "")) + ":" + str(data.get("token", "")),
            event_type=str(data.get("iyziEventType", "")),
            tenant_id=tenant_id,
            plan_tier=self._tier_for_code(str(data.get("pricingPlanReferenceCode", ""))),
            status=status,
            provider_subscription_id=(
                str(data["subscriptionReferenceCode"])
                if data.get("subscriptionReferenceCode")
                else None
            ),
            provider_customer_id=(
                str(data["customerReferenceCode"]) if data.get("customerReferenceCode") else None
            ),
        )

    def _tier_for_code(self, code: str) -> PlanTier | None:
        for tier, plan_code in self._plan_codes.items():
            if plan_code == code:
                return tier
        return None
