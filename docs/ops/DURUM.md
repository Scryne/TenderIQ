# DURUM — çalışma günlüğü

> **Bu dosya bir sonraki oturumun TEK giriş noktasıdır.** Nerede kalındığı,
> sırada ne olduğu ve hangi süreçlerin ayakta bırakıldığı buradan okunur.
> Her madde bitiminde güncellenir.

**Son güncelleme:** 2026-07-29 · **Aktif tur:** Tur 5 — webhook + canlı sandbox
> Tur 5'te madde 0 ve madde 1'in imza/sıra kısmı bitti. **Canlı sandbox'a hiç
> çağrı yapılmadı** ve mutabakat görevi (kritik yol) başlanmadı.

---

## Tur 5 — biten

| # | Madde | Commit |
|---|---|---|
| 0 | Anahtar hijyeni denetimi + `BILLING_ENV` kapısı + `live_sandbox` işareti | `6e86049` |
| 1a | Sırasız webhook teslimine karşı olay zaman damgası | `f5539d9` |

## Tur 5 — SIRADA (yarım kalanlar)

**Madde 1'in kalanı — webhook sertleştirme**
- Ölü mektup kuyruğu (tablo + model + migration) ve **yönetici için yeniden
  işleme ucu**. Şu an doğrulaması geçen ama uygulanamayan olay kayboluyor.
- İmza/idempotency/eski-olay koruması TAMAM; yalnız DLQ eksik.

**Madde 2 — mutabakat görevi (KRİTİK YOL, başlanmadı)**
Checkout `activated=False` bıraktığı için erişimi açan **tek** mekanizma webhook.
Webhook hiç gelmezse "ödeme alındı ama erişim açılmadı" hâli sessizce sürer.
Yapılacak: sağlayıcıdaki abonelik durumunu periyodik çekip bizdeki
yetkilendirmeyi düzelten iş + sapmayı metrik/log olarak raporlama.

**Madde 3 — olay başına e-posta bildirimi (başlanmadı)**
Tur 2'nin servisinden: abonelik başladı · yenilendi · tahsilat başarısız ·
askıya alındı · iptal edildi. Şablonlar `email/templates.py`de HAZIR
(`payment_succeeded`, `payment_failed`, `subscription_canceled`), yalnız
webhook işleyicisine bağlanmaları gerekiyor.

**Madde 4 — kiracı izolasyonu (başlanmadı)**
Bu turda yeni kiracı-özel TABLO eklenmedi (yalnız `subscription.last_event_at`
kolonu); DLQ tablosu eklendiğinde RLS + sızıntı testi gerekecek.

**Madde 5 — canlı sandbox doğrulaması (BAŞLANMADI)**
Sandbox anahtarları `.env`de mevcut ama **hiçbir gerçek çağrı yapılmadı**.
Yapılacak: checkout başlatma → 3DS test kartı → dönen yanıt; dokümandan yazılan
imza şeması/uç yolları/alan adları ile gerçek yanıt arasındaki farkları raporla
ve adaptörü düzelt; gerçek gövdeleri (temizlenmiş) sabit test verisi yap;
`scripts/replay_billing_webhook.py` ile imzalı tekrar oynatma.

**Yayın engeli (işaretlendi):** iptal ve plan değişimi seam'de var ama API
ucuna BAĞLANMADI. `/sartlar` 14 gün koşulsuz cayma taahhüt ediyor; kullanıcının
kendi iptal edebildiği yol olmadan GA yok.

## Sonraki turlara ertelenenler (bilerek)

- Havale/EFT ile manuel aktivasyon yolu
- Playwright E2E (kayıt→doğrulama→giriş→panel + bekleme listesi)
- CSP'yi zorlayıcıya alma (nonce tabanlı) · Lighthouse ölçümü
- Bounce webhook'u için entegrasyon testi
- `email_suppression` kiracı-dışı kararının ADR'si + sızmama testi
- Onboarding sihirbazı + demo analiz
- J.6 ölçek korkulukları · süresi dolmuş davet temizliği

## Ayakta olan süreçler

| Ne | Kapatma |
|---|---|
| API (uvicorn, :8000) | `taskkill //PID 6476 //F` |
| Postgres + Redis konteynerleri | `docker compose -f infra/compose/docker-compose.yml stop postgres redis` |

Yerel veritabanı migration'ı: `0018_subscription_last_event`.

## Bilinen borç / dikkat

- Hukuki metinler **taslak**; `LEGAL_TODO.md`de 12 zorunlu alan bekliyor.
- Resend'e **gerçek gönderim yapılmadı** (alan adı doğrulanmamış; hesap kullanıcıda).
- iyzico adaptörü **gerçek sandbox'a karşı hâlâ koşulmadı** (anahtarlar .env'de
  mevcut ama Tur 5'te sıra gelmedi). İmza şeması, uç yolları ve alan adları
  DOKÜMANTASYONDAN yazıldı — gerçek yanıtla doğrulanana kadar hepsi varsayım.
- `BILLING_ENV=live` ikinci onay bayrağı ister; üretim tabanına çağrı hâlâ
  durma koşulu.
- Testler dış servise çıkmamalı: `conftest`te `EMAIL_PROVIDER=memory` ve
  `billing_client`ta `BILLING_PROVIDER=manual` sabitlenmiş durumda. Yeni sağlayıcı
  eklerken aynı kalıbı uygula.
- Webhook testlerinde **sabit olay kimliği kullanma** — dedup anahtarı Redis'te
  kalıcıdır, ikinci koşuda test yanlış şeyi ölçer.
