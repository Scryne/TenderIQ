# TenderIQ — portföy brifingi

> Bu dosya bir **veri çıkarma** çıktısıdır, pazarlama metni değildir. Her sayının
> yanında kaynağı vardır. Bilinmeyen alanlar `BİLİNMİYOR` yazar.
>
> **Ölçüm ayrımı:** "**[bu oturumda ölçüldü]**" = komutu bu oturumda ben koşturdum.
> "**[kodda yazıyor]**" = kaynak dosyadan/commit gövdesinden okundu, yeniden
> doğrulanmadı. "**[proje kaydı]**" = `docs/ops/DURUM.md` gibi projenin kendi
> ölçüm kaydından alındı; ölçen ben değilim, tarihi ve yöntemi orada yazıyor.
>
> Çıkarma tarihi: 2026-08-09. Depo durumu: `main`, HEAD `3606531`, çalışma ağacında
> commit'lenmemiş 8 dosya var (aşağıda).

---

## 1. Künye

**Ne yapar**
Türkçe kamu ihale/RFP dosyalarını okuyup gereksinimleri, riskleri, istenen
teslim belgelerini, takvimi ve firmanın uygunluk boşluklarını çıkarır; her bulguyu
dokümandaki kaynak sayfa ve maddeye bağlar.

**Kimin için**
Türkçe kamu ihalelerine teklif veren firmaların teklif/ihale ekipleri. Koddan
çıkarılan kanıtlar:

- Landing rozeti: "Kapalı beta · Türkçe kamu ihaleleri" (`apps/web/src/app/page.tsx:126`) **[kodda yazıyor]**
- `CapabilityProfile` modeli kiracı başına tek "firma yetkinlik profili" tutuyor ve
  uygunluk boşluğu analizinin girdisi — yani kullanıcı bir *firma*, birey değil
  (`packages/core/src/tenderiq_core/models/capability_profile.py:1-25`) **[kodda yazıyor]**
- Organizasyon / üyelik / davet modelleri ve rol yönetimi var → ekip kullanımı
  (`packages/core/src/tenderiq_core/models/`, `apps/api/.../routers/v1/members.py`, `invitations.py`) **[kodda yazıyor]**
- Sektör dağılımı `spike-docs/` altındaki gerçek test dosyalarından okunuyor: sağlık
  kurumu hizmet alımları, temizlik, güvenlik, BT, tıbbi cihaz (MR) şartnameleri
  **[bu oturumda ölçüldü — dizin listesi; dosyalar commit'lenmemiş, bkz. §9]**

**Çalışma dönemi**
İlk commit **2026-07-04**, son commit **2026-07-31**. Toplam 28 gün, 74 commit,
hepsi tek ay içinde. **[bu oturumda ölçüldü — `git log --reverse` / `git log -1`]**

Commit yoğunluğu düz değil **[bu oturumda ölçüldü — `git log --format=%ad --date=short | uniq -c`]**:

| Dönem | Commit | Not |
|---|---|---|
| 07-04 → 07-08 | 3 | Faz 0 (bootstrap + denetim) |
| 07-09 → 07-15 | **0** | **7 günlük ara** |
| 07-16 → 07-28 | 21 | Faz 1-2-3 (hattı, ajanlar, UI) — günde 1-4 |
| 07-29 | 20 | ← |
| 07-30 | 12 | ← Faz 4 / GA hazırlığı: 74 commit'in **50'si son 3 günde** |
| 07-31 | 18 | ← |

Son commit'ten (07-31) sonra da çalışılmış ama commit'lenmemiş: çalışma ağacında
CSP/depolama zinciri düzeltmesi duruyor ve `DURUM.md`'de 2026-08-01 tarihli bir
tuzak notu var. **[bu oturumda ölçüldü — `git status`; tarih DURUM.md §1.4'ten]**

**Rol**
Tek geliştirici. `git shortlog -sn --all` → **74 commit, tek yazar (Berkay)**;
başka katkıda bulunan yok. **[bu oturumda ölçüldü]**
Commit gövdelerinde `Co-Authored-By: Claude Opus 4.8 / Opus 5` trailer'ları var —
proje AI eşli geliştirme ile yürütülmüş. **[kodda yazıyor — ör. `a42ae31`, `2a2b445`]**

**Yığın** (mimariyi belirleyen 8 madde; tam bağımlılık listesi değil)

1. **Next.js (App Router) + TypeScript + Tailwind/shadcn** — frontend
2. **FastAPI (async) + SQLAlchemy 2.0 async + Pydantic** — API
3. **Celery + Redis** — asenkron işleme hattı (parse → index → extract)
4. **PostgreSQL 16 + pgvector**, kiracı izolasyonu **RLS** ile (ADR-0002, ADR-0003)
5. **LangGraph** orkestrasyon + **Anthropic Claude** (üretim yolu); dev katmanında
   NVIDIA NIM (`qwen3.5-122b`) ve Ollama (ADR-0005)
6. **Docling + pypdf + EasyOCR** — hibrit parsing, sayfa bazlı dijital/taranmış
   yönlendirme (ADR-0004, ADR-0011)
7. **BGE-M3 embedding + BM25 + RRF füzyon + reranker** — hibrit getirim (ADR-0008, ADR-0012)
8. **Cloudflare R2 (S3-uyumlu)** — doküman nesne depolama

**[hepsi kodda yazıyor — `packages/core/pyproject.toml`, `pyproject.toml`, `docs/adr/`]**

**Satır ve dosya sayısı** (yalnız git'in izlediği dosyalar; `node_modules`, `.venv`,
`.next`, üretilmiş çıktı hariç) **[bu oturumda ölçüldü — `git ls-files | xargs wc -l`]**

| Tür | Dosya | Satır |
|---|---|---|
| Python (`.py`) | 258 | 38.483 |
| React (`.tsx`) | 79 | 13.754 |
| TypeScript (`.ts`) | 35 | 8.593 |
| CSS | 1 | 403 |
| Node script (`.mjs`) | 4 | 554 |
| SQL | 1 | 15 |
| **Kod toplamı** | **378** | **61.802** |
| Markdown (belge) | 37 | 7.269 |

**Düzeltme payı:** `.ts` toplamının **4.996 satırı** OpenAPI'dan üretilen
`packages/api-client/src/schema.d.ts`; elle yazılmış TypeScript ≈ 3.597 satır.
Yani elle yazılmış kod ≈ **56.806 satır**. **[bu oturumda ölçüldü]**

İzlenen toplam dosya sayısı: **460**. Diskteki toplam dosya sayısı bunun ~113 katı
(`node_modules` + `.venv` + torch/docling model ağırlıkları).

**Commit sayısı:** 74 **[bu oturumda ölçüldü — `git rev-list --count HEAD`]**

---

## 2. Durum

### `GA öncesi`

**Gerekçe:** Ürünün tüm akışı uçtan uca kapalı ve CI'da doğrulanıyor
(kayıt → e-posta doğrulama → doküman yükleme → parse/index/extract → inceleme →
onay → Word/Excel export → abonelik/kota), ama **hiç yayına alınmamış**: staging
ortamı yok, ödeme sağlayıcısının abonelik modülü hesapta kapalı ve hukuki metinler
taslak.

**Ölçülebilir ayrıntı:**

- CI'nın **9 job'ının tamamı yeşil** (`backend`, `contract`, `frontend`, `e2e`,
  `a11y`, `security`, `image-scan`×3) — 2026-07-31, run id `30645835860`, commit
  `eddc16e` **[proje kaydı — DURUM.md §3]**
- Yerel tam koşum (Tur 17, 2026-07-31): **413 unit + 183 entegrasyon** pytest çıkışı 0,
  **Playwright 25/25**, mypy strict 149 dosya, ruff 258 dosya **[proje kaydı]**
- Buna karşılık `DURUM.md §1.3` **6 doğrulanmamış varsayım** listeliyor ve bunların
  4'ü ödeme/e-posta sağlayıcısının hesap tarafında kapalı olmasından kaynaklanıyor
  (iyzico abonelik modülü kapalı → istek/yanıt şeması ve webhook olay türü eşlemesi
  gerçek bir olayla doğrulanmadı; Resend'e gerçek gönderim yapılmadı) **[proje kaydı]**
- `LEGAL_TODO.md`'de **12 zorunlu alan** hâlâ boş; hukuki metinler taslak **[proje kaydı]**
- Kodda TODO/FIXME yoğunluğu **düşük: 9 işaret / 5 dosya** (61.802 satırda) — yani
  durum "yarım kalmış modül" değil, "dış onay bekleyen ürün"
  **[bu oturumda ölçüldü — `grep -E "TODO|FIXME|HACK|XXX"`]**

**Neden `yayında` değil:** dağıtım yok. `DURUM.md §2.1` madde 5, statik prerender
kaybının gerçek maliyetinin "**staging olmadan ölçülemez**" olduğunu yazıyor —
yani staging ortamı hiç kurulmamış. Ödeme akışı `BILLING_PROVIDER=fake/manual` ile
test ediliyor; canlı mod (`BILLING_ENV=live`) ikinci bir onay bayrağı istiyor ve hiç
açılmamış. **[proje kaydı + kodda yazıyor]**

**Neden `geliştirme` değil:** projenin kendi fazlaması GA hazırlığında
(ADR-0013 başlığı "Faz 4 / GA hazırlığı"), son 17 turun tamamı yeni özellik değil
GA kapısı kapatma işi (CI yeşile alma, yapılandırma kapıları, bütçe tavanı, kota
kalibrasyonu, erişilebilirlik). **[kodda yazıyor — `docs/adr/0013`, DURUM.md §1.1]**

**Kullanıcı sayısı: 0.** Kapalı beta; ödeme modülü açılmamış. **[kodda yazıyor]**

---

## 3. Problem

### README'nin tanımı

> "Yüzlerce sayfalık Türkçe ihale/RFP dokümanlarını dakikalar içinde analiz eder;
> gereksinim, risk, teslim-belge ve uygunluk boşluklarını kaynağına kadar
> izlenebilir (citation-first) biçimde çıkarır."
> — `README.md:3-6` **[kodda yazıyor]**

### Koda bakınca doğrulanan hâli

Problem tanımı **kodla örtüşüyor** ve kod onu README'den daha keskin söylüyor:

- **Acı 1 — hacim.** Bir kamu ihalesi dosyası tek belge değil: idari şartname,
  teknik şartname, sözleşme tasarısı, teklif mektubu, yaklaşık maliyet formu ayrı
  ayrı gelir (`spike-docs/` içindeki 20 gerçek dosya bu dağılımı gösteriyor). Teklif
  ekibi bunları elle tarayıp gereksinim listesi çıkarıyor.
- **Acı 2 — kaçırılan zorunlu madde pahalı.** Eval metriklerinden biri doğrudan
  `kaçırılan-zorunlu` oranı (`a42ae31` commit gövdesi) — ürünün ölçtüğü şey
  "özet kalitesi" değil, "atlanan şart".
- **Acı 3 — bu yüzden LLM özeti yetmez.** Kaynağını gösteremeyen bir çıkarım, teklif
  kararında kullanılamaz. Kod bunu bir ürün sözü değil **zorunluluk** olarak
  uyguluyor: `grounding.py` her bulgunun birebir alıntısını kaynak metinde arar;
  bulamazsa bulgu `UNGROUNDED` işaretlenir ve **API'den hiç dönmez** (DB'ye yalnız
  gözlemlenebilirlik için yazılır).
  — `packages/core/src/tenderiq_core/agents/grounding.py:1-25` **[kodda yazıyor]**
- **Acı 4 — "bize uygun mu?" sorusu ayrı bir iş.** Uygunluk boşluğu analizi,
  dokümandan çıkarılmayan tek girdiyi kullanıcıdan alıyor: firmanın kendi yetkinlik
  profili (sertifika, iş deneyimi, mali kapasite). **[kodda yazıyor]**

### Ayrışma — bunu portföyde düzeltmen gerekir

README'nin **yol haritası tablosu bayat**. `README.md:105-113` şöyle diyor:

| Faz | README'nin dediği | Gerçek |
|---|---|---|
| 1 | 🚧 "Sırada" | 2026-07-17'de kapandı (`25bfc32`) |
| 2 | ⏳ | 2026-07-19'da kapandı (`a42ae31`) |
| 3 | ⏳ | 2026-07-24'te kapandı (`0950e59`) |
| 4 | ⏳ | Sürüyor — 17 tur tamamlandı |

**Güncel olan `docs/ops/DURUM.md`'dir, README değil.** README 2026-07-08 tarihli
(`git log -1 -- README.md`) ve projenin ilk haftasından kalma. Problem *tanımı*
hâlâ doğru; *durum* tablosu değil. **[bu oturumda ölçüldü]**

---

## 4. Sistem

### Ana bileşenler ve sorumluluk sınırları

| Bileşen | Sorumluluk | Sınır — ne YAPMAZ |
|---|---|---|
| `apps/web` (Next.js) | Arayüz, oturum çerezi, CSP nonce üretimi | İş mantığı yok; backend'e **yalnız** üretilen `@tenderiq/api-client` üzerinden çıkar |
| `apps/api` (FastAPI) | HTTP sözleşmesi, kimlik/yetki, kota ve bütçe kabul kontrolü, SSE | Ağır iş yapmaz; parse/embed/LLM çağırmaz — kuyruğa atar |
| `apps/worker` (Celery) | Hattı yürütür: parse → index → extract; periyodik görevler (mutabakat, silme süpürme, bayat yükleme temizliği) | HTTP sunmaz |
| `packages/core` | **Ortak her şey**: modeller, servisler, parsing, getirim, ajanlar, billing, e-posta, export, LLM maliyet/bütçe | — |
| `packages/api-client` | OpenAPI'dan **üretilen** TS istemcisi | Elle düzenlenmez (CI drift kapısı var) |

**Dürüst not — `packages/core` sınır tanımıyor.** 258 Python dosyasının çoğu burada;
alt paketleri (`agents/`, `retrieval/`, `parsing/`, `billing/`, `services/`,
`models/`, `llm/`, `email/`, `export/`, `security/`, `indexing/`, `db/`) ayrı
sorumluluklar taşıyor ama tek dağıtım biriminde duruyorlar. `apps/*` gerçekten
"ince giriş noktası": worker'ın tamamı 10 dosya, API'nin router katmanı 20 dosya.
**[bu oturumda ölçüldü — dosya sayımları]**

### Veri akışı

```
Tarayıcı → (imzalı URL) → Nesne depolama (R2)          ← baytlar API'den GEÇMEZ
    ↓ "yükleme tamam" bildirimi
API → kota + depolama kapısı (gerçek nesne boyutuyla) → Job kaydı → Redis kuyruğu
    ↓
Worker · parse:   sayfa bazlı yönlendirme (dijital metin var mı?) → Docling (+EasyOCR)
                  → ParsedElement (sayfa + bbox + seq)
Worker · index:   yapı-farkında chunking → BGE-M3 embedding → pgvector
Worker · extract: LangGraph → retrieve_context (pgvector + BM25 → RRF → rerank)
                  → paralel ajanlar (gereksinim / teslim-belge / risk / takvim / uygunluk)
                  → grounding doğrulaması (alıntı kaynakta var mı?)
                  → Finding kayıtları (RLS'li tablolar)
    ↓
API → /tenders/{id}/review → tarayıcı PDF'i doğrudan depolamadan çeker,
      PDF.js tuvalinde bulgunun bbox'ını vurgular → onay → Word/Excel export
```

Her LLM çağrısı `CostTracer`'dan geçer; token'lar contextvar tamponunda birikir ve
faz sonunda `llm_usage` tablosuna tek transaction'da yazılır. Faz **başlamadan** önce
plan bütçesine karşı Redis'te atomik rezervasyon alınır. **[kodda yazıyor —
`llm/cost.py`, `services/llm_reservation.py`, `tasks/documents.py`]**

### Dış bağımlılıklar

| Bağımlılık | Ne için | Zorunlu mu |
|---|---|---|
| PostgreSQL 16 + pgvector | Tüm veri + vektör indeksi | Evet |
| Redis | Celery broker, oran sınırı, bütçe rezervasyonu, webhook dedup | Evet |
| Cloudflare R2 / S3-uyumlu | Doküman nesneleri, imzalı URL | Evet |
| Anthropic Claude | Üretim çıkarım yolu | Analiz için evet |
| NVIDIA NIM / Ollama | Dev/ucuz iterasyon LLM'i | Hayır |
| Resend | İşlemsel e-posta (`memory` sağlayıcısı test için) | Hayır (test'te) |
| iyzico | Abonelik ödemesi (`fake` sağlayıcısı test için) | Hayır (test'te) |
| Langfuse | LLM tracing — anahtar yoksa **tamamen no-op**, import bile edilmez | Hayır |
| Sentry | Hata izleme — DSN yoksa no-op | Hayır |

**[hepsi kodda yazıyor — `packages/core/pyproject.toml`, `config.py`, `conftest.py`]**

### Diyagram önerisi — 9 kutu

```
1  Tarayıcı / Next.js arayüz
2  FastAPI (kimlik · kota · bütçe kapısı)
3  Redis (kuyruk · rezervasyon · oran sınırı)
4  Celery Worker (hattın yürütücüsü)
5  Nesne depolama R2 (imzalı URL — tarayıcıya DOĞRUDAN ok)
6  Parsing (Docling + OCR yönlendirme)
7  pgvector + BM25 hibrit getirim
8  LangGraph ajanları + grounding doğrulaması
9  PostgreSQL 16 (RLS — kiracı izolasyonu)
```

**Diyagramda mutlaka görünmesi gereken iki ok** (ürünün iddiası bunlarda):

- **5 → 1 doğrudan ok**: doküman baytları API'den geçmiyor, tarayıcı depolamaya
  doğrudan çıkıyor (hem yükleme hem önizleme). CSP'nin `connect-src`i bu yüzden
  ayrı bir origin taşımak zorunda.
- **8 → 9 ok üzerinde "grounding" kapısı**: kaynağa bağlanamayan bulgu geçemiyor.

---

## 5. Kritik kararlar

### Karar 1 — Kiracı izolasyonu veritabanı katmanında (PostgreSQL RLS)

- **Seçim:** Her kiracı-kapsamlı tablo RLS politikası taşıyor; uygulama RLS'ye tabi
  `tenderiq_app` rolüyle bağlanıyor, migration'lar ayrıcalıklı `tenderiq` rolüyle
  koşuyor. Kiracı ifadesi tek bir null-safe SQL fonksiyonunda:
  `tenant_id = app_current_tenant()`. (ADR-0003, migration `0021`)
- **Alternatif:** İzolasyonu uygulama katmanında tutmak — her sorguya
  `WHERE tenant_id = ?` eklemek (ORM seviyesinde global filtre). Ya da kiracı başına
  ayrı şema.
- **Gerekçe:** Uygulama katmanı filtresi, "unutulan tek bir sorgu"ya karşı savunmasız
  ve çok-kiracılı SaaS'ta bu sızıntı sınıfı geri alınamaz. RLS, hatayı sessiz sızıntı
  yerine boş sonuç kümesine çeviriyor (fail-closed).
- **Bedel:** *(dört tanesi de ölçülebilir)*
  1. **İki veritabanı rolü + iki bağlantı dizesi** — kurulum karmaşıklaştı; eski veri
     hacmiyle çalışanların hacmi bir kez sıfırlaması gerekti (`README.md:61-64`).
  2. **22 migration boyunca politika bakımı**; `audit_log`'un append-only olması
     (UPDATE/DELETE politikası bilinçli YOK) politikalara dokunan her migration'ın
     korumak zorunda olduğu bir değişmez.
  3. **Bağlantı havuzu tuzağı**: ham `current_setting` kullanan bir politika, havuzda
     sorguyu çökertiyor ve NullPool'lu test bunu göremiyor — bu yüzden ifade tek
     fonksiyona indirildi ve **yapısal bir test** (`test_rls_no_context.py`) kalıptan
     sapmayı yakalıyor. Yani karar, kendini koruyacak ekstra bir test katmanı istedi.
  4. **İzolasyon iki yerde**: `organization`, `membership`, `user_account`,
     `invitation`, `waitlist_entry`, `email_suppression` tablolarında RLS **kapalı**
     (bunlar kiracı-kapsamlı değil) — yani "her şey RLS'te" diyemiyorsun, iki
     mekanizmayı birden bilmek gerekiyor.

**[kodda yazıyor — ADR-0003, ADR-0015, `migrations/versions/0021_rls_null_safe_tenant.py`, DURUM.md §1.2]**

---

### Karar 2 — Grounding zorunlu: kaynağa bağlanamayan bulgu gösterilmez

- **Seçim:** Her ajan çıktısı `source_index` + birebir `source_quote` taşımak zorunda.
  `grounding.py` alıntıyı kaynak metinde **deterministik olarak** (LLM'siz) arıyor:
  Türkçe-farkında büyük harf katlaması (İ/I), tipografik noktalama denkliği,
  boşluk normalizasyonu. Üç çözünürlük: `ELEMENT` (tek öğe → bbox'a kadar),
  `CHUNK` (öğe sınırı aştı → sayfa izlenebilir), `UNGROUNDED` (bulunamadı).
  `UNGROUNDED` bulgular **API'den dönmez.**
- **Alternatif:** LLM'in ürettiği sayfa/madde referansına güvenip olduğu gibi
  göstermek; ya da doğrulamayı ikinci bir LLM çağrısıyla ("bu alıntı metinde var mı?")
  yapmak.
- **Gerekçe:** Teklif kararında kullanılacak bir çıkarımın kaynağı doğrulanabilir
  olmalı; LLM'in ürettiği referans halüsinasyona en açık alan. Deterministik eşleme
  ayrıca ücretsiz ve tekrarlanabilir.
- **Bedel:**
  1. **Recall düşüyor.** Doğrulanamayan doğru bulgular da eleniyor. qwen dev
     modeliyle ölçülen taban: `requirements R=0.20`, `deliverables R=0.00`,
     `risks R=0.07` (`a42ae31` commit gövdesi, 3 gerçek şartname).
  2. **Ajan istemi kırılganlaştı:** modelden şemaya uyan bir alıntı istemek, çıktı
     token'ını ve şema-ret oranını artırıyor.
  3. **Türkçeye özel bir metin normalizasyon katmanı** elle yazıldı ve bakımı
     `retrieval.keyword` ile senkron kalmak zorunda (aynı katlama kuralı iki yerde).
  4. **Bağlam penceresi taşarsa sessizce çöküyor** — bkz. §6'daki ikinci aday olay:
     model kaynağı göremeyince grounding 14 gereksinimin 1'ine düştü.

**[kodda yazıyor — `agents/grounding.py`, `a42ae31` commit gövdesi]**

---

### Karar 3 — Zorlayıcı nonce tabanlı CSP; bedeli tüm rotaların dinamik render'ı

- **Seçim:** İçerik Güvenlik Politikası `report-only` değil **zorlayıcı**, script'ler
  istek başına üretilen nonce ile çalışıyor. Nonce her istekte değiştiği için kök
  layout `headers()` okuyor → **Next'in tüm rotaları dinamik render'a düştü**
  (statik prerender yok). İhlaller `/api/csp-report`ta toplanıyor; `e2e/csp.spec.ts`
  ve `csp-policy.spec.ts` politikayı CI'da kapı olarak sınıyor.
- **Alternatif:** Statik prerender'ı korumak ve CSP'yi hash tabanlı ya da
  `'unsafe-inline'`li gevşek bir politikayla yazmak (ya da yalnız `report-only`
  bırakmak).
- **Gerekçe:** `'unsafe-inline'` script-src'de nonce'un tüm değerini iptal ediyor;
  hash tabanlı izin her paket sürümünde kırılıyor. Ürün KVKK-uyumluluk iddiası
  taşıdığı için XSS yüzeyini kapalı tutmak pazarlama değil sözleşme meselesi.
- **Bedel:**
  1. **Statik prerender kaybedildi.** Ölçülen bedel localhost'ta küçük: ortanca
     TTFB **+6 ms**, LCP **+25 ms**, Lighthouse skoru değişmedi — ama bu ölçüm
     **CDN/kenar önbelleği kaybını göremiyor** ve gerçek maliyet staging olmadan
     ölçülemiyor. Yani bedelin bir kısmı hâlâ **bilinmiyor**.
  2. **`style-src 'unsafe-inline'` kalıcı borç.** Kök sebep ölçülerek bulundu:
     `sonner` (toast paketi) çalışma anında `document.head`e **14,8 KB'lık nonce'suz**
     bir `<style>` bloğu enjekte ediyor ve nonce kabul etmiyor. Sıkılaştırma denendi,
     her sayfada 3 ihlal üretti, geri alındı.
  3. **Depolama origin'i derleme argümanı olmak zorunda.** Middleware edge
     runtime'da koşuyor ve `process.env` orada derleme sırasında sabite çevriliyor →
     `NEXT_PUBLIC_STORAGE_ORIGIN` çalışma anında verilirse **işe yaramıyor** ve
     doküman tuvali **sessizce boş kalıyor**. Bu yüzden ayrı bir yapılandırma
     manifestosu + üç kapı (derleme / açılış / dağıtım-dosyası denetimi) yazılmak
     zorunda kalındı (Tur 12, `0067e70`) — CSP kararı bir alt sistem doğurdu.

**[kodda yazıyor — `apps/web/src/lib/security/csp.ts`, `middleware.ts`, DURUM.md §1.2/§3]**

---

### Karar 4 — Frontend ile backend arasında üretilen tip sözleşmesi (OpenAPI → TS)

- **Seçim:** Frontend backend'e **yalnız** `@tenderiq/api-client` üzerinden erişiyor;
  istemci OpenAPI şemasından üretiliyor (`schema.d.ts`, 4.996 satır, elle
  düzenlenmiyor). CI'da iki drift kapısı var: şema commit'lenenle aynı mı, üretilen
  TS commit'lenenle aynı mı. (ADR-0010)
- **Alternatif:** Elle yazılmış tipli bir fetch katmanı; ya da tRPC/GraphQL gibi tek
  dilli bir sözleşme (bu, backend'i Python'dan çıkarmayı gerektirirdi).
- **Gerekçe:** Backend Python, frontend TypeScript. İki dil arasında tek doğruluk
  kaynağı olmadan, şema değişikliği çalışma anında patlıyor — hem de en pahalı yerde
  (kullanıcının ekranında).
- **Bedel:**
  1. **Her şema değişikliği iki ekstra komut istiyor**
     (`export_openapi.py` + `api-client generate`) ve bunu **hiçbir yerel araç
     hatırlatmıyor**: `pytest` de `mypy` de göremiyor.
  2. **Bu unutuldu ve CI'ı düşürdü.** Tur 15, `DocumentCreate.size_bytes` eklendiği
     ama şema yeniden üretilmediği için **8/9** ile döndü (run id 30632395852) —
     "yerel tam koşum geçti" raporu sözleşme kapısını hiç çalıştırmamıştı.
     Tur 16'da `650b59e` ile düzeltildi.
  3. **Üretilmiş 4.996 satır depoda duruyor** ve her şema değişikliğinde diff'i
     şişiriyor.

**[kodda yazıyor — ADR-0010, DURUM.md §1.4/§3, commit `650b59e`]**

---

## 6. Zorlandığım yer

### Ana olay: Bütçe tavanı vardı, çalışıyordu, ve **korumuyordu**

**Nasıl fark edildi**

Tavan (Tur 14, `c07af86`) testleriyle birlikte yeşildi: plan bazlı aylık LLM
bütçesi, Redis'te Lua ile atomik rezervasyon, sert ret, yarış koruması, Redis
kesintisinde muhafazakâr moda düşme. Sonraki tur bir **özellik** değil bir **soru**
ile başladı: *"ücretsiz kademe pratikte çalışıyor mu?"*

Cevabı bulmak için `spike-docs/` altındaki gerçek şartnameler, **üretimdeki gerçek
kod yollarıyla** (`chunk_elements` + `AGENT_INSTRUCTIONS` + `build_context_block`)
5 çağrılık ajan istemine çevrildi ve doğrulanmış Anthropic fiyatlarıyla
ücretlendirildi. Sonuç beklenenin tersi çıktı:

```
 2 sayfa → ~5,1 TL        15 sayfa → ~13,2 TL
12 sayfa → ~10,3 TL       29 sayfa → ~24,7 TL       en kötü hâl → ~94 TL
```

Sabit rezervasyon **5,0 TL** idi.

**Kök sebep neydi**

Yanlış varsayım rezervasyonun *mekanizmasında* değil, *büyüklüğünde*ydi. Yarış
koruması doğru tasarlanmıştı ama aşımın üst sınırı `eşzamanlılık × tahmin`. Tahmin
gerçeğin 2-5 katı (en kötü hâlde ~19 katı) altında kalınca **bu sınır anlamını
yitiriyor**: tavan koruyor *görünüyor*, korumuyor. Kod doğruydu, sayı yanlıştı —
ve testler sayıyı değil mekanizmayı sınıyordu.

Daha derindeki varsayım: "bir analizin maliyeti aşağı yukarı sabittir." Ölçüm bunu
da çürüttü ve **neyin ölçeklendiğini** gösterdi: ajan *bağlamı*
`RETRIEVAL_AGENT_CONTEXT_LIMIT` (12 chunk) ile tavanlı, doküman büyüdükçe büyümüyor.
Sayfayla ölçeklenen şey **bulgu sayısı** — yani çıktı token'ları ve compliance
isteminin gereksinim listesi.

**Nasıl çözüldü** (`2a2b445`)

İki bileşenli tahmin, ölçülen yapıyı izliyor:

```
tahmin = min(5,0 TL + sayfa × 0,6 TL, 60 TL)
```

`page_count` bilinmiyorsa tahmin **tavana** çıkıyor (fail-closed): bilinmeyen boyutu
ucuz saymak, tam da korunmak istenen aşımı üretirdi. Dört yeni test eklendi;
sonuncusu kademenin kâğıt üzerinde kalmasını kilitliyor: *"ücretsiz kiracı temiz
bakiyeyle 29 sayfalık tipik bir şartnameyi çalıştırabilir."*

**Sonrasında ne değişti**

Ölçüm, düzeltmesi istenmeyen ikinci bir çelişkiyi de açığa çıkardı: **plan kotaları
kendi bütçeleriyle tutarsızdı.** Ücretsiz plan 5 doküman vaat ediyordu ama 25 TL'lik
bütçesi ~3 doküman finanse ediyordu; Pro 100 doküman vaat ediyordu, 500 TL ~30
analiz finanse ediyordu. Kota kullanıcıya verilen **söz**, bütçe gerçek **kısıt** —
tutulamayan söz iptal ve iade olarak geri döner.

Zincirleme üç tur:

| Tur | Commit | Ne değişti |
|---|---|---|
| 15 | `2a2b445` | Rezervasyon tahmini sayfayla ölçekleniyor (fail-closed) |
| 16 | `956bdaa` | **Kotalar artık elle yazılmıyor, bütçeden türetiliyor**: `doküman = ⌊bütçe ÷ 8,3 TL⌋`. Ücretsiz plan 5 → **3 doküman**a düştü (vaat küçüldü, ama tutulabilir hâle geldi) |
| 16 | `ba17493` | Maliyet düşürme keşfi: maliyetin **%73'ü çıktı token'ı** — optimizasyon sırası tersine döndü, "bağlamı kısalt" en fazla %27'lik havuza dokunuyor |
| 17 | `eddc16e` | Aynı hatanın kullanıcıya bakan yüzü kapandı: `GET /usage` `reserved_try`i sabit `0.0` döndürüyordu, yani ekran "₺14 kaldı" derken sunucu reddedebiliyordu |

Ayrıca bir **yöntem** değişti: `2a2b445` sonrası ölçüm belgesi
(`docs/ops/maliyet-tavani.md`) ölçümü yeniden üretme talimatıyla birlikte yazılıyor
ve fiyat tablosundaki `verified: true` satırları `source` + `verified_at` taşımak
zorunda — taşımıyorsa kod onu **doğrulanmamış sayıyor**. Bayrağı elle çevirmek,
tavanı denetlenemez bir sayının üstüne oturtmaya yetmiyor artık.

> Bu olayın portföydeki değeri: hata "kod çalışmıyordu" değil, **"kod çalışıyordu ve
> yanlış şeyi garanti ediyordu"**. Testler yeşildi. Bulan şey test değil, ürün
> sorusuydu.

---

### İkinci aday: bağlam penceresi sessizce kırpıldı, grounding çöktü (`a42ae31`)

- **Nasıl fark edildi:** Faz 2 çıkış kapısı 3 gerçek şartname ile uçtan uca
  koşulduğunda gereksinimlerin **14'te 1'i** grounded çıktı.
- **Kök sebep:** `OLLAMA_NUM_CTX=8192` + 12 chunk'lık ajan bağlamı (~7k token) +
  `num_predict=4096` pencereyi taşırıyordu. **Ollama istemi sessizce kırpıyor** —
  hata yok, uyarı yok. Model kaynağı göremeyince grounding zorunluluğu her bulguyu
  eliyordu. Belirti "kalite düşük"tü, sebep "istem yarıda kesiliyor".
- **Nasıl çözüldü:** `Settings.effective_agent_context_limit()` — bağlam tavanı
  sağlayıcı-farkında hesaplanıyor: Ollama'da pencereye sığan chunk sayısına
  (8192/4096/1800 ⇒ **6**) otomatik kısılıyor, geniş pencereli Claude'da 12 aynen
  kalıyor.
- **Sonrasında:** grounding 1/14 → **3/6**, süre ~8 dk → **~1,5 dk/doküman**.

### Üçüncü aday: 8 turdur var olmayan bir rota (`1eae36c`)

E-posta bounce webhook'u Tur 2'de yazılmış ama `routers/v1/__init__.py`'ye hiç
eklenmemişti — sağlayıcının her bildirimi **404** alıyor, hiçbir adres
bastırılmıyordu. 8 tur sessiz kaldı çünkü uç kimliksiz ve **404, sır
yapılandırılmamış bir kurulumun BEKLENEN yanıtı** — "rota yok" ile "sır yok" ayırt
edilemiyordu. Düzeltme sadece rotayı bağlamak değildi: **bağlanmamış artefakt
denetimi** yazıldı (`test_baglanti_denetimi.py`, `test_beat_denetimi.py`) — her
router erişilebilir mi, her webhook erişilebilir mi, her sağlayıcı adaptörü fabrikaya
bağlı mı, her periyodik görev zamanlanmış mı. Kasıtlı istisnalar o dosyalarda
**gerekçesiyle** duruyor.

**[üçü de kodda yazıyor — commit gövdeleri `2a2b445`, `a42ae31`, `1eae36c`; DURUM.md §1.1/§1.4]**

---

## 7. Ekran görüntüsü hazırlığı

### Yerelde ayağa kalkıyor mu?

**Bu oturumda denemedim.** Ne durumda olduğunu ölçtüm:
`:8000` ve `:3000` kapalı; `docker ps` yalnız **başka bir projenin** (FabrikaOS)
konteynerlerini gösteriyor ve bunlar **5432 ile 6379'u tutuyor**.
**[bu oturumda ölçüldü — `docker ps`, `curl`]**

Ama proje kaydı, tam yığının **2026-07-31'de yerelde koştuğunu** belgeliyor:
Playwright 25/25 (iki ayrı yığın ayağa kaldırılarak), Lighthouse `/usage` 100/100 ve
`/usage` ekran görüntüleri **canlı backend'e karşı** (mock değil) alınmış.
**[proje kaydı — DURUM.md §3]**

**Tam komut zinciri** (`README.md:35-56` + `package.json`):

```bash
cp .env.example .env                 # 74 değişken; yerel için varsayılanlar çalışır
uv sync                              # backend (tek venv, uv workspace)
pnpm install                         # frontend
docker compose -f infra/compose/docker-compose.yml up -d postgres redis
uv run alembic upgrade head          # şema başı: 0022_llm_usage
pnpm api:dev                         # :8000  → /docs
pnpm worker:dev                      # ayrı terminal
pnpm --filter @tenderiq/web dev      # :3000
uv run python scripts/seed_e2e.py    # demo veri
```

**Bu makineye özgü üç tuzak** — ekran görüntüsü alacak kişinin bilmesi şart
**[proje kaydı — DURUM.md §1.4]**:

1. **5432/6379 dolu.** Compose override ile yan portlara alınmalı
   (`ports: !override` — `ports` listeleri normalde birleştirilir, ezilmez) ve
   `DATABASE_URL`/`REDIS_URL` oraya yönlendirilmeli. Diğer projenin konteynerlerine
   dokunulmamalı.
2. **Windows'ta `uvicorn --reload` olmadan koşulmamalı.** Reload'suz
   `ProactorEventLoop` kullanılıyor, async psycopg onunla çalışmıyor: her DB isteği
   500 veriyor, oran sınırlayıcı bunu "çok fazla deneme" 429'una çeviriyor ve gerçek
   sebep hiç görünmüyor.
3. **Dev sunucusu ayaktayken `next build` çalıştırılmamalı** — `.next` bozuluyor,
   site chunk 404'leriyle düşüyor.

### Ön koşullar — hangileri olmadan uygulama açılmıyor

| Ön koşul | Olmadan ne olur |
|---|---|
| PostgreSQL 16 + **pgvector** | Açılmaz (migration `0002` extension istiyor) |
| `alembic upgrade head` | Açılır, her istek düşer |
| Redis | Worker çalışmaz; oran sınırı ve bütçe rezervasyonu muhafazakâr moda düşer |
| `.env` (74 değişken) | Açılışta doğrulama kapısı reddeder (`instrumentation.ts` → `assertRuntimeEnv`) |
| **`NEXT_PUBLIC_STORAGE_ORIGIN`** — **derleme anında** | Üretim derlemesi **düşer**; dev'de verilmezse doküman tuvali **sessizce boş kalır** |
| S3-uyumlu depolama (R2 / MinIO) | Yükleme ve PDF önizleme çalışmaz |
| LLM anahtarı (`ANTHROPIC_API_KEY` **veya** NIM **veya** Ollama) | Yükleme/inceleme ekranları çalışır, **analiz üretilmez** |
| `LLM_USD_TRY_RATE` | Tavan fiilen yok olur (her kayıt `no_fx_rate` ile 0 TL) — açılışta `error` uyarısı düşer |
| iyzico / Resend anahtarları | **Gerekmez**: `BILLING_PROVIDER=fake`, `EMAIL_PROVIDER=memory` |

**[kodda yazıyor — `.env.example`, `apps/web/env-manifest.json`, `config.py`, DURUM.md §1.2]**

### Demo veri var mı?

**Var ve iyi durumda.** `scripts/seed_e2e.py`:

- Bilinen parolalı admin kullanıcı + kiracı + incelemeye hazır bir ihale
- **2 gereksinim + 1 risk**, hepsi kaynağa bağlı (grounded)
- **İdempotent** ve "istenen duruma getirir" (yoksa oluşturur değil): inceleme
  durumunu sıfırlıyor — aksi hâlde onay butonları yalnız ilk koşuda görünürdü
- CI'ın `a11y` job'ı bunu dinamik rotalar için gerçek ihale kimliği üretmek üzere
  zaten kullanıyor

**Eksik olan tek şey:** tohum, bulguları **doğrudan DB'ye yazıyor** — gerçek bir PDF
parse etmiyor. Yani `/tenders/[id]/review` ekranındaki **PDF tuvali ve bbox vurgusu**
için ayrıca bir PDF yüklenip hattan geçirilmesi gerekiyor. Bu, ürünün en güçlü
ekranı ve tohumla gelmiyor.

**İş tahmini:** temiz, paylaşılabilir bir demo şartnamesi üretmek (kurum adı
uydurma, 10-30 sayfa, gerçekçi madde yapısı) + tam yığından geçirmek + LLM anahtarı.
`evals/golden/sample/ornek-sartname.json` ve `spike-docs/ornek_sartname.pdf` bir
başlangıç noktası olabilir — ama `spike-docs/` **commit'lenmemiş ve gerçek
dokümanlar içeriyor**, içindeki `ornek_sartname.pdf`in gerçek mi sentetik mi olduğu
**doğrulanmalı**. **[bu oturumda ölçüldü — dosya var; içeriği açılıp kontrol edilmedi]**

### Ekran görüntüsü alınabilecek anlamlı ekranlar

Öncelik sırasıyla:

| # | Rota | Ne gösteriyor / hangi iddiayı kanıtlıyor |
|---|---|---|
| 1 | `/tenders/[id]/review` | **Ürünün tek cümlelik iddiası burada.** Bulgu listesi + orijinal PDF'te vurgulanmış kaynak + insan-döngüde onay. "Kaynağını gösteremeyen sonuç göstermeyiz" sözü ancak burada görülür. **Gerçek PDF ister.** |
| 2 | `/usage` | Bütçe ölçeri: harcanan / **rezerve** (ayrı segment, 45° tarama dokusu) / kalan + depolama + yönetici teşhis kartı. §6'daki hikâyenin görsel karşılığı — birim ekonomiyi kullanıcıya gösteren bir SaaS. Lighthouse a11y **100/100**. |
| 3 | `/tenders/[id]` | İş durumu: parse → index → extract fazları, SSE ile canlı. Bunun bir "LLM'e sor" sarmalayıcısı değil bir işleme hattı olduğunu gösterir. |
| 4 | `/panel` | Toplu genel bakış ucu (`GET /api/v1/panel` — N+1'i gidermek için yazıldı). Çok-ihaleli günlük kullanım. |
| 5 | `/capability` | Firma yetkinlik profili — uygunluk boşluğu analizinin, dokümandan çıkarılmayan tek girdisi. Ürünün "sadece özetleyici değil" tarafı. |
| 6 | `/` (landing) | Kapak görseli için. Hero'daki bulgu satırı illüstrasyon değil, ürünün gerçek bileşeni. |

**Hazır malzeme var:** `design/shots/` altında **4 viewport** (375/768/1440/1920) +
koyu tema varyantlarıyla alınmış PNG'ler duruyor — `kullanim-*` (5 durum: ilk
kullanım, normal, tavana yakın, dolu, koyu), `tur10-tenders`, `tur10-settings`,
`kayit`, `login`, `kabuk`, `abonelik-*`, `kok`, `kvkk`/`sartlar`/`trust`/`dpa`.
Dizin `.gitignore`'da ama **dosyalar diskte**. Portföy için doğrudan
kullanılabilirler; yalnız içerdikleri veri kontrol edilmeli.
**[bu oturumda ölçüldü — `ls design/shots/`]**

Ekran görüntüsü aracı hazır: `node scripts/shoot.mjs <rota> [etiket]` dört viewport'u
birden çekiyor.

### Gerçek veri riski

| Kaynak | Risk | Durum |
|---|---|---|
| `scripts/seed_e2e.py` verisi | **Yok** — uydurma kiracı, uydurma bulgular | Güvenli |
| `spike-docs/` (20 PDF) | **YÜKSEK** — gerçek kurum şartnameleri: hastane hizmet alımları, MR cihazı, güvenlik, temizlik, tıbbi sekreter. Kurum adları, ihale kayıt numaraları, personel sayıları | Ekranda **asla** görünmemeli |
| `evals/golden/private/` | **YÜKSEK** — aynı dokümanların etiketleri, doküman içeriği taşıyor | `.gitignore`'da, commit'lenmemiş |
| Yerel veritabanı | **Orta** — `0021` migration doğrulamasında "85 org / 101 kullanıcı" korunduğu yazıyor; bunlar test verisi olmalı ama gerçek e-posta adresi içerip içermediği **doğrulanmadı** | Ekran görüntüsünden önce kontrol et |
| `design/shots/` mevcut PNG'ler | **Bilinmiyor** — hangi veriyle çekildikleri dosya adından anlaşılmıyor | Portföye koymadan önce **her biri açılıp bakılmalı** |

**Kural:** demo veriyle doldurulmadan `/tenders`, `/tenders/[id]`, `/panel`
ekranlarının görüntüsü alınmamalı. `/usage`, `/capability` ve landing bu riski
taşımıyor.

---

## 8. Ölçülebilir ne varsa

| Ölçüm | Değer | Kanıt |
|---|---|---|
| Commit | 74, tek yazar | `git rev-list --count HEAD`, `git shortlog -sn` **[bu oturumda]** |
| İzlenen dosya | 460 | `git ls-files \| wc -l` **[bu oturumda]** |
| Elle yazılmış kod | ~56.806 satır (378 dosya − üretilmiş 4.996) | `git ls-files \| xargs wc -l` **[bu oturumda]** |
| Belge | 7.269 satır Markdown (37 dosya) | aynı **[bu oturumda]** |
| Test fonksiyonu (kaynak) | **518** `def test_` / 78 test dosyası | `grep -c "def test_"` **[bu oturumda]** |
| Toplanan test (pytest) | **596** — 413 unit + 183 entegrasyon, çıkış kodu 0 | DURUM.md §3, Tur 17, 2026-07-31 **[proje kaydı]** |
| Tarayıcı testi | **Playwright 25/25** (iki ayrı yığın: açık kayıt + bekleme listesi) | DURUM.md §3, 2026-07-31 **[proje kaydı]** |
| CI | **9 job / 9 yeşil** | run id `30645835860`, commit `eddc16e`, 2026-07-31 **[proje kaydı]** |
| CI kapıları | ruff · mypy strict · pytest · entegrasyon (testcontainers, RLS izolasyon kapısı) · AI golden-set regresyonu (**bloke edici, exit 2**) · OpenAPI drift · eslint/tsc/next build · Playwright · Lighthouse a11y · gitleaks · pip-audit · trivy (3 imaj) | `.github/workflows/ci.yml` **[bu oturumda okundu]** |
| Tip kapsamı | **mypy strict, 149 dosya** — `strict = true` + pydantic plugin | `pyproject.toml` + DURUM.md §3 |
| Erişilebilirlik | **18 rota × 100/100**, düşen denetim yok (dinamik rotalar dâhil) | `docs/ops/lighthouse-erisilebilirlik.md`, 2026-07-30 **[proje kaydı]** |
| Nonce CSP'nin performans bedeli | ortanca TTFB **+6 ms**, LCP **+25 ms**, skor değişmedi | aynı makinede statik-prerender taban derlemesiyle karşılaştırma, 2026-07-30 **[proje kaydı]** · *localhost — CDN kaybını ölçmüyor* |
| Veritabanı | **22 migration**, şema başı `0022_llm_usage`; `0021`in geri alınabilirliği doğrulandı (temiz DB'de upgrade→downgrade→upgrade; fonksiyon + **19 politika** birebir geri geldi) | `migrations/versions/`, DURUM.md §3 |
| Mimari karar kaydı | **13 ADR** | `docs/adr/` **[bu oturumda]** |
| Bir analizin maliyeti | 2 sayfa ~5,1 TL · 12 sayfa ~10,3 TL · 15 sayfa ~13,2 TL · 29 sayfa ~24,7 TL · en kötü ~94 TL | `2a2b445` commit gövdesi + `docs/ops/maliyet-tavani.md` §2 **[proje kaydı]** · **TAHMİN**, birebir sayılmadı — bkz. aşağıdaki uyarı |
| Ortalama analiz maliyeti | **8,3 TL/doküman** (11 gerçek şartname/form, kur 42) | `plans.py:MEASURED_AVERAGE_ANALYSIS_COST_TRY` **[kodda yazıyor]** |
| Maliyet dağılımı | **çıktı token'ı = maliyetin %73'ü** (token sayısının yalnız %35'i; $25 vs $5/Mtok) | `maliyet-tavani.md` §6.2, Tur 16 ölçümü **[proje kaydı]** |
| Plan kotaları (türetilmiş) | Ücretsiz **3 doküman / 35 sayfa / 25 TL / 500 MB** · Pro **60 doküman / 390 sayfa / 500 TL / 20 GB / 1.500 TL/ay** · Kurumsal sınırsız | `billing/plans.py` **[bu oturumda okundu]** |
| Grounding taban kalitesi (dev modeli) | requirements R=0.20 · deliverables R=0.00 · risks R=0.07 · kaynak-eşleme (sayfa) **%100** | `a42ae31` commit gövdesi, 3 gerçek şartname, qwen **[proje kaydı]** |
| Bağlam düzeltmesinin etkisi | grounding 1/14 → 3/6 · süre ~8 dk → **~1,5 dk/doküman** | `a42ae31` **[proje kaydı]** |
| TODO/FIXME | 9 işaret / 5 dosya | `grep -E "TODO\|FIXME\|HACK\|XXX"` **[bu oturumda]** |
| Kullanıcı / müşteri / gelir | **0 / 0 / 0** | Kapalı beta; `BILLING_ENV=live` hiç açılmadı |

### Bu sayıları portföyde kullanırken üç uyarı

1. **Maliyet rakamları tahmindir.** Karakter→token dönüşümü muhafazakâr bir oranla
   (2,5 kr/token) yapıldı; makinede Anthropic kimlik bilgisi olmadığı için
   `count_tokens` ile **birebir ölçüm yapılamadı**. Bulgu sayısı varsayımı
   (`sayfa × 1,4`) da ölçülmedi. **[proje kaydı — DURUM.md §1.3]**
2. **Grounding kalite sayıları dev modelinindir** (qwen), üretim modelinin (Claude)
   değil. Proje bunu bilerek böyle bırakmış: kalite kapısı yayın fazına ertelendi.
   Bu sayıları "ürünün doğruluğu" diye sunmak yanlış olur.
3. **CI ve test sayıları benim ölçümüm değil**, projenin 2026-07-31 tarihli kaydı.
   `DURUM.md` kendi başında şunu yazıyor: *"testler yeşil ifadesinin tek geçerli
   kaynağı CI koşumudur, bu dosya değil."* Portföyde kullanılacaksa run id
   `30645835860` üzerinden tazelenebilir.

---

## 9. Yayına çıkarma engelleri

### Karar vermen gereken çelişki

**Depo zaten public.** `origin` = `https://github.com/Scryne/TenderIQ.git` ve
`DURUM.md §2.1` açıkça "repo herkese açık" diyor (CI sonuçlarını kimlik doğrulaması
olmadan okuyabilmesinin sebebi bu).

**Ama README bunun tersini söylüyor:** `README.md:118` →
*"© 2026 Berkay (Scryne) · İç kullanım — ticari sırlar içerir."*

Ve **`LICENSE` dosyası yok** — yani varsayılan olarak tüm hakları saklı, kimse
kullanamaz ama herkes okuyabilir. Portföyde koda link vermeden önce bu üçünü
hizalaman gerekiyor. **[bu oturumda ölçüldü — `git remote -v`, `ls LICENSE*`]**

### Sır durumu — temiz

- `.env` **izlenmiyor** (`.gitignore`'da); depoda yalnız `.env.example` var
  **[bu oturumda ölçüldü — `git ls-files | grep .env`]**
- CI'da `gitleaks` **git geçmişini** tarıyor ve yeşil; ek olarak `pip-audit` ve
  `trivy` (3 imaj) koşuyor
- **Bu brifinge hiçbir anahtar, bağlantı dizesi veya parola girmedi.** Yalnız
  değişken *adları* geçiyor (`LLM_USD_TRY_RATE`, `NEXT_PUBLIC_STORAGE_ORIGIN` gibi) —
  değerleri **[GİZLİ]**

### Üçüncü taraf veri — dikkat

- **`spike-docs/` (20 PDF) ve `evals/golden/private/`** gerçek kamu ihale
  dokümanları içeriyor: sağlık kurumu hizmet alımları, MR cihazı teknik şartnamesi,
  güvenlik/temizlik personeli alımları, sözleşme tasarıları, yaklaşık maliyet
  formları. Bunlar kamuya açık ihale belgeleri olsa da **kurum adı ve ihale kayıt
  numarası taşıyorlar**. `.gitignore`'da ve commit'lenmemişler — bu doğru karar,
  aynen korunmalı. Portföyde **hiçbir ekran görüntüsünde görünmemeliler.**
  **[bu oturumda ölçüldü — dizin listesi + `.gitignore`]**

### Hukuki / uyumluluk

- **KVKK md. 9 yurt dışı aktarım**: ürünün çekirdek işlevi kullanıcının şartname
  **içeriğini** yurt dışındaki bir LLM sağlayıcısına göndermek. ADR-0013 bunun
  hukuki dayanağını **standart sözleşme** olarak seçmiş (açık rıza yolu, md. 9/6'nın
  "arızi olmak kaydıyla" sınırı yüzünden elenmiş). **Standart sözleşme henüz
  imzalanmış/Kurul'a bildirilmiş değil** — bu bir yayın engeli.
  **[kodda yazıyor — `docs/adr/0013-kvkk-yurt-disi-aktarim.md`]**
- **Hukuki metinler taslak.** `LEGAL_TODO.md`de **12 zorunlu alan** boş (unvan, adres,
  VKN, veri sorumlusu bilgileri vb.). Sitede KVKK/ToS/DPA/Trust sayfalarının ekran
  görüntüsü kullanılacaksa, **taslak oldukları belirtilmeli** — aksi hâlde yayımlanmış
  bir hukuki taahhüt gibi görünürler. **[proje kaydı]**
- **e-Arşiv/e-Fatura yükümlülüğü** LEGAL_TODO'da madde olarak açık (`d7466aa`).

### Müşteri işi / NDA

- **Müşteri işi değil**, kendi ürünü: 74 commit'in tamamı tek yazarda, `origin`
  kişisel hesap altında, `docs/adr/` kararları "Karar veren: Berkay (Scryne)" diyor.
- **NDA'ya işaret eden bir şey bulamadım.** Ama `spike-docs/` dosyalarının nereden
  geldiği (EKAP'tan mı indirildi, bir kurumdan mı alındı) **kodda yazmıyor** —
  bunu senin doğrulaman gerek. **[bilinmiyor]**

### Kurum içi bilgi

- `docs/ops/DURUM.md`, `docs/runbook.md`, `docs/slo.md`, `docs/guvenlik-denetimi.md`
  ve `docs/ops/maliyet-tavani.md` **operasyonel iç belgeler**. Portföy için değerli
  malzeme (özellikle maliyet ölçümü) ama içlerinde **birim ekonomi ve fiyatlandırma
  stratejisi** var: Pro'nun 1.500 TL/ay fiyatı ile 500 TL LLM bütçesi arasındaki
  marj, ücretsiz kademenin zarar sınırı, ortalama analiz maliyeti. Bunlar bir rakibe
  doğrudan bilgi verir. **Ne kadarını yayımlayacağın senin kararın** — §6'daki hikâye
  bu sayılar olmadan da anlatılabilir, ama sayılarla çok daha güçlü.
- `.mcp.json` ve `.claude/` dizini geliştirme akışını (hangi AI araçları, hangi
  skill'ler) açık ediyor. Sır içermiyor ama tercih meselesi.

### Commit'lenmemiş çalışma

Çalışma ağacında 8 dosyalık bitmemiş bir değişiklik var (CSP + depolama zinciri
düzeltmesi, `login-form.tsx` ayrıştırması). Portföy için koda link verilecekse
**önce bu commit'lenmeli veya temizlenmeli** — yarım bir çalışma ağacı `main`'de
görünmez ama yerelde `git clone` yapan biri için fark yaratmaz; asıl risk, bu
değişikliğin CI'da doğrulanmamış olması. **[bu oturumda ölçüldü — `git status`]**

---

## Ek: portföy oturumunun dolduracağı alanlar

Bu brifing kasıtlı olarak **doldurmuyor**: `slug`, `featured`, `order`, `diagram`,
`cover`, `updated`. Bunlar site geneli sıralama ve dosya yolu kararları; buradan
uydurulmuş bir yol vermek yayında kırık görsel demektir.

Proje tarafından bilinen 7 alanın özeti:

```yaml
title: TenderIQ
tagline: Türkçe ihale şartnamelerini, her bulguyu kaynak sayfasına bağlayarak analiz eden SaaS
period: 2026-07-04 – 2026-07-31 (aktif; commit'lenmemiş çalışma 2026-08-01)
role: Tek geliştirici (74/74 commit)
stack: [Next.js, FastAPI, Celery, PostgreSQL+pgvector, LangGraph, Claude, Docling/EasyOCR, Cloudflare R2]
status: GA öncesi
statusDetail: >-
  Uçtan uca akış kapalı, CI 9/9 yeşil (596 backend testi + 25 tarayıcı testi,
  2026-07-31). Yayın engelleri dış onaylarda: ödeme sağlayıcısının abonelik
  modülü hesapta kapalı, hukuki metinler taslak, staging ortamı yok.
```
