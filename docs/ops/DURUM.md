# DURUM — çalışma günlüğü

> **Bu dosya bir sonraki oturumun TEK giriş noktasıdır.** Nerede kalındığı,
> sırada ne olduğu ve hangi süreçlerin ayakta bırakıldığı buradan okunur.
> Her madde bitiminde güncellenir.

**Son güncelleme:** 2026-07-29 · **Aktif tur:** Tur 8 — DLQ + abonelik bildirimleri
> Tur 8'in iki maddesi de bitti. Sıradaki iş: **kiracı izolasyonu denetimi**
> (DLQ tablosu eklendi, RLS + sızıntı testi yazıldı — geri kalan tablolar).

---

## Tur 8 — biten

| # | Madde | Durum |
|---|---|---|
| 1 | Ölü mektup kuyruğu + yönetici yeniden işleme ucu + metrik | bitti |
| 2 | Abonelik olaylarında e-posta bildirimi | bitti |

### Webhook yolu kapandı

Doğrulaması geçip uygulanamayan olay artık **kaybolmuyor**:

- `webhook_dead_letter` (migration `0020`): gövde **redakte**, imza durumu,
  hata sebebi/türü, deneme sayısı, durum.
- **Kalıcı** (tanınmayan kiracı, ayrıştırılamayan gövde, geçersiz imza) →
  kuyruk + **400**. **Geçici** → kuyruk + **503** (sağlayıcı yeniden dener),
  `MAX_TRANSIENT_ATTEMPTS`ten sonra **200** (fırtınayı durdur).
- Olay sonunda uygulanırsa kuyruk satırı otomatik **çözülür**.
- `GET /billing/dead-letters` + `POST /billing/dead-letters/{id}/retry` (admin).
  Yeniden işleme **hiçbir korumayı atlamaz**: idempotency ve sırasız-olay
  koruması aynen işler (`duplicate` / `stale` döner, durum değişmez).
- `/ops/metrics` → `dead_letter_pending`. **`null` = ölçülemedi, sıfır DEĞİL** —
  sayaç okunamadığında "kuyruk boş" demek panoyu yanlışlıkla yeşile boyardı.
- Redaksiyon listesi artık log kapısıyla **ortak**
  (`tenderiq_core.redaction.SENSITIVE_FIELDS`); iki liste tutmak, birine
  eklenip diğerine eklenmeyen alanın sızması demekti.

### Bildirimler bağlandı

Altı olay → e-posta: başladı · yenilendi · tahsilat başarısız · askıya alındı ·
iptal edildi (dönem sonu tarihiyle) · iptal geri alındı. Gönderim **commit
sonrası ve işlem dışı**; hata yutulur. Gerekçe: e-posta hatası isteği
düşürseydi sağlayıcı 5xx görür, olayı yeniden gönderir ve abonelik **ikinci kez
uygulanırdı** — bildirim arızası bir yetkilendirme arızasına dönüşürdü. Alıcı
kiracının yöneticileri; tekrar koruması mevcut idempotency anahtarından;
bastırma listesi geçerli.

### Tur 8'in en önemli bulgusu

`replay_billing_webhook.py` yine canlı uçta bir kusur yakaladı — ve bu kez
**entegrasyon testlerinin göremediği** bir kusur.

RLS politikası `tenant_id = current_setting('app.current_tenant', true)::uuid`
yazılmıştı. `current_setting(..., true)` ayar **hiç tanımlanmamışsa** `NULL`
döner; ama aynı bağlantıda daha önce bir istek onu transaction-local olarak
kurduysa, transaction bittikten sonra ayar **boş dizeye** (`''`) döner.
Bağlantı havuzunda bu kaçınılmazdır. `''::uuid` hata fırlatır ve politika
"false" üretmek yerine **sorguyu çökertir** → kimliksiz webhook yolu kuyruğa
hiç yazamıyor, uç 503 dönüyordu. Testler göremedi çünkü testlerdeki taze
bağlantılarda ayar hiç tanımlanmamış oluyor.

Düzeltme: `nullif(current_setting('app.current_tenant', true), '')::uuid`.
Regresyon testi: `test_kiraci_baglami_kullanilmis_baglantida_da_yazilabilir`
(önce kimlikli istekler, sonra kimliksiz webhook — sıra testin kendisi).

> **Diğer tablolar için not.** Mevcut RLS politikalarının hepsi aynı
> `nullif`siz kalıbı kullanıyor. Onlar bugüne kadar patlamadı çünkü **yalnız
> kiracı bağlamı kurulmuşken** sorgulanıyorlar. Kimliksiz bir yoldan
> sorgulanan ilk tablo bu oldu. Yeni bir tabloyu kimliksiz yoldan
> sorgulayacaksan `nullif` şart.

## ÖNCELİK SIRASI (sıradaki turlar)

1. **Kiracı izolasyonu denetimi.** DLQ tablosu RLS + sızıntı testiyle geldi;
   geri kalan tablolar için aynı denetim yapılmalı. Ayrıca yukarıdaki `nullif`
   tuzağı diğer politikalarda da var (bugün zararsız, yarın değil).
2. **Havale/EFT ile manuel aktivasyon yolu** (ADR-0014'te korunmuş kart dışı yol).
3. **Playwright E2E** (kayıt→doğrulama→giriş→panel + bekleme listesi).

## Sonraki turlara ertelenenler (bilerek)

- Havale/EFT ile manuel aktivasyon yolu
- Playwright E2E (kayıt→doğrulama→giriş→panel + bekleme listesi)
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

**Tur 8'de açılan süreçler — HEPSİ KAPATILDI.** Yeni kural uygulandı: açılan her
süreç PID'i `.run/<port>.pid`e yazılarak başlatıldı ve tur sonunda kapatıldı.
`.run/` `.gitignore`dadır.

> **Tur 7'den kalan iki süreç HÂLÂ AYAKTA ve kapatılamıyor.** `:8010` (PID
> 10212) ve `:8011` (PID 22500). Bu PID'ler port dinlemede görünüyor ama
> `taskkill` ve `Stop-Process` "böyle bir süreç yok" diyor — bu oturumdan
> erişilemiyorlar. Görev Yöneticisi'nden kapatın ya da makineyi yeniden
> başlatın. Zararsızlar (Tur 7 kodunu servis eden boşta dev sunucuları) ama
> portları tutuyorlar.
>
> Sebebi kayda geçti: `nohup ... &` ile başlatılan süreçler bu ortamda
> kapatılamıyor; `run_in_background` ile başlatılanlar kapatılabiliyor.

Yerel veritabanı migration'ı: `0020_webhook_dead_letter`.

## Bilinen borç / dikkat

- **`test_auth_account_flow.py`de 8 test KIRIK ve Tur 8'den ÖNCE de kırıktı.**
  `POST /auth/register` yanıtındaki `user` nesnesi `email_verified` alanını
  taşımıyor; testler onu bekliyor (`KeyError: 'email_verified'`). Bu turda
  dokunulmadı — kapsam dışıydı ve sebebi ödeme yolu değil. Doğrulandı:
  değişiklikler `git stash`lenip aynı testler koşulduğunda da 8 hata veriyor.
  Sözleşme mi test mi yanlış, karar verilmeli.
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
- **RLS politikalarında `nullif` tuzağı** (Tur 8 bulgusu): kimliksiz yoldan
  sorgulanacak her tabloda
  `nullif(current_setting('app.current_tenant', true), '')::uuid` kullan.
  `nullif`siz kalıp, bağlantı havuzunda ayar boş dizeye döndüğünde sorguyu
  çökertir. Mevcut diğer tablolar bugün etkilenmiyor (yalnız bağlam kuruluyken
  sorgulanıyorlar) ama kalıp yayılmamalı.
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
