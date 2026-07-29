# DURUM — çalışma günlüğü

> **Bu dosya bir sonraki oturumun TEK giriş noktasıdır.** Nerede kalındığı,
> sırada ne olduğu ve hangi süreçlerin ayakta bırakıldığı buradan okunur.
> Her madde bitiminde güncellenir.

**Son güncelleme:** 2026-07-29 · **Aktif tur:** Tur 4 — iyzico adaptörü + webhook

---

## Bu turda biten

| # | Madde | Commit |
|---|---|---|
| 0 | Kalıcı bounce'ta otomatik yeniden deneme kaldırıldı | `6d002ae` |

## Sırada (bu tur)

1. **`PaymentProvider` — iyzico implementasyonu** (turun ana işi): seam'i doldur,
   sahte sağlayıcı + sözleşme testleri, `conftest`'te sahte sağlayıcıya sabitle,
   abonelik oluştur/iptal/yükselt/düşür.
2. **Webhook sertleştirme**: sıra dışı olay dayanıklılığı (zaman damgası),
   ölü mektup kuyruğu + yeniden işleme ucu (admin), her olayda e-posta bildirimi,
   yetkilendirme mutabakat kontrolü.
3. **Kiracı izolasyonu**: yeni abonelik/ödeme tablolarında RLS + sızıntı testleri.

## Sonraki turlara ertelenenler (bilerek)

- Havale/EFT ile manuel aktivasyon yolu
- Playwright E2E (kayıt→doğrulama→giriş→panel + bekleme listesi)
- CSP'yi zorlayıcıya alma (nonce tabanlı)
- Lighthouse erişilebilirlik ölçümü
- Bounce webhook'u için **entegrasyon** testi
- `email_suppression` kiracı-dışı kararının ADR'si + kiracıya sızmama testi
- Onboarding sihirbazı + demo analiz
- J.6 ölçek korkulukları (LLM bütçe tavanı, kuyruk adaleti, depolama kotası)
- Süresi dolmuş davet temizliği

## Ayakta olan süreçler

| Ne | Kapatma |
|---|---|
| API (uvicorn, :8000) | `taskkill //PID 6476 //F` |
| Postgres + Redis konteynerleri | `docker compose -f infra/compose/docker-compose.yml stop postgres redis` |

Yerel veritabanı migration'ı: `0017_email_suppression`.

## Bilinen borç / dikkat

- Hukuki metinler **taslak**; `LEGAL_TODO.md`de 12 zorunlu alan bekliyor.
- Resend'e **gerçek gönderim yapılmadı** (alan adı doğrulanmamış; hesap kullanıcıda).
- Testler dış servise çıkmamalı: `conftest`te `EMAIL_PROVIDER=memory` ve
  `billing_client`ta `BILLING_PROVIDER=manual` sabitlenmiş durumda. Yeni sağlayıcı
  eklerken aynı kalıbı uygula.
- Webhook testlerinde **sabit olay kimliği kullanma** — dedup anahtarı Redis'te
  kalıcıdır, ikinci koşuda test yanlış şeyi ölçer.
