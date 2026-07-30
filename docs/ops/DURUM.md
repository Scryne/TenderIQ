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
| 10 | Tur 9'un taze doğrulaması · DURUM.md yeniden yapılandırıldı · zorlayıcı nonce CSP · Lighthouse a11y · ADR-0015 + sızıntı testi · bounce webhook testi (**rota bağlanmamış kusuru bulundu**) | `b63abee` |

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
- **İçerik Güvenlik Politikası ZORLAYICI ve nonce tabanlıdır** (Tur 10).
  Tanım `apps/web/src/lib/security/csp.ts`, yayın `middleware.ts`; ihlaller
  `/api/csp-report`ta toplanır. `script-src`e `'unsafe-inline'` EKLEME — nonce'un
  tüm değerini iptal eder; `e2e/csp.spec.ts` bunu CI'da yakalar. Nonce istek
  başına değiştiği için kök layout `headers()` okur ve **tüm rotalar dinamik
  render'dadır** (bilinçli ödün). `style-src 'unsafe-inline'` kalan borçtur:
  Next kritik CSS'i satır içi gömüyor ve nonce geçirmenin desteklenen yolu yok.
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

---

## 2. Sıradakiler

### 2.1 Öncelik sırası

1. **CI sonucunu OKU** — Tur 10'da 30 commit `origin/main`e push edildi ve CI ilk
   kez `e2e` + `image-scan` job'larıyla koştu. Sonuç bu dosyada YAZMIYOR: GitHub
   Actions'tan bakılacak. Düşen job varsa sıradaki iş odur. (`gh` CLI kurulu
   değil; kurulursa `gh run list` ile okunabilir.)
2. **Havale/EFT ile manuel aktivasyon yolu** (ADR-0014'te korunmuş kart dışı yol).
3. **Onboarding sihirbazı + demo analiz.**
4. **Kalan doğrulama borcu:** `/tenders/[id]` ve `/tenders/[id]/review` için
   Lighthouse ölçümü (dinamik rota; betiğin listesi sabit — inceleme ekranı
   çekirdek çalışma alanı olduğu için açık madde) · nonce CSP'nin tüm rotaları
   dinamik render'a geçirmesinin performans maliyeti ölçülmedi.

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
(eslint · tsc · next build), `e2e` (Playwright, iki yığın), `security`
(gitleaks · pip-audit · trivy), `image-scan`.

| Ne | Durum | Nasıl / ne zaman ölçüldü |
|---|---|---|
| CI koşumu | Tur 10'da ilk kez tetiklendi; **sonucu bu dosya BİLMİYOR** | 2026-07-30, 30 commit `origin/main`e push edildi. Sonuç GitHub Actions'ta; bir sonraki oturum oradan okumalı |
| Yerel tam koşum (Tur 10 commit'i) | geçti | 2026-07-30 · `ruff check` + `ruff format --check` (238 dosya) · `mypy` strict (139 dosya) · `pytest` 358 · `pytest -m integration` 157 · `playwright test` 16 · `replay_billing_webhook.py` 8/8 · eslint + tsc (web & api-client) + `next build` · OpenAPI ve api-client drift yok |
| Lighthouse erişilebilirlik | 16 rota × 100/100 | 2026-07-30 · `docs/ops/lighthouse-erisilebilirlik.md` (yöntem + düzeltilen üç kusur orada) |
| `0021` migration'ın geri alınabilirliği | doğrulandı | 2026-07-30 · temiz DB'de `upgrade → downgrade 0020 → upgrade`; ayrıca veri dolu yerel DB'de aynı çevrim (85 org / 101 kullanıcı korundu). Fonksiyon + 19 politika birebir geri geldi |

> Yerel ölçüm CI'nın yerini TUTMAZ: Windows/OneDrive ortamı CI'nın Linux
> ortamından farklı davranıyor (yukarıdaki tuzaklar) ve yerel koşum kirli bir
> veritabanı üzerinde çalışır. Bir sonraki oturum "yeşil mi?" sorusunu bu
> dosyadan değil CI'dan yanıtlamalı.

Veritabanı şema başı: `0021_rls_null_safe_tenant`.
