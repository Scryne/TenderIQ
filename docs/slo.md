# SLO'lar ve Ölçüm Kaynakları

> **Durum:** beta hedefleri · **Son güncelleme:** 2026-07-28 · **Sahibi:** Berkay (Scryne)
>
> Plan referansı: `GELISTIRME_PLANI.md` J.4. Bu belge "ne kadar iyi çalışmalı"
> sorusunun tek cevabıdır; olay anında ne yapılacağı `docs/runbook.md`dedir.

## 0. Neden bu belge var

Hedefsiz bir sistemde her yavaşlık tartışmaya açıktır ve her uyarı aciliyet
kazanır. SLO, "kabul edilebilir"in nerede bittiğini **önceden** yazar: hedefin
altına düşmeden alarm çalmaz, düştüğünde ise tartışma değil runbook başlar.

Solo-dev gerçekçiliği (J bölümü ilkesi: *yönetilen servis > kendi kur*): kendi
metrik yığınımızı (Prometheus + Grafana) işletmiyoruz. Uygulama, yuvarlanan bir
pencerenin sayaçlarını Redis'te tutar ve tek bir uçtan (`/ops/metrics`) sunar;
dış izleme ve status page hosted servislerdir.

## 1. Hedefler (beta)

| # | SLI | Hedef | Ölçüm kaynağı |
|---|---|---|---|
| 1 | API erişilebilirliği | ≥ **%99,5** | Dış izleyici (asıl) + `/ops/metrics` 5xx oranı (yardımcı) |
| 2 | API gecikmesi p95 | < **500 ms** | `/ops/metrics` → `api.p95_ms` |
| 3 | Doküman işleme süresi p95 | < **10 dk** (100 sayfa, dijital) | `/ops/metrics` → `phases[total].p95_seconds` |
| 4 | İşleme başarı oranı | ≥ **%98** | `/ops/metrics` → `phases[total].success_rate` |

Eşikler koda gömülüdür: `packages/core/src/tenderiq_core/ops.py` (`SLO_*` sabitleri).
Yük testi (`scripts/load_test.py`) hedefleri **oradan import eder** — belge ile
sistem ayrışamaz.

### Kapsam dışı bırakılanlar (bilinçli)

- **SSE/akış uçları** (`/api/v1/tenders/{id}/stream`): süreleri sunucunun
  yavaşlığı değil, sözleşmesidir (dakikalarca açık kalır). Gecikme histogramına
  hiç girmezler — yanıtın `content-type`'ı `text/event-stream` ise ölçüm atlanır.
- **Sağlık probları** (`/healthz`, `/readyz`) ve `/ops/*`: saniyede bir gelen ve
  daima hızlı olan istekler p95'i yapay olarak **iyileştirirdi**.
- **LLM'in kendi gecikmesi:** çıkarım worker'da, kullanıcı isteğinin dışında
  koşar; kullanıcıya yansıyan büyüklük #3'tür (uçtan uca işleme süresi).

## 2. Hata bütçesi

%99,5 aylık erişilebilirlik = **~3 sa 39 dk / ay** kesinti bütçesi.

| Bütçe tüketimi | Anlamı | Davranış |
|---|---|---|
| < %50 | Sağlıklı | Normal geliştirme; risk alınabilir |
| %50–100 | Daralıyor | Yeni altyapı değişikliği dondurulur; önce dayanıklılık işleri |
| > %100 | Aşıldı | Özellik geliştirme durur; kök neden kapanana dek yalnız güvenilirlik işi |

Bütçe elle takip edilir (dış izleyicinin aylık uptime raporu). Otomatik bütçe
takibi GA sonrasına bırakılmıştır — ölçüm hattı kurulmadan otomasyonu kurmak,
yanlış sayıyı otomatikleştirmek olurdu.

## 3. Ölçüm nasıl çalışır

### 3.1 Yuvarlanan pencere (uygulama içi)

- **Yazan:** API middleware'i her isteğin süresini/durum sınıfını, worker her
  fazın süresini/sonucunu **dakikalık histogram kovalarına** yazar
  (`ops:api:<dakika>`, `ops:job:<dakika>` hash'leri, 25 saat TTL).
- **Okuyan:** `GET /ops/metrics` son N dakikayı toplar (varsayılan 60,
  `?window=` ile daraltılır; tavan 24 saat).
- **Yüzdelikler kova tavanıdır**: "p95 = 500 ms", isteklerin %95'inin 500 ms
  kovasına *veya altına* düştüğü anlamına gelir. Değeri hep yukarı yuvarlar —
  yargı yanlışlıkla "geçti" diyemez.
- **Ölçüm asla isteği bozmaz:** Redis erişilemezse metrik kaybolur, istek akar.
  Bu, "pano çalışıyor ama ürün çalışmıyor" hâlinin tersini garanti eder.

Toplam işleme süresi (#3) **veritabanındaki** `job.started_at`/`finished_at`
damgalarından hesaplanır: retry'lı bir iş kullanıcıyı bir kez bekletir ve
ölçülmesi gereken o bekleyiştir, son denemenin süresi değil.

### 3.2 Ucu açmak

```bash
# .env
OPS_METRICS_TOKEN=$(openssl rand -hex 32)

curl -s -H "Authorization: Bearer $OPS_METRICS_TOKEN" \
     http://localhost:8000/ops/metrics | jq '{queue_depth, healthy, slos}'
```

Token yapılandırılmamışsa uç **404** döner (401 değil): kapalı bir kurulumda
ucun varlığı bile sızmaz. Uç kiracı verisi döndürmez, yalnız kurulum geneli
toplamları döndürür; OpenAPI sözleşmesine dâhil değildir.

### 3.3 Dış izleme (asıl erişilebilirlik kaynağı)

Kendi sunduğu metrikle kendi erişilebilirliğini ölçen bir sistem, çöktüğünde
%100 uptime raporlar. Bu yüzden **#1'in asıl kaynağı dış izleyicidir**;
`/ops/metrics`teki 5xx oranı yalnız yardımcı göstergedir.

Kurulacak kontroller (hosted izleyici — BetterStack/Instatus/UptimeRobot):

| Kontrol | Aralık | Alarm koşulu |
|---|---|---|
| `GET /healthz` (API) | 60 sn | 2 ardışık başarısız |
| `GET /readyz` (API) | 60 sn | 2 ardışık başarısız (DB/Redis kopuğu) |
| `GET /` (web) | 60 sn | 2 ardışık başarısız |
| `GET /ops/metrics` → `healthy == false` | 5 dk | 3 ardışık ihlal |

Bildirim kanalı: e-posta + Telegram. Sentry (hata izleme) zaten kuruludur ve
PII maskelemesi `tenderiq_core.observability.scrub_event` ile doğrulanmıştır.

### 3.4 Status page

Hosted status page (Instatus/BetterStack) dış izleyicinin kontrollerine
bağlanır. Bileşenler: **API**, **Web**, **Doküman işleme**. Planlı bakım aynı
sayfadan duyurulur. Kapalı beta boyunca müşteri sayısı tek haneli olduğundan
duyurular ayrıca e-posta ile yapılır.

## 4. Uyarı eşikleri

Uyarı, SLO ihlalinden **önce** gelmelidir; ihlal anında gelen uyarı geç kalmıştır.

| Sinyal | Eşik | Aciliyet |
|---|---|---|
| `/healthz` veya `/readyz` düştü | 2 ardışık | **Acil** — runbook §1/§2 |
| `queue_depth` > 50 ve artıyor | 10 dk | **Acil** — runbook §2 |
| `phases[total].success_rate` < %98 | 30 dk penceresi | Yüksek — runbook §3 |
| `api.p95_ms` > 500 | 30 dk penceresi | Orta — runbook §5 |
| Sentry'de yeni hata sınıfı | ilk görülme | Orta |
| Disk kullanımı > %80 | — | Orta — runbook §4 |

## 5. Yük testiyle doğrulama

SLO'lar üretim trafiği beklemeden doğrulanabilir olmalıdır:

```bash
uv run python scripts/load_test.py --tenants 10 --docs 1 --pages 100 \
    --base-url https://staging.tenderiq.example --ops-token "$OPS_METRICS_TOKEN"
```

Betik gerçek yığına karşı koşar, aynı SLO eşiklerini uygular ve ihlalde **çıkış
kodu 1** döndürür (zamanlanmış dayanıklılık koşusu olarak CI'dan çağrılabilir).
Üretim verisi oluşturduğu için production'a karşı **koşulmaz**.

Ücretsiz plan aylık 5 doküman / 150 sayfa olduğundan varsayılan senaryo
(1×100 sayfa) kotaya sığar; daha büyük koşularda `--plan pro` verilir.

## 6. Log saklama ve PII

- Yapılandırılmış (JSON) loglar merkezî toplayıcıda **≥ 30 gün** saklanır.
- Loglar PII değil **korelasyon kimlikleri** taşır: `request_id`, `tenant_id`,
  `job_id`. Bu kural bir temenni değil, `packages/core/tests/test_log_pii.py`
  ile uygulanan **statik kapıdır**: log çağrılarında `email=`, `body=`, `text=`
  gibi alan adları ve f-string olay adları reddedilir.
- E-posta adresi loglanması gerektiğinde `tenderiq_core.logging.mask_email` ile
  maskelenir (`b***@example.com`).
- Gerekçe: silme akışımız (KVKK md. 7) veritabanını ve nesne depolamayı temizler,
  **log arşivini temizlemez**. Oraya sızan kişisel veri, silme talebinin
  ulaşamadığı bir kopya üretirdi.

## 7. Açık uçlar

1. **Dış izleyici + status page hesabı henüz açılmadı** (J.4). Bu belge
   kontrolleri tanımlar; kurulum kapalı beta öncesi yapılacaktır.
2. **Hata bütçesi takibi elle.** Otomatik tüketim grafiği GA sonrası.
3. **Metrikler tek Redis'e yazılır.** Redis kaybı = ölçüm penceresi kaybı
   (ürün etkilenmez). Kalıcı metrik arşivi ihtiyaç doğarsa eklenir.
