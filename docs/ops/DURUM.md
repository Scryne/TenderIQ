# DURUM — çalışma günlüğü

> **Bu dosya bir sonraki oturumun TEK giriş noktasıdır.** Nerede kalındığı,
> sırada ne olduğu ve hangi süreçlerin ayakta bırakıldığı buradan okunur.
> Her madde bitiminde güncellenir.

**Son güncelleme:** 2026-07-29 · **Aktif tur:** Tur 6 — canlı doğrulama + mutabakat
> Tur 6'nın iki maddesi de bitti. Sıradaki iş: **iptal/plan değişimi uçları
> (yayın engeli)**.

---

## Tur 6 — biten

| # | Madde | Commit |
|---|---|---|
| 1 | Canlı sandbox doğrulaması (imza doğrulandı, abonelik modülü kapalı çıktı) | `1ec038b` |
| 1 | live_sandbox testinde import sırası | `fff1e1f` |
| 2 | Abonelik mutabakat görevi (kritik yol) | `3d5d92a` |

### Tur 6'nın en önemli bulgusu

`/payment/bin/check` aynı anahtarlarla **200 success** dönüyor → kimlik, imza
şeması ve taban adres DOĞRU. Ama `/v2/subscription/*` uçlarının hiçbiri
çalışmıyor (`422 errorCode:100001`, gövdeden bağımsız) → **merchant hesabında
abonelik modülü etkin değil.** Bu bir hesap işlemi; adımlar
`docs/ops/billing-setup.md`de. Modül açılınca
`test_abonelik_modulunun_durumu_raporlanir` KIRILACAK — kasıtlı; şemayı gerçeğe
göre doğrulama zamanının geldiğini söyler.

## ÖNCELİK SIRASI (sıradaki turlar)

1. **İptal + plan değişimi uçları — YAYIN ENGELİ.** Seam'de var, API'ye
   bağlanmadı. `/sartlar` 14 gün koşulsuz cayma taahhüt ediyor; kullanıcının
   kendi iptal edebildiği yol olmadan GA yok.
2. **DLQ + yönetici yeniden işleme ucu.** Doğrulaması geçip uygulanamayan olay
   şu an kayboluyor.
3. **Olay başına e-posta bildirimi.** Şablonlar `email/templates.py`de hazır;
   webhook işleyicisine bağlanacak.
4. **Kiracı izolasyonu** — DLQ tablosu eklendiğinde RLS + sızıntı testi.

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
- iyzico **imza şeması gerçeğe karşı doğrulandı**; abonelik istek/yanıt ŞEMASI
  hâlâ varsayım (modül kapalı, doğrulanamıyor).
- **Webhook olay gövdesi ve imza biçimi doğrulanmadı** — gerçek bir olay
  alınamadığı için `IYZICO_SIGNATURE_HEADER` ve imza hesabı dokümandan alındı.
  `scripts/replay_billing_webhook.py` **yazılmadı** (Tur 6'da sıra gelmedi).
- Başarı kontrolü HTTP durumuna GÜVENMEZ (sandbox'ta doğrulandı: geçersiz imza
  `/payment/bin/check`te HTTP 200 + gövdede "Geçersiz imza" ile geliyor).
- `BILLING_ENV=live` ikinci onay bayrağı ister; üretim tabanına çağrı hâlâ
  durma koşulu.
- Testler dış servise çıkmamalı: `conftest`te `EMAIL_PROVIDER=memory` ve
  `billing_client`ta `BILLING_PROVIDER=manual` sabitlenmiş durumda. Yeni sağlayıcı
  eklerken aynı kalıbı uygula.
- Webhook testlerinde **sabit olay kimliği kullanma** — dedup anahtarı Redis'te
  kalıcıdır, ikinci koşuda test yanlış şeyi ölçer.
