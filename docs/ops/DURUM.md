# DURUM — çalışma günlüğü

> **Bu dosya bir sonraki oturumun TEK giriş noktasıdır.** Nerede kalındığı,
> sırada ne olduğu ve hangi süreçlerin ayakta bırakıldığı buradan okunur.
> Her madde bitiminde güncellenir.

**Son güncelleme:** 2026-07-30 · **Aktif tur:** Tur 9 — RLS süpürmesi + tarayıcı E2E
> Tur 9'un iki maddesi de bitti. **Kırık test kalmadı** (143 entegrasyon + 7 E2E yeşil).
> Sıradaki iş: **havale/EFT ile manuel aktivasyon yolu**.

---

## Tur 9 — biten

| # | Madde | Durum |
|---|---|---|
| 1a | RLS boş-dize kalıbının süpürülmesi (19 politika → tek fonksiyon) | bitti |
| 1b | Kayıt yanıtı sözleşmesi / 8 kırık test | bitti |
| 2 | Playwright E2E + CI job'ı (4 akış) | bitti |

### RLS mayını temizlendi

Tur 8'de tek tabloda bulunan boş-dize tuzağı **17 tabloda daha** duruyordu.
Kanıt üretildi (aynı bağlantı, `tender` tablosu):

```
BEGIN; SELECT set_config('app.current_tenant', '<uuid>', true); COMMIT;
SELECT count(*) FROM tender;   -- ERROR: invalid input syntax for type uuid: ""
```

- **`app_current_tenant()`** (migration `0021`): `nullif(...)` ile tek tanım
  noktası. 19 politikadaki **32 ifade** buna geçirildi; artık hiçbir politikada
  ham `current_setting` yok. Fonksiyon `STABLE`+`PARALLEL SAFE` ve `SET`
  yan tümcesi taşımıyor — planlayıcı satır içi açabiliyor (RLS ifadesi satır
  başına değerlendiği için bu gerçek bir maliyet farkı).
- **Politika çökmüyor, satır döndürmüyor.** "Hata verdi, demek ki güvenli"
  kabul edilmedi: test satır sayısının **sıfır** olduğunu da doğruluyor.

### Testin göremediği kusur artık görülebiliyor

`packages/core/tests/integration/test_rls_no_context.py` — üç kapı:

1. **Davranış:** `QueuePool(pool_size=1)` ile bağlantı GERÇEKTEN yeniden
   kullanılıyor; bağlam kurulup bırakıldıktan sonra **her** RLS tablosu
   sorgulanıyor. Tablo listesi `pg_class`tan türetiliyor → yeni bir RLS tablosu
   eklendiğinde kimse listeyi güncellemese de kapsanıyor.
2. **Yapı:** hiçbir politika ham `current_setting` kullanmamalı.
3. **Sözleşme:** `app_current_tenant()` boş dizede de NULL döndürmeli.

> Mevcut `test_rls_isolation.py` bunu göremezdi ve göremez: `NullPool`
> kullanıyor, yani her oturum **taze bağlantı** alıyor ve ayar hiç
> tanımlanmamış oluyor. Fark tam olarak buradaydı.

**Negatif doğrulama yapıldı:** migration 0021 geçici olarak kaldırılıp testler
koşuldu → 16 tablo `InvalidTextRepresentation` ile çöktü ve yapısal kapı 19
politikayı tek tek adlandırdı. Yani test gerçekten bu kusuru yakalıyor.

### Kayıt sözleşmesi — gerekçe düzeltildi

Madde 1b'nin varsayımı ("`email_verified` sözleşmede yok") **tutmuyordu**: alan
`body["user"]["email_verified"]` altında zaten vardı. Kırık 8 test yanıtı DÜZ
bir kullanıcı nesnesi sanıyordu; zarf (`{status, user, email_delivery}`) bekleme
listesi modunu taşıyor ve **17 test dosyası + frontend + üretilen api-client**
onu kullanıyor. Kullanıcı onayıyla stale test yardımcısı zarfa güncellendi
(1 dosya, 2 satır); uç ve sözleşme dokunulmadan kaldı.

## ÖNCELİK SIRASI (sıradaki turlar)

1. **Havale/EFT ile manuel aktivasyon yolu** (ADR-0014'te korunmuş kart dışı yol).
2. **CSP'yi zorlayıcıya alma** (nonce tabanlı) · **Lighthouse** ölçümü.
3. **Onboarding sihirbazı + demo analiz.**

## Sonraki turlara ertelenenler (bilerek)

- Havale/EFT ile manuel aktivasyon yolu
- CSP'yi zorlayıcıya alma (nonce tabanlı) · Lighthouse ölçümü
- Bounce webhook'u için entegrasyon testi
- `email_suppression` kiracı-dışı kararının ADR'si + sızmama testi
- Onboarding sihirbazı + demo analiz
- J.6 ölçek korkulukları · süresi dolmuş davet temizliği

## Ayakta olan süreçler

| Ne | Port | PID | Kapatma |
|---|---|---|---|
| API — **kullanıcının kendi süreci** | 8000 | 6476 / 18500 | `taskkill //PID 6476 //F` |
| Postgres + Redis konteynerleri | — | — | `docker compose -f infra/compose/docker-compose.yml stop postgres redis` |

**Tur 9'da açılan süreçlerin hepsi kapatıldı.** Playwright `webServer`ları
(:8100/:8101/:3100/:3101) koşu sonunda kendisi kapatıyor.

**Tur 7'den kalan `:3000` dev sunucusu KAPATILDI** (web derlemesi için
gerekliydi; `next build` dev sunucusu ayaktayken `.next`i bozuyor).

> **Tur 7'den kalan iki API süreci HÂLÂ AYAKTA ve kapatılamıyor.** `:8010`
> (PID 10212) ve `:8011` (PID 22500). Bu PID'ler port dinlemede görünüyor ama
> `taskkill`/`Stop-Process` "böyle bir süreç yok" diyor. Görev Yöneticisi'nden
> kapatın ya da makineyi yeniden başlatın. Zararsızlar ama portları tutuyorlar.
>
> Sebep kayda geçti: `nohup ... &` ile başlatılan süreçler bu ortamda
> kapatılamıyor; `run_in_background` ve Playwright `webServer` ile
> başlatılanlar kapatılabiliyor.

Yerel veritabanı migration'ı: `0021_rls_null_safe_tenant`.

## Bilinen borç / dikkat

- **E2E iki yığın kaldırıyor** (:8100/:3100 açık kayıt · :8101/:3101 bekleme
  listesi) çünkü `SIGNUP_MODE` sunucu seviyesinde. CI'da bu ~4 süreç demek;
  yavaşlarsa bekleme listesi projesi ayrı bir job'a alınabilir.
- **E2E oran-sınırı sayaçlarını temizler** (`globalSetup`). Temizlenmezse
  `rl:register:ip:127.0.0.1` birikir ve testler **429 yüzünden gezinme zaman
  aşımıyla** düşer — sebebi hiç ele vermeyen bir arıza (yaşandı: aynı testler
  önce 24 sn yeşil, sonraki koşuda 4,8 dk üç kırmızı).
- **`/_test/inbox` ucu** yalnız `EMAIL_PROVIDER=memory` + production dışında
  yanıt verir, aksi hâlde 404. Ayrıca `memory` sağlayıcısı artık production'da
  açılışta reddediliyor (`logging` gibi) — iki kapı birden aşılmadan uç açılmaz.
- **Tohum betiği artık "istenen duruma getirir"**, "yoksa oluşturur" değil:
  inceleme durumunu sıfırlıyor. Aksi hâlde `review-export` spec'i yalnız ilk
  koşuda geçiyordu (onay kalıcı, onay butonu yalnız incelenmemiş bulguda görünür).
- Hukuki metinler **taslak**; `LEGAL_TODO.md`de 12 zorunlu alan bekliyor.
- Resend'e **gerçek gönderim yapılmadı** (alan adı doğrulanmamış; hesap kullanıcıda).
- iyzico **imza şeması gerçeğe karşı doğrulandı**; abonelik istek/yanıt ŞEMASI
  hâlâ varsayım (modül kapalı, doğrulanamıyor). Tur 7'de eklenen
  `resume_subscription` (`/v2/subscription/subscriptions/activate`) ve dönem sonu
  alanı (`subscriptionNextChargeDate`) de **dokümantasyondan**.
- **Webhook olay gövdesi ve imza biçimi hâlâ doğrulanmadı** — gerçek bir olay
  alınamadı. Ama artık biçim **tek yerde**:
  `packages/core/src/tenderiq_core/billing/signature.py` (`SCHEMES`). Uç ve
  `scripts/replay_billing_webhook.py` aynı tanımı okur; gerçek olay geldiğinde
  düzeltilecek yer tek ve `verified=False` işareti oradadır.
- **iyzico olay TÜRÜ eşlemesi eksik.** `_resolve_target` bizim adlarımızı
  (`subscription.canceled`, `subscription.expired`…) bekliyor; iyzico ham
  `iyziEventType` gönderiyor ve karşılığı bilinmiyor. Gerçek olay geldiğinde
  `iyzico._to_event` içinde eşlenecek.
- ADR-0014'ün **koşulu kayda geçti**: abonelik modülü etkinleştirilemezse karar
  yeniden açılır (ADR §"Koşul").
- Başarı kontrolü HTTP durumuna GÜVENMEZ (sandbox'ta doğrulandı: geçersiz imza
  `/payment/bin/check`te HTTP 200 + gövdede "Geçersiz imza" ile geliyor).
- `BILLING_ENV=live` ikinci onay bayrağı ister; üretim tabanına çağrı hâlâ
  durma koşulu.
- Testler dış servise çıkmamalı: `conftest`te `EMAIL_PROVIDER=memory` ve
  `billing_client`ta `BILLING_PROVIDER=manual` sabitlenmiş durumda. Yeni sağlayıcı
  eklerken aynı kalıbı uygula.
- **RLS kiracı ifadesi ARTIK TEK YERDE** (Tur 9): yeni politika yazarken
  `tenant_id = app_current_tenant()` kullan, ham `current_setting` YAZMA.
  `test_rls_no_context.py` yapısal kapısı sapmayı CI'da yakalar.
- **Ölü mektup kuyruğunun kiracıya görünen kısmı pratikte seyrek dolar.**
  Kalıcı hataların çoğu (tanınmayan kiracı, ayrıştırılamayan gövde) tanımı
  gereği bir kiracıya atfedilemez ve yalnız operatöre görünür. Kiracının
  listesinde çoğunlukla geçici altyapı hataları görünür. Bu bilinçlidir:
  atfedemediğimiz bir ödemeyi rastgele bir kiracıya göstermek sızıntı olurdu.
- Webhook testlerinde **sabit olay kimliği kullanma** — dedup anahtarı Redis'te
  kalıcıdır, ikinci koşuda test yanlış şeyi ölçer.
- **Dönem sonu görevi bir YEDEKTİR**, kaynak değil. Normalde dönem bitişini
  sağlayıcının olayı bildirir; `apply_due_subscription_changes` (saatlik) olay
  hiç gelmezse iptali/düşürmeyi uygular. Sağlayıcıya çıkmaz, bu yüzden sağlayıcı
  kesintisinde yanlış kapatma üretemez.
- **Ortam tuzağı (yeniden doğrulandı).** Windows'ta `uvicorn --reload` olmadan
  psycopg `ProactorEventLoop` hatası veriyor. Ayrıca OneDrive altında
  watchfiles reload'ı bazen **eski bytecode'u servis etmeye devam ediyor**:
  düzeltme uygulanmış görünüp uçta eski davranış sürüyorsa süreci yeniden başlat
  (Tur 7'de bir kez bu yüzden yanlış teşhis kondu).
