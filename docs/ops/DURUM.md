# DURUM — proje durumu

> **Bu dosya bir sonraki oturumun TEK giriş noktasıdır.**
>
> **Neye güvenebilirsin, neyi kendin ölçmelisin.** Bölüm 1'deki *kalıcı
> gerçeklere* güven: commit'ler, alınan kararlar, bilinen borç ve tuzaklar —
> bunlar zamanla yanlışa dönüşmez. Bölüm 3'teki *doğrulama durumu* bir
> zaman damgasıdır, bir garanti değil: "testler yeşil" ifadesinin tek geçerli
> kaynağı CI koşumudur, bu dosya değil. **Ayakta olan süreçlerin listesi burada
> TUTULMAZ** — süreçler durum değildir, her yeniden başlatmada bu dosyayı
> yalancı yaparlar; ne bıraktığı yalnız ilgili turun raporunda yazar. Kod
> yapısını, geçmiş düzeltmeleri ve dosya düzenini buradan değil repodan ve git
> geçmişinden oku.
>
> Kural: **ölçüme dayalı her ifade tarih + "nasıl ölçüldü" taşır**, yoksa
> yazılmaz.

---

## 1. Kalıcı gerçekler

### 1.1 Biten turlar

| Tur | Ne yapıldı | Commit |
|---|---|---|
| 4 | Kalıcı bounce'ta otomatik yeniden deneme kaldırıldı | `6d002ae` |
| 4 | iyzico abonelik adaptörü + sahte sağlayıcı | `e46f90b` |
| 4 | `InvoiceProvider` seam'i + ödeme yolunda sızıntı/sır testleri | `ad05538` |
| 5 | Ödeme ortamı kapısı + anahtar hijyeni | `6e86049` |
| 5 | Sırasız webhook teslimine karşı olay zaman damgası | `f5539d9` |
| 5 | iyzico sandbox'ına canlı doğrulama (imza doğru, abonelik modülü kapalı) | `1ec038b` |
| 6 | Abonelik mutabakat görevi — kayıp webhook'un yedeği | `3d5d92a` |
| 7 | İptal + plan değişimi uçları, webhook tekrar oynatma betiği | `774af94` |
| 8 | Ölü mektup kuyruğu + abonelik bildirimleri | `43dbfcf` |
| 9 | RLS kiracı ifadesi tek null-safe fonksiyona indirildi + Playwright E2E | `9d0287b` |
| 10 | Tur 9'un taze doğrulaması · DURUM.md yeniden yapılandırıldı · zorlayıcı nonce CSP · Lighthouse a11y · ADR-0015 + sızıntı testi · bounce webhook testi (**rota bağlanmamış kusuru bulundu**) | `1eae36c` |
| 14 | J.6 madde 2: LLM bütçe TAVANI (Redis rezervasyonu · sert ret · yumuşak eşik bildirimi) | `HEAD` |
| 13 | J.6 madde 1: LLM kullanım/maliyet ÖLÇÜMÜ (tracer sarmalama · `llm_usage` RLS · fiyat tablosu yapılandırmadan) | `42e2138` |
| 12 | Derleme-zamanı yapılandırma manifestosu + üç kapı (derleme · açılış · dağıtım-dosyası denetimi) | `0067e70` |
| 11 | CI yeşile alındı (gitleaks + mypy) · bağlanmamış artefakt denetimi (router/beat/webhook/adaptör) · dinamik rotalar Lighthouse'a girdi · performans tabanı · Lighthouse CI job'ı · **CSP'nin öldürdüğü doküman tuvali bulundu** | `e77ee20`…`61a0274` |

Ayrıntılı gerekçeler commit gövdelerindedir (`git show <hash>`); buraya
kopyalanmaz.

### 1.2 Kararlar ve değişmezler

- **RLS kiracı ifadesi TEK YERDE.** Yeni politika yazarken
  `tenant_id = app_current_tenant()` kullan; ham `current_setting` YAZMA.
  Fonksiyon migration `0021`'de tanımlı, `nullif(..., '')` ile boş dizeyi NULL'a
  çevirir (fail-closed: çökmez, satır döndürmez). `STABLE` + `PARALLEL SAFE` ve
  gövdesinde `SET` yok — planlayıcı satır içi açabilsin diye (RLS ifadesi satır
  başına değerlendirilir). `test_rls_no_context.py`'nin yapısal kapısı kalıptan
  sapmayı yakalar.
- **RLS yalnız kiracı-kapsamlı tablolarda açıktır.** `organization`,
  `membership`, `user_account`, `invitation`, `waitlist_entry` ve
  `email_suppression` tablolarında RLS KAPALIDIR; izolasyon uygulama
  katmanındadır (ADR-0003).
- **`email_suppression` kiracı-dışıdır — ADR-0015.** Gerekçe: korunan kaynak
  (gönderen alan adının itibarı) tüm kiracılar için ortaktır. Bedeli tek kuralla
  sınırlı: **hiçbir uç bir adresin listede olup olmadığını göstermez**; tek
  istisna çağıranın kendi kaydolduğu adres (`POST /auth/register` →
  `email_delivery`). Davet/üyelik uçları gönderim sonucunu ATAR.
  `test_email_suppression_leak.py` bunu kilitler.
- **Web ortam değişkenlerinin TEK KAYNAĞI `apps/web/env-manifest.json`.**
  Her girdi "hangi katmanda okunuyor / derleme mi çalışma anı mı / eksikse ne
  kırılır" bilgisini taşır; okunur özeti `docs/ops/yapilandirma.md`. Üç kapı
  (Tur 12): **derleme** (`next.config.ts` → `assertBuildTimeEnv`, yalnız
  `PHASE_PRODUCTION_BUILD`ta), **açılış** (`instrumentation.ts` →
  `assertRuntimeEnv`) ve **dağıtım-dosyası denetimi**
  (`test_yapilandirma_denetimi.py`: `.env.example` · compose build arg ·
  Dockerfile `ARG` · CI job env — dördünden biri eksikse kırılır; ayrıca kodda
  okunup manifestoya yazılmamış değişken bırakmaz).
- **`NEXT_PUBLIC_STORAGE_ORIGIN` DOLDURULMAK ZORUNDA** ve **derleme anında**
  verilir. Boş kalırsa zorlayıcı CSP `connect-src`i aynı-origin'e kilitler,
  tarayıcı imzalı PDF URL'ini çekemez ve **doküman tuvali sessizce boş kalır**.
  Çalışma anı değişkeni İŞE YARAMAZ: middleware edge runtime'da koşuyor ve
  `process.env` orada derleme sırasında sabite çevriliyor. Artık production
  derlemesi bu değişken olmadan DÜŞER.
- **Next yalnız STATİK `process.env.SABIT` erişimini gömer.** `process.env[ad]`
  (dinamik) derlenmiş imajda değeri göremez — doğrulamayı dinamik erişimle
  yazmak doğru yapılandırılmış kurulumu bile "eksik" sanır. `config/env.ts`
  bu yüzden değişken başına açık okuyucu tutar; okuyucusu olmayan bir manifesto
  girdisi `e2e/csp-policy.spec.ts`i kırar.
- **LLM bütçe TAVANI var** (J.6 madde 2, Tur 14). Plan bazlı
  `llm_budget_try_per_month`; ücretsizde 25 TL, Pro'da 500 TL, kurumsalda
  sınırsız (tavan sözleşmeyle). **Sert tavan REDDEDER** — küçük modele düşme,
  kısaltma, kısmi sonuç yok. Kabul kontrolü faz BAŞLAMADAN yapılır; işin
  ortasında aşım olursa iş BİTİRİLİR (token zaten harcandı; kesmek parayı geri
  getirmez, yalnız yarım analiz bırakır).
  **Yarış koruması Redis rezervasyonu** (`llm:reserved:{tenant}:{dönem}`, Lua ile
  atomik): harcama iş bitince yazıldığı için yalnız "harcanan < tavan" bakmak
  eşzamanlı işleri birlikte geçirirdi. Her rezervasyon kendi son kullanma
  damgasını taşır — çöken worker kiracıyı kendi tavanına KİLİTLEMEZ.
  **Redis kesintisinde muhafazakâr DB kontrolüne düşülür** (tek rezervasyon
  varmış gibi; sınır erken kapanır) ve `ops`ta `llm_budget_degraded` sayılır —
  "sessizce geç" seçenek değildi. Fiilî kabul sınırı `tavan − rezervasyon`;
  son kısmi dilim bilinçli olarak verilmez.
- **LLM maliyeti ÖLÇÜLÜYOR** (J.6 madde 1, Tur 13): `create_llm_tracer` çıktısı
  `CostTracer` ile sarmalanır — Langfuse yolu bozulmaz, ajan katmanına
  dokunulmaz. Ölçüm LLM çağrısını BLOKE ETMEZ: contextvar tamponuna yazılır,
  worker faz sonunda `llm_usage`a (RLS) tek transaction'da boşaltır. Yazma
  `finally` içinde — iş yarıda düşse bile token'lar harcanmıştır ve faturaya
  girer. Fiyat tablosu `config/llm-pricing.json` (yapılandırma; kodda rakam
  yok). **0 TL dört ayrı şey demektir ve dördü ayrı işaretlenir**
  (`priced` / `unverified` / `unknown_model` / `no_fx_rate`); toplam yalnız
  ilk ikisini sayar, hesaplanamayanlar ayrıca raporlanır. Kayıp kayıt
  `ops` metriğine düşer (`llm_usage_lost`) — "harcama düşük" ile "kayıt
  kayboluyor" ayırt edilebilsin diye. **Tavan HENÜZ YOK** (madde 2).
- **Bağlanmamış artefakt denetimi var** (Tur 11): `apps/api/tests/test_baglanti_denetimi.py`
  (her router erişilebilir · webhook'lar erişilebilir · "rota yok" ≠ "sır yok" ·
  her sağlayıcı adaptörü fabrikaya bağlı) ve `apps/worker/tests/test_beat_denetimi.py`
  (periyodik task zamanlanmış · beat girişi var olan task'a işaret ediyor ·
  periyotlar makul). Kasıtlı istisnalar o dosyalardaki sözlüklerde **gerekçesiyle**
  durur. Yeni router/task/adaptör eklerken kayıt adımını atlamak artık test kırar.
- **İçerik Güvenlik Politikası ZORLAYICI ve nonce tabanlıdır** (Tur 10).
  Tanım `apps/web/src/lib/security/csp.ts`, yayın `middleware.ts`; ihlaller
  `/api/csp-report`ta toplanır. `script-src`e `'unsafe-inline'` EKLEME — nonce'un
  tüm değerini iptal eder; `e2e/csp.spec.ts` bunu CI'da yakalar. Nonce istek
  başına değiştiği için kök layout `headers()` okur ve **tüm rotalar dinamik
  render'dadır** (bilinçli ödün; bedeli Tur 11'de ölçüldü → ortanca TTFB +6 ms,
  performans skoru değişmedi, bkz. `docs/ops/lighthouse-erisilebilirlik.md`).
- **`style-src 'unsafe-inline'` KALICI borçtur — sebebi ölçüldü (Tur 11).**
  Eski gerekçe ("Next kritik CSS'i satır içi gömüyor") yanlıştı: sunucu HTML'inde
  hiç satır içi `<style>` yok. Gerçek sebep **`sonner`** (toast, 2.0.7): çalışma
  anında `document.head`e 14,8 KB'lık nonce'suz bir `<style>` bloğu ekliyor,
  paket nonce kabul etmiyor, ayrı `dist/styles.css`i import etmek enjeksiyonu
  durdurmuyor, hash tabanlı izin de her sürümde kırılır. Sıkılaştırma denendi
  (`style-src 'self'` + `style-src-attr 'unsafe-inline'`) ve her sayfada üç
  `style-src-elem` ihlali üretti. Kalan risk stil enjeksiyonuyla sınırlı
  (tıklama hedefi kaydırma, `background-image` ile sızdırma); **betik yolu
  kapalı** çünkü `script-src` nonce'lu. sonner nonce desteklerse ikili yönergeye
  geçilir. Uğraşmayı bırak.
- **`webhook_dead_letter` yazma politikaları koşulsuzdur** (`service_insert`,
  `service_update` → `true`); kimliksiz webhook yolu kuyruğa yazabilmek
  zorundadır. Okuma tarafı kiracıyla süzülür.
- `audit_log` **append-only**: yalnız SELECT + INSERT politikası tanımlıdır,
  UPDATE/DELETE politikası bilinçli olarak YOKTUR. Politikalara dokunan her
  migration bunu korumak zorundadır.
- **Abonelik yetkilendirmesini açan tek mekanizma webhook'tur** (ADR-0014).
  ADR'nin koşulu kayda geçti: abonelik modülü etkinleştirilemezse karar yeniden
  açılır (ADR §"Koşul").
- **Dönem sonu görevi bir YEDEKTİR**, kaynak değil. Normalde dönem bitişini
  sağlayıcının olayı bildirir; `apply_due_subscription_changes` (saatlik) olay
  hiç gelmezse iptali/düşürmeyi uygular. Sağlayıcıya çıkmaz, bu yüzden sağlayıcı
  kesintisinde yanlış kapatma üretemez.
- **Webhook imza biçimi tek yerdedir:**
  `packages/core/src/tenderiq_core/billing/signature.py` (`SCHEMES`). Uç ve
  `scripts/replay_billing_webhook.py` aynı tanımı okur.
- **Testler dış servise çıkmaz.** `conftest`te `EMAIL_PROVIDER=memory`,
  `billing_client`ta `BILLING_PROVIDER` sabitlenmiş; Playwright
  yapılandırmasında `EMAIL_PROVIDER=memory` + `BILLING_PROVIDER=fake` sabit.
  Yeni sağlayıcı eklerken aynı kalıbı uygula.
- **Ölü mektup kuyruğunun kiracıya görünen kısmı seyrek dolar** ve bu
  bilinçlidir: kalıcı hataların çoğu (tanınmayan kiracı, ayrıştırılamayan gövde)
  tanımı gereği bir kiracıya atfedilemez, yalnız operatöre görünür. Atfedemediğimiz
  bir ödemeyi rastgele bir kiracıya göstermek sızıntı olurdu.

### 1.3 Doğrulanmamış varsayımlar (yayın engeli olabilir)

- **iyzico abonelik istek/yanıt ŞEMASI varsayım.** İmza şeması gerçeğe karşı
  doğrulandı; şema doğrulanamıyor çünkü modül hesapta kapalı. Tur 7'de eklenen
  `resume_subscription` (`/v2/subscription/subscriptions/activate`) ve dönem sonu
  alanı (`subscriptionNextChargeDate`) **dokümantasyondan** alındı.
- **Webhook olay gövdesi ve imza biçimi gerçek bir olayla doğrulanmadı.**
  Düzeltilecek yer tek: `SCHEMES` (`verified=False` işareti oradadır).
- **iyzico olay TÜRÜ eşlemesi eksik.** `_resolve_target` bizim adlarımızı
  (`subscription.canceled`, `subscription.expired`…) bekliyor; iyzico ham
  `iyziEventType` gönderiyor ve karşılığı bilinmiyor. Gerçek olay geldiğinde
  `iyzico._to_event` içinde eşlenecek.
- **Resend'e gerçek gönderim yapılmadı** (alan adı doğrulanmamış; hesap
  kullanıcıda).
- Hukuki metinler **taslak**; `LEGAL_TODO.md`de 12 zorunlu alan bekliyor.
- Başarı kontrolü HTTP durumuna GÜVENMEZ — sandbox'ta doğrulandı: geçersiz imza
  `/payment/bin/check`te HTTP 200 + gövdede "Geçersiz imza" ile geliyor.
- `BILLING_ENV=live` ikinci onay bayrağı ister; üretim tabanına çağrı **durma
  koşulu**.

### 1.4 Tuzaklar (yeniden yaşanmasın)

- **Windows'ta `uvicorn --reload` olmadan koşmayın.** Reload'suz
  `ProactorEventLoop` kullanılıyor ve async psycopg onunla çalışmıyor: her DB
  isteği 500 verir, oran sınırlayıcı bunu "çok fazla deneme" 429'una çevirir ve
  sebep hiç görünmez.
- **OneDrive altında watchfiles reload bazen eski bytecode'u servis etmeye devam
  ediyor.** Düzeltme uygulanmış görünüp uçta eski davranış sürüyorsa süreci
  yeniden başlat (Tur 7'de bir kez bu yüzden yanlış teşhis kondu).
- **`nohup ... &` ile başlatılan süreçler bu ortamda kapatılamıyor**; port
  dinlemede görünürler ama `taskkill`/`Stop-Process` "böyle bir süreç yok" der.
  `run_in_background` ve Playwright `webServer` ile başlatılanlar kapatılabiliyor.
- **`next build`, dev sunucusu ayaktayken çalıştırılmaz** — `.next` bozulur, site
  chunk 404'leriyle düşer.
- **E2E iki yığın kaldırır** (:8100/:3100 açık kayıt · :8101/:3101 bekleme
  listesi) çünkü `SIGNUP_MODE` sunucu seviyesindedir. Modu istemciden taklit
  etmek, sınanmak istenen şeyi (sunucunun kararını) atlardı.
- **E2E oran-sınırı sayaçlarını temizler** (`globalSetup`). Temizlenmezse
  `rl:register:ip:127.0.0.1` birikir ve testler **429 yüzünden gezinme zaman
  aşımıyla** düşer — sebebini hiç ele vermeyen bir arıza.
- **Tohum betiği "istenen duruma getirir"**, "yoksa oluşturur" değil: inceleme
  durumunu sıfırlar. Aksi hâlde `review-export` spec'i yalnız ilk koşuda geçer
  (onay kalıcı, onay butonu yalnız incelenmemiş bulguda görünür).
- **`/_test/inbox` ucu** yalnız `EMAIL_PROVIDER=memory` + production dışında
  yanıt verir; ayrıca `memory` sağlayıcısı production'da açılışta reddedilir.
- **Webhook testlerinde sabit olay kimliği kullanma** — dedup anahtarı Redis'te
  kalıcıdır, ikinci koşuda test yanlış şeyi ölçer.
- **SQL'de `LIKE '%..._...%'` ile kalıp arama yapma.** `_` LIKE'ta JOKERDİR:
  `'%app_current_tenant%'` metindeki `app.current_tenant` dizesini de yakalar ve
  hem yanlış kırmızı hem yanlış yeşil üretir. `strpos(...) > 0` kullan. (Tur
  10'da bir doğrulama betiğinde yaşandı; repo kodunda `LIKE` kullanımı yok.)
- **Yeni bir router yazdıktan sonra `routers/v1/__init__.py`ye EKLEMEYİ unutma.**
  Tur 10'da bulundu: bounce webhook'u Tur 2'den beri kayıtlı değildi, yani
  sağlayıcının her bildirimi 404 alıyor ve hiçbir adres bastırılmıyordu. Sessiz
  kaldı çünkü uç kimliksizdir ve **404, sır yapılandırılmamış kurulumun BEKLENEN
  yanıtıdır** — "rota yok" ile "sır yok" ayırt edilemiyordu. Testte durum kodunu
  değil GÖVDEDEKİ mesajı doğrula.
- **Windows'ta `chrome-launcher`ın çıkış koduna güvenme.** Lighthouse raporu
  yazdıktan SONRA geçici profil klasörünü silerken `EPERM` alıp süreç 1 ile
  çıkıyor; ölçüm başarılıdır. Kararı rapor dosyasının varlığı verir
  (`scripts/lighthouse-a11y.mjs` bunu böyle yapıyor).
- **Git Bash argümanı `/x` biçimindeyse Windows yoluna çevirir.**
  `--only /tenders` → `C:/Program Files/Git/tenders`; `git show origin/main:dosya`
  da bozulur. `MSYS_NO_PATHCONV=1` kullan ya da baştaki `/`yi verme.
- **Middleware'de `process.env` ÇALIŞMA ANI değeri okumaz.** Edge runtime'da
  derleme sırasında sabite çevrilir; imaja gömülmeyen değişken görünmez. CSP gibi
  middleware'de üretilen her şey derleme argümanı ister (Tur 11).
- **Mypy'yi CI ile aynı görmek için opsiyonel bağımlılıkları override'a yaz.**
  CI `uv sync --frozen` ile yalnız varsayılan grubu kurar; `parsing`/`ocr`/
  `embedding` paketleri orada YOKTUR. Override eksikse mypy CI'da
  "Cannot find implementation" der, geliştirici makinesinde sessiz kalır
  (Tur 11'de `pypdf` yüzünden CI kırıldı). CI ortamını yerelde üretmek için:
  `UV_PROJECT_ENVIRONMENT=.venv-ci UV_FROZEN=1 uv sync --frozen` (mevcut `.venv`i
  bozmaz).
- **Gitleaks `detect` GİT GEÇMİŞİNİ tarar, çalışma ağacını değil.** Yeni bir sır
  commit'lenmeden yakalanmaz; `--no-git` bu sürümde beklendiği gibi çalışmıyor
  (0–3 bayt tarıyor), çalışma ağacı için `gitleaks dir <yol>` kullan. İstisnalar
  `.gitleaks.toml`da ve yalnız `generic-api-key` kuralı için daraltılmış —
  sağlayıcıya özgü desenler test dosyalarında da bloke eder.
- **`5432`/`6379` başka bir projenin konteynerleri tarafından tutulabilir**
  (bu makinede FabrikaOS). O konteynerlere DOKUNMA; TenderIQ'yu yan portlara al:
  compose override'ında `ports: !override` ile (`ports` listeleri normalde
  BİRLEŞTİRİLİR, ezilmez) ve `DATABASE_URL`/`REDIS_URL`i o portlara yönlendir.
  Adlandırılmış hacim aynı kaldığı için veri korunur.

---

## 2. Sıradakiler

### 2.1 Öncelik sırası

1. **J.6 madde 2–3: TAVAN ve DEPOLAMA KOTASI (GA ENGELİ; ölçüm Tur 13'te bitti).**
   Ölçüm çalışıyor (`llm_usage`, `CostTracer`, `compute_spend_sync`) ama
   **hiçbir tavan yok** — `SIGNUP_MODE=open` ile kayıt açık olduğu için risk
   duruyor. Tur 13'te alt adım sınırında durduk; alınan tasarım kararları:
   - **`Plan.llm_budget_micros_try_per_month`** — ücretsiz kademeye ayrı ve
     sıkı tavan (kötüye kullanım yüzeyi orası). Sert tavanda **reddet**;
     sessizce küçük modele düşme / kısaltma / kısmi sonuç YOK.
   - **Yarış koruması: Redis rezervasyonu.** Yalnız "harcama < tavan" bakmak
     yetmez — eşzamanlı iki iş aynı anda bakıp ikisi de geçer. Kabul anında
     `llm:reserved:{tenant}:{period}` atomik artırılır (iş başına muhafazakâr
     bir tahmin), iş bitince düşülür; karar `harcanan + rezerve` üzerinden
     verilir. Aşım böylece (eşzamanlılık × tahmin) ile SINIRLI kalır.
   - **İşin ORTASINDA tavan aşılırsa iş BİTİRİLİR, sonraki iş reddedilir.**
     Gerekçe: token'lar zaten harcanmıştır (fatura oluştu) ve yarıda kesmek
     kullanıcıya işe yaramaz bir yarım analiz bırakır; aşım tek dokümanla
     sınırlıdır. Kesme, parayı geri getirmediği hâlde değeri yok eder.
   - Yumuşak eşikte (ör. %80) alarm: Tur 8'in e-posta yolu + arayüzde uyarı.
     Tavana çarpınca kullanıcı NE OLDUĞUNU, NE ZAMAN sıfırlanacağını
     (dönem `quota.current_period_bounds` ile aynı takvim ayı) ve ne
     yapabileceğini görmeli.
   - **Depolama kotası:** plan bazlı `storage_bytes`; aşımda yükleme reddi +
     bildirim. Mevcut kullanım hesabı silinen dosyalarda da doğru kalmalı.
   - Kuyruk adaleti (kiracı başına eşzamanlılık + adil sıralama) hâlâ ERTELENDİ.
2. **Havale/EFT ile manuel aktivasyon yolu** (ADR-0014'te korunmuş kart dışı yol).
3. **Onboarding sihirbazı + demo analiz.**
4. **Kalan doğrulama borcu:** statik prerender kaybının GERÇEK maliyeti
   (CDN/kenar önbelleği) ölçülmedi — staging olmadan ölçülemez (J.1) ·
   `email_suppression`dan adres çıkarmanın operatör ucu yok (ADR-0015 "Ödünler").

> **CI sonucu nasıl okunur** (`gh` CLI kurulu değil, gerek de yok — repo
> herkese açık). Son durum Bölüm 3'te; ilk yeşil koşum `61a0274`:
> ```bash
> curl -s "https://api.github.com/repos/Scryne/TenderIQ/actions/runs?branch=main&per_page=5"
> curl -s "https://api.github.com/repos/Scryne/TenderIQ/actions/runs/<id>/jobs"
> ```
> Job'ların hangi ADIMDA düştüğü buradan görünür. **Log İÇERİĞİ için kimlik
> doğrulaması gerekir (403)** — arızayı yerelde CI'ın komutunu birebir koşarak
> üret (Tur 11'de iki arıza da böyle bulundu).

### 2.2 Bilerek ertelenenler

- J.6 ölçek korkulukları · süresi dolmuş davet temizliği
- Abonelik istek/yanıt şemasının gerçeğe karşı doğrulanması (modül açılınca)
- Bastırılmış bir adresi listeden çıkarmanın operatör ucu (şu an yalnız elle DB —
  ADR-0015 "Ödünler")
- Lighthouse'un CI'da kapı olması (şu an elle koşuluyor; betik çıkış koduyla
  eşiği zorluyor, job'a bağlanmadı)

---

## 3. Doğrulama durumu

**Yeşilliğin tek geçerli kaynağı CI'dır.** Yapılandırma:
`.github/workflows/ci.yml` — job'lar: `backend` (ruff · mypy · pytest ·
`pytest -m integration` · eval kapısı), `contract` (OpenAPI drift), `frontend`
(eslint · tsc · next build), `e2e` (Playwright, iki yığın), `a11y` (Lighthouse —
kapı düşen DENETİM listesi, skor değil), `security` (gitleaks · pip-audit ·
trivy), `image-scan`.

| Ne | Durum | Nasıl / ne zaman ölçüldü |
|---|---|---|
| CI koşumu (Tur 10 push'u, `7274618`) | `e2e` ✅ · `image-scan` ✅ (3 imaj) · `frontend` ✅ · `contract` ✅ · **`security` ❌ (gitleaks)** · **`backend` ❌ (mypy)** | 2026-07-30, Actions REST API'sinden okundu (run #12, id 30516757650). İki arıza Tur 11'de yerelde üretilip düzeltildi |
| CI koşumu (Tur 13, `8f5ff82`) | **9 job'ın tamamı yeşil** | 2026-07-31, Actions REST API'si (run id 30587710454) |
| CI koşumu (Tur 12, `7a30448`) | **9 job'ın tamamı yeşil** | 2026-07-30, Actions REST API'si (run id 30568253675). Not: derleme kapısı önce `frontend` + `image-scan` job'larını düşürdü — kapı çalıştı, eksik olan bağlantıydı; denetim de o iki hedefi görmüyordu (manifesto listelemiyordu) |
| CI koşumu (Tur 11, `61a0274`) | **9 job'ın TAMAMI yeşil** (`backend` · `contract` · `frontend` · `e2e` · `a11y` · `security` · `image-scan`×3) | 2026-07-30, Actions REST API'sinden okundu (run id 30537772592). CI ilk kez uçtan uca yeşil |
| Yerel tam koşum (Tur 13 commit'i) | geçti | 2026-07-31 · `ruff check` + `ruff format --check` (248 dosya) · `mypy` strict 143 dosya · `pytest` 391 · `pytest -m integration` 160 · migration `0022` temiz DB'de upgrade→downgrade→upgrade |
| Yerel tam koşum (Tur 12 commit'i) | geçti | 2026-07-30 · `ruff check` + `ruff format --check` (241 dosya) · `mypy` strict 139 dosya · `pytest` 375 · `pytest -m integration` 157 · `playwright test` 23 · eslint + tsc + `next build` · derleme kapısı negatif doğrulandı |
| Yerel tam koşum (Tur 11 commit'i) | geçti | 2026-07-30 · `ruff check` + `ruff format --check` (240 dosya) · `mypy` strict **iki ortamda** (yerel `.venv` + CI eşi `.venv-ci --frozen`), 139 dosya · `pytest` 368 · `pytest -m integration` 157 · `playwright test` 17 · `replay_billing_webhook.py` 8/8 · eslint + tsc (web & api-client) + `next build` · OpenAPI ve api-client drift yok |
| Lighthouse erişilebilirlik | **18 rota × 100/100** (dinamik rotalar dâhil), düşen denetim yok | 2026-07-30 · `docs/ops/lighthouse-erisilebilirlik.md`; artık CI'da `a11y` job'ı olarak da koşar |
| Nonce CSP'nin performans bedeli | ortanca TTFB +6 ms · LCP +25 ms · skor değişmedi | 2026-07-30 · aynı makinede statik-prerender taban derlemesiyle karşılaştırıldı; localhost olduğu için CDN/önbellek kaybını ÖLÇMEZ |
| `0021` migration'ın geri alınabilirliği | doğrulandı | 2026-07-30 · temiz DB'de `upgrade → downgrade 0020 → upgrade`; ayrıca veri dolu yerel DB'de aynı çevrim (85 org / 101 kullanıcı korundu). Fonksiyon + 19 politika birebir geri geldi |

> Yerel ölçüm CI'nın yerini TUTMAZ: Windows/OneDrive ortamı CI'nın Linux
> ortamından farklı davranıyor (yukarıdaki tuzaklar) ve yerel koşum kirli bir
> veritabanı üzerinde çalışır. Bir sonraki oturum "yeşil mi?" sorusunu bu
> dosyadan değil CI'dan yanıtlamalı.

Veritabanı şema başı: `0022_llm_usage`.
