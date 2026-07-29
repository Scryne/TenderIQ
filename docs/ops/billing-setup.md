# Ödeme Kurulumu (iyzico)

> **Durum:** sandbox anahtarları çalışıyor, **abonelik modülü kapalı** ·
> **Son güncelleme:** 2026-07-29 · ADR-0014

## Sandbox doğrulamasının bulduğu engel

Sandbox'a karşı koşulan canlı doğrulama (`uv run pytest -m live_sandbox`) şunu
gösterdi:

| Kontrol | Sonuç |
|---|---|
| Kimlik + imza şeması (`/payment/bin/check`) | ✅ 200 `status:success` |
| Yanlış sırla aynı çağrı | ✅ `status:failure` — imza gerçekten doğrulanıyor |
| `/v2/subscription/*` (ürün, plan, checkout) | ❌ `422 errorCode:100001` — gövde ne olursa olsun |

Anahtarlar ve imza doğru olduğuna göre sorun istekte değil: **merchant
hesabında abonelik (Abonelik / Subscription) modülü etkin değil.**

> **Yapılacak (sen):** iyzico paneli veya destek kanalından sandbox merchant
> hesabınız için **abonelik modülünün etkinleştirilmesini** isteyin. Bu bir
> hesap işlemidir; koddan açılamaz.
>
> Etkinleştikten sonra `uv run pytest -m live_sandbox` çalıştırın:
> `test_abonelik_modulunun_durumu_raporlanir` **kırılacaktır** — bu kasıtlıdır
> ve adaptörün istek/yanıt şemasını gerçek yanıta göre doğrulama zamanının
> geldiğini söyler.

## Kurulum adımları (modül etkinleştikten sonra)

1. **Ürün ve ödeme planı oluştur** (panelden veya API ile). Her plan kademesi
   için bir *pricing plan reference code* alırsın.
2. **Eşlemeyi ver** — `.env`:
   ```bash
   IYZICO_PLAN_CODES=pro=<referans-kod>,enterprise=<referans-kod>
   ```
   Kademe adı sağlayıcıya doğrudan gönderilmez; eşleme buradan okunur ve eksikse
   istek reddedilir.
3. **Ortam kapısı** — `BILLING_ENV=sandbox` (varsayılan). Canlıya geçerken
   `BILLING_ENV=live` **ve** `BILLING_LIVE_CONFIRMED=true` gerekir; ikisi birden
   olmadan açılış reddedilir.
4. **Webhook** — iyzico panelinde bildirim adresi:
   `https://<api-alan-adı>/api/v1/billing/webhook`. İmza sırrı
   `BILLING_WEBHOOK_SECRET` ile aynı olmalıdır; sır boşken uç 404 döner.

## Webhook'u yerelde doğrulama

iyzico localhost'a ulaşamaz ve **tünel kurmak bir dış servis/ağ kararıdır**.
Bunun yerine kaydedilmiş bir olay gövdesini imzalayıp uca gönderen tekrar
oynatma betiği kullanılır:

```bash
uv run python scripts/replay_billing_webhook.py --help
```

Tünelle uçtan uca doğrulama istersen (ngrok/cloudflared) tüneli **sen** aç ve
iyzico paneline tünel adresini yaz; bu adım bilinçli olarak otomatikleştirilmedi.

## Doğrulanmış davranış sözleşmesi (koda gömülü)

- **Başarı kontrolü HTTP durumuna GÜVENMEZ.** Sandbox'ta doğrulandı: geçersiz
  imzada `/payment/bin/check` **HTTP 200** döndürüp gövdede
  `status:"failure", errorCode:"1000", "Geçersiz imza"` diyor; aynı hata
  `/v2/subscription/*` uçlarında HTTP 401 ile geliyor. Yalnız HTTP durumuna
  bakan bir adaptör geçersiz imzalı yanıtı başarı sayardı.
- **İmza:** `HMAC-SHA256(secret, randomKey + uriPath + payload)` → hex;
  `base64("apiKey:…&randomKey:…&signature:…")`; başlık `IYZWSv2 <base64>`.
  Payload'ın imzaya dâhil olduğu, payload'sız imzanın 401 almasıyla doğrulandı.
- **Kart verisi bize hiç gelmez**; PAN/CVV iyzico formunda kalır.
- **Non-3DS yol sunulmaz** (ADR-0014).

## Kalan borç

- Abonelik istek/yanıt **şeması hâlâ dokümantasyondan yazılmış varsayımdır**;
  modül etkinleşene kadar doğrulanamaz.
- **Webhook olay gövdesi ve imza biçimi de doğrulanmadı** — gerçek bir olay
  alınamadığı için `IYZICO_SIGNATURE_HEADER` ve imza hesabı dokümandan alındı.
