# İşlemsel E-posta Kurulumu (Resend)

> **Durum:** kurulum bekliyor · **Son güncelleme:** 2026-07-29
>
> Kod hazır (`EMAIL_PROVIDER=resend`). Bu belge **senin yapman gereken** hesap
> ve DNS adımlarını anlatır. DNS kaydı ekleme işini ben yapmadım: alan adı
> yönetimi geri alınamaz bir dış işlemdir.

## Neden alan adı doğrulaması şart

Doğrulanmamış bir alan adından gönderilen e-posta, alıcı sunucularda "kimliği
belirsiz" sayılır ve **spam klasörüne düşer**. Parola sıfırlama e-postası spam'e
düşen bir üründe, kullanıcı hesabına giremez. Bu yüzden SPF/DKIM/DMARC üçlüsü
opsiyonel bir iyileştirme değil, ürünün çalışma koşuludur.

## Adımlar

1. **Resend hesabı aç** → https://resend.com · *Domains* → *Add Domain* →
   gönderim yapacağın alan adını gir (ör. `tenderiq.com`).

2. **Resend'in verdiği DNS kayıtlarını ekle.** Panel üç kayıt üretir:

   | Tür | Amaç | Not |
   |---|---|---|
   | `TXT` (SPF) | Hangi sunucuların senin adına gönderebileceğini ilan eder | Zaten SPF kaydın varsa **birleştir**, ikinci bir SPF kaydı ekleme — iki SPF kaydı doğrulamayı bozar |
   | `TXT` (DKIM) | Giden e-postayı imzalar | Resend'in verdiği ada birebir ekle |
   | `MX` / `TXT` (dönüş yolu) | Bounce bildirimlerinin dönüş adresi | Alt alan adında olur |

3. **DMARC kaydı ekle** (Resend üretmez, sen eklersin). Başlangıçta gözlem modu:

   ```
   Ad:   _dmarc.<alan-adı>
   Tür:  TXT
   Değer: v=DMARC1; p=none; rua=mailto:dmarc@<alan-adı>; fo=1
   ```

   `p=none` **rapor toplar, hiçbir şeyi engellemez**. 2-4 hafta rapor izledikten
   ve tüm meşru gönderim kaynaklarının hizalandığını gördükten sonra
   `p=quarantine`, ardından `p=reject`e geç. Doğrudan `p=reject` ile başlamak,
   gözden kaçan bir gönderim kaynağının (ör. fatura sistemi) e-postalarını
   sessizce yok eder.

4. **Doğrulamayı bekle** (DNS yayılımı: dakikalar–saatler). Resend panelinde
   alan adı *Verified* olmalı.

5. **Anahtarları ver** — `.env`:

   ```bash
   EMAIL_PROVIDER=resend
   RESEND_API_KEY=re_...
   EMAIL_FROM="TenderIQ <no-reply@<alan-adı>>"
   RESEND_WEBHOOK_SECRET=$(openssl rand -hex 32)
   ```

   `EMAIL_FROM`taki alan adı **doğrulanmış alan adıyla aynı** olmalıdır; aksi
   hâlde Resend gönderimi 422 ile reddeder.

6. **Bounce/şikâyet webhook'unu bağla.** Resend → *Webhooks* → *Add Endpoint*:

   ```
   URL:  https://<api-alan-adı>/api/v1/email/webhook
   Olay: email.bounced, email.complained
   ```

   İmza sırrı `RESEND_WEBHOOK_SECRET` ile aynı olmalıdır. Sır boşken uç
   **404** döner — yapılandırılmamış bir kurulumda ucun varlığı bile sızmaz.

## Doğrulama (kurulumdan sonra)

```bash
# 1. Sağlayıcı ayakta mı: kayıt akışını tetikle, Resend panelinde "Delivered" gör.
# 2. Bastırma listesi çalışıyor mu: Resend'in test bounce adresine gönder
#    (bounced@resend.dev) ve tabloyu kontrol et:
psql -c "SELECT email, reason, created_at FROM email_suppression ORDER BY created_at DESC LIMIT 5;"
```

## Davranış sözleşmesi (kodda sabit)

- **Bastırma listesindeki adrese gönderilmez** — istisna: e-posta doğrulama ve
  parola sıfırlama. Kullanıcıyı bir bounce kaydı yüzünden hesabından kalıcı
  olarak kilitlemek, itibar kaybından ağır bir zarardır.
- **Yumuşak bounce bastırmaz** (kutu dolu / geçici hata): adres geçerlidir.
- **Aynı olay iki kez e-posta üretmez** — ödeme/abonelik mesajları olay
  kimliğiyle anahtarlanır; webhook'lar mükerrer teslim eder.
- **Sağlayıcı hatası çağıranı düşürmez**: kayıt/davet akışları e-postaya bağlı
  değildir, kullanıcı yeniden gönderim isteyebilir.
- **API anahtarı loglara ve istisna metinlerine düşmez** (regresyon testi:
  `test_resend_anahtari_hata_mesajina_sizmaz`).
