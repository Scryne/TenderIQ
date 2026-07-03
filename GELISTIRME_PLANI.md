# TenderIQ — Geliştirme Planı (Yürütme Eşlikçisi)

> **Yapay Zekâ Destekli İhale ve RFP Analiz Platformu**
> Bu belge, `TenderIQ_Proje_Plani.docx` (v1.0) stratejik ürün planının **yürütülebilir mühendislik karşılığıdır**. Stratejiyi tekrar etmez; onu somut görevlere, kabul kriterlerine, kod mimarisine ve kalite kapılarına dönüştürür.

| Alan | Değer |
|---|---|
| **Belge** | Geliştirme Planı (Engineering Execution Plan) |
| **Sürüm** | v1.0 |
| **Tarih** | Temmuz 2026 |
| **Sahip** | Berkay (GitHub: Scryne) — tek kurucu-geliştirici |
| **Kaynak plan** | `TenderIQ_Proje_Plani.docx` v1.0 (bundan sonra **"Ürün Planı"** ve `§X.Y` ile atıf) |
| **Skill haritası** | `TenderIQ_ClaudeCode_Skills.md` |
| **Durum** | Yürütmeye hazır — Faz 0 bugün başlatılabilir |
| **Hedef** | ~14 haftada MVP + kapalı beta; en riskli varsayımı (AI çıkarım doğruluğu) erken doğrulamak |

---

## İçindekiler

- [A. Giriş & Kullanım](#a-giriş--kullanım)
- [B. Mimari & Araç Zinciri](#b-mimari--araç-zinciri)
- [C. Ortak Mühendislik Standartları](#c-ortak-mühendislik-standartları)
- [D. Fazlar](#d-fazlar)
  - [Faz 0 — Temeller (Hafta 0–2)](#faz-0--temeller-hafta-02)
  - [Faz 1 — Çekirdek İşleme Hattı (Hafta 3–6)](#faz-1--çekirdek-i̇şleme-hattı-hafta-36)
  - [Faz 2 — Çıkarım & Analiz (Hafta 7–10)](#faz-2--çıkarım--analiz-hafta-710--en-kritik-faz)
  - [Faz 3 — İnceleme UI + Export + Ödeme (Hafta 11–13)](#faz-3--i̇nceleme-ui--export--ödeme-hafta-1113)
  - [Faz 4 — Beta & İlk Müşteriler (Hafta 14+)](#faz-4--beta--i̇lk-müşteriler-hafta-14)
- [E. AI Değerlendirme & Kalite Kapıları](#e-ai-değerlendirme--kalite-kapıları)
- [F. Güvenlik & KVKK Yürütme Kontrol Listesi](#f-güvenlik--kvkk-yürütme-kontrol-listesi)
- [G. Mimari Karar Kayıtları (ADR) — İlk Set](#g-mimari-karar-kayıtları-adr--i̇lk-set)
- [H. Riskler (Yürütme Odaklı)](#h-riskler-yürütme-odaklı)
- [I. Kilometre Taşları & İlk 30/60/90 Gün](#i-kilometre-taşları--i̇lk-306090-gün)
- [J. Ekler](#j-ekler)

---

## A. Giriş & Kullanım

### A.1 Amaç ve Kapsam

Ürün Planı v1.0 "ne" ve "neden" sorularını kapsamlı yanıtlıyor. Bu belge **"nasıl ve ne sırayla"** sorusunu yanıtlar: her fazı sprint'lere, sprint'leri işaretlenebilir görevlere böler; her görev için çıktı ve kabul kriteri tanımlar; kararları ADR'lerle sabitler.

**Kapsam:** MVP (v1) — belge yükleme → ayrıştırma → gereksinim/belge/risk/takvim çıkarımı → kaynak izlenebilirliğiyle inceleme → Word/Excel export → temel çok-kiracılı hesap & ödeme (Ürün Planı §3.4).
**Kapsam dışı (bu plan için):** v2 özellikleri — tam teklif üretimi, EKAP canlı entegrasyonu, gelişmiş maliyet motoru, CRM entegrasyonları (Ürün Planı §3.5, §12.7).

### A.2 v1.0 Ürün Planı ile İlişki

Bu belge Ürün Planı'nı **değiştirmez**, ona **atıfla bağlanır**. `§6.7` gibi referanslar Ürün Planı'nın ilgili bölümünü gösterir. İki belge birlikte okunur: strateji/gerekçe için Ürün Planı, yürütme için bu belge.

### A.3 Bu Belge Nasıl Kullanılır

- **İlerleme takibi:** Görevler `- [ ]` (bekliyor) / `- [x]` (tamam) kutularıyla işaretlenir. Bu dosya aynı zamanda canlı bir kanban görevi görür.
- **Faz kapısı:** Bir sonraki faza geçmeden önce, fazın **"Çıkış Kapısı"** bölümündeki ölçülebilir kriterlerin tümü sağlanmalıdır.
- **Sprint ritmi:** 2 haftalık sprint'ler; her sprint sonunda çalışan bir dikey dilim (vertical slice) hedeflenir.
- **Claude Code eşlemesi:** Her fazın başında kurulması gereken skill'ler listelenir; skill-creator ile üretilir (bkz. `TenderIQ_ClaudeCode_Skills.md`).
- **DoD:** Her görev, C.2'deki global Definition of Done'a ek olarak (varsa) yerel kabul kriterini karşıladığında "tamam" sayılır.

### A.4 Rehber İlkeler (her kararın süzgeci)

1. **Güven her şeyden önce — citation-first.** Kaynağa (sayfa + madde) bağlanamayan hiçbir bulgu üretilmez, gösterilmez, export edilmez. Grounding opsiyonel değil, **yapısal zorunluluktur** (Ürün Planı §3.6, §6.9).
2. **İnsan-döngüde.** Sistem hızlandırır, karar vermez. Her bulgu kullanıcı onayına tabidir (§4.3).
3. **Gizlilik varsayılan.** Zero-retention LLM, kiracı izolasyonu (RLS), veri minimizasyonu ilk günden mimaride (§10.3).
4. **Dar ama derin.** TR kamu BT/yazılım ihaleleri dikeyinde en iyi olmak; her yerde vasat olmaktan iyidir (§3.6).
5. **En riskli varsayımı erken doğrula.** AI çıkarım doğruluğu (kaçırılan zorunlu madde) ürünün kaderidir; Faz 0 spike + Faz 1 golden-set ile **Faz 2'den önce** ölçülebilir hâle getirilir (§16, §17.1).
6. **Maliyet bilinci.** Değişken maliyet (belge başına LLM/parsing) ilk günden Langfuse ile izlenir; OSS-önce, model yönlendirme, prompt caching (§13).

---

## B. Mimari & Araç Zinciri

### B.1 Monorepo Yapısı

Tek repo; `apps/*` ince çalıştırma giriş noktaları, ağır ve paylaşılan Python mantığı `packages/core` içinde. Bu ayrım, `api` ve `worker`'ın aynı domain modelini/servislerini paylaşmasını sağlar (Ürün Planı §5.2 bileşen sorumluluklarıyla eşlenir).

```
tender-iq/
├─ apps/
│  ├─ web/                     # Next.js (App Router) + React + TS — istemci (§7.1)
│  ├─ api/                     # FastAPI giriş noktası — REST /api/v1, auth, SSE (§5.2, §9)
│  └─ worker/                  # Celery giriş noktası — parsing/indexing/extraction (§5.5)
├─ packages/
│  ├─ core/                    # Python çekirdek (api + worker ortak):
│  │   ├─ models/              #   SQLAlchemy modelleri + tenant_id + RLS (§8)
│  │   ├─ schemas/             #   Pydantic şemaları (API + ajan I/O sözleşmeleri)
│  │   ├─ db/                  #   Session, RLS bağlamı, repository katmanı
│  │   ├─ services/            #   Domain servisleri (Document, Tender, Billing...)
│  │   ├─ llm/                 #   LLM Gateway: yönlendirme, retry, caching, Langfuse (§6.8)
│  │   ├─ parsing/             #   Hibrit parsing (Docling + VLM fallback) (§6.2)
│  │   ├─ indexing/            #   Chunking + embedding + pgvector (§6.3–6.5)
│  │   ├─ retrieval/           #   Hibrit getirim + reranker (§6.6)
│  │   └─ agents/              #   LangGraph ajanları (§6.7)
│  ├─ api-client/              # OpenAPI'dan ÜRETİLEN TypeScript istemci + tipler (web tüketir)
│  └─ prompts/                 # Versiyonlanmış prompt şablonları (Langfuse eşlemesi, §6.11)
├─ migrations/                 # Alembic — pgvector kolonları + RLS politikaları (§8.3)
├─ evals/                      # Golden set + precision/recall + LLM-as-judge (§6.10)
├─ infra/
│  ├─ docker/                  # api.Dockerfile, worker.Dockerfile, web.Dockerfile
│  └─ compose/                 # docker-compose.yml (postgres+pgvector, redis, api, worker, web)
├─ docs/
│  └─ adr/                     # Mimari Karar Kayıtları (ADR-0001 ...)
├─ scripts/                    # Yardımcı scriptler (seed, migrate, eval-run...)
├─ .github/workflows/          # ci.yml, deploy.yml (§11.3)
├─ .env.example                # Ortam değişkeni şablonu (sır İÇERMEZ)
├─ GELISTIRME_PLANI.md
├─ README.md
└─ TenderIQ_Proje_Plani.docx   # Kaynak ürün planı (değiştirilmez)
```

### B.2 Paket Sınırları ve Bağımlılık Yönü

Bağımlılıklar **tek yönlüdür** (döngü yasak):

```
apps/api    ─┐
             ├─▶ packages/core ─▶ (PostgreSQL, Redis, R2, LLM API, parsing)
apps/worker ─┘
apps/web    ─▶ packages/api-client ─▶ (apps/api OpenAPI şeması)
```

- `packages/core` HİÇBİR `apps/*`'a bağlı olamaz (framework-agnostik domain).
- `apps/api` ve `apps/worker` yalnızca ince adaptör/entrypoint içerir; iş mantığı `core`'dadır.
- `apps/web` backend'e **yalnızca** üretilen `packages/api-client` üzerinden erişir — ham `fetch` ile endpoint çağrısı yasak (drift önleme).

### B.3 Teknoloji Yığını (özet)

Tam gerekçeler Ürün Planı §7'de. Buradaki tablo yürütme için sabitlenen sürüm hedeflerini verir (kesin sürümler kilit dosyalarında sabitlenir):

| Katman | Seçim | Hedef Sürüm |
|---|---|---|
| Frontend | Next.js (App Router) + React + TypeScript | Next 15+, React 19+, TS 5.6+ |
| UI | Tailwind CSS + shadcn/ui | Tailwind 4+ |
| Veri getirme | TanStack Query | v5 |
| Doküman önizleme | react-pdf / PDF.js + vurgu katmanı | güncel |
| Backend | FastAPI (Python) | Python 3.12+, FastAPI 0.115+ |
| Async görev | Celery + Redis | Celery 5.4+, Redis 7+ |
| ORM & migrasyon | SQLAlchemy + Alembic | SQLAlchemy 2.0+ |
| Orkestrasyon | LangGraph | güncel |
| Parsing | Docling (birincil) + VLM/LlamaParse (fallback) | güncel |
| Embedding | BGE-M3 (OSS) → yönetilen opsiyon | — |
| Vektör | pgvector | PostgreSQL 16+, pgvector 0.7+ |
| Birincil LLM | Claude (Anthropic) `claude-opus-4-8` / uygun kademe | — |
| LLM gözlemleme | Langfuse | güncel |
| Nesne depolama | Cloudflare R2 (S3-uyumlu) | — |
| Auth | Auth.js (NextAuth) — başlangıç | v5 |
| Ödeme | iyzico/PayTR (TR) + Stripe (global) | — |

### B.4 Modern Araç Zinciri (2026 hızlı & tutarlı geliştirme)

| Amaç | Python (`apps/api`, `apps/worker`, `packages/core`) | Frontend (`apps/web`, `packages/api-client`) |
|---|---|---|
| Paket & ortam | **`uv`** (hızlı bağımlılık çözümü + venv + kilit) | **`pnpm`** (workspaces, disk-verimli) |
| Lint & format | **`ruff`** (lint + format tek araç) | **eslint** + **prettier** |
| Tip denetimi | **`mypy`** (strict) | **`tsc --noEmit`** (strict) |
| Birim/entegrasyon test | **`pytest`** + `pytest-asyncio` + `pytest-cov` | **Vitest** |
| E2E test | (API için httpx + testcontainers) | **Playwright** |
| Görev koşucu | `Makefile` / `uv run` scriptleri | `pnpm` scriptleri |
| Pre-commit | `pre-commit` (ruff, mypy, eslint, gitleaks) | (aynı hook) |

**İlke:** Tüm sürümler kilit dosyalarıyla sabitlenir (`uv.lock`, `pnpm-lock.yaml`). CI, kilit dosyasıyla birebir kurulum yapar (deterministik build).

### B.5 Tip-Güvenli API Sözleşmesi (OpenAPI → TS)

Backend↔frontend drift'ini yapısal olarak önlemek için tek doğruluk kaynağı FastAPI'nin ürettiği OpenAPI şemasıdır:

1. FastAPI, Pydantic modellerinden `/openapi.json` üretir.
2. CI/dev script'i `openapi-typescript` (+ opsiyonel `orval`/TanStack Query jeneratörü) ile `packages/api-client`'ı üretir.
3. `apps/web` yalnızca bu üretilen istemciyi/tipleri tüketir.
4. **CI drift kontrolü:** üretilen istemci commit'lenenle aynı değilse pipeline kırılır → şema değişince istemci güncellenmek zorunda.

### B.6 Yerel Geliştirme Ortamı

Tek komutla tam yığın: `docker compose up` → `postgres` (pgvector), `redis`, `api`, `worker`, `web`. Healthcheck'ler ve `.env` ile beslenir. Amaç: yeni ortamın dakikalar içinde ayağa kalkması (Ürün Planı §11.2).

---

## C. Ortak Mühendislik Standartları

Bu standartlar **tüm fazlarda** geçerlidir; faz görevleri bunların üzerine inşa edilir.

### C.1 Git Dallanma Modeli & Sürüm Yönetimi

- **Trunk-based**: `main` her zaman deploy-edilebilir. Kısa ömürlü `feat/*`, `fix/*`, `chore/*` dalları; PR ile birleşme.
- **PR kuralı:** CI yeşil + kendi kod incelemesi (solo dev için PR şablonundaki kontrol listesi) olmadan merge yok.
- **Commit:** Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`...). Otomatik CHANGELOG'a temel oluşturur.
- **Etiketleme:** faz sonlarında `v0.1.0-faz0` gibi anlamlı etiketler.

### C.2 Definition of Done (Global)

Bir görev, aşağıdakilerin **tümü** sağlanmadan "tamam" işaretlenmez:

- [ ] Kod yazıldı ve **lint + tip denetimi** temiz (`ruff`, `mypy`, `eslint`, `tsc`).
- [ ] **Birim/entegrasyon testleri** yazıldı ve yeşil; kritik yollarda anlamlı kapsam.
- [ ] Kiracıya-özel veri dokunuyorsa **RLS izolasyon testi** eklendi (bkz. F).
- [ ] LLM çağrısı içeriyorsa **Langfuse trace** + **grounding kontrolü** var.
- [ ] **Observability** eklendi: yapılandırılmış log + korelasyon kimliği (C.6).
- [ ] Gerekli **dokümantasyon** güncellendi (README/ADR/OpenAPI).
- [ ] CI hattı uçtan uca yeşil.

### C.3 Test Stratejisi & Piramidi

| Katman | Kapsam | Araç |
|---|---|---|
| **Birim** | saf fonksiyonlar, servisler, şema doğrulama, chunking kuralları | pytest / Vitest |
| **Entegrasyon** | DB + RLS, Celery task'ları, LLM gateway (mock), API endpoint'leri | pytest + testcontainers (Postgres+pgvector) |
| **E2E** | yükleme→işleme→inceleme→export akışı | Playwright (web) + API senaryoları |
| **AI regresyon (ayrı kapı)** | golden-set üzerinde precision/recall + kaçırılan zorunlu belge oranı | `evals/` + CI (bkz. E) |

**Kural:** AI regresyon kapısı diğer testlerden **ayrıdır**; prompt/model değişince otomatik çalışır ve kaliteyi düşüren değişikliği bloke eder (Ürün Planı §6.10, §11.3).

### C.4 CI/CD Hattı (GitHub Actions)

`.github/workflows/ci.yml` aşamaları (Ürün Planı §11.3):

1. **Setup** — `uv`/`pnpm` kilit dosyasıyla deterministik kurulum.
2. **Lint & Tip** — `ruff`, `mypy`, `eslint`, `tsc --noEmit`.
3. **API sözleşme drift** — OpenAPI→TS istemci güncel mi (B.5).
4. **Test** — birim + entegrasyon (testcontainers).
5. **AI regresyon** — golden-set (değişiklik ilgiliyse / nightly).
6. **Güvenlik taraması** — bağımlılık (pip/npm audit) + sır taraması (`gitleaks`).
7. **Build** — Docker imajları (api, worker, web) etiketlenir.

`deploy.yml`: **staging'e otomatik**, **production'a onaylı (manual approval)** dağıtım.

### C.5 Ortam & Sır Yönetimi

- **Ortam matrisi:** `development` (Docker Compose) · `staging` (üretime yakın) · `production` (§11.1).
- **`.env.example`** tüm gerekli anahtarları **değersiz** listeler; gerçek sırlar repoya **asla** girmez (`gitleaks` CI'da bekçi).
- Sırlar ortam sağlayıcısının secret store'unda (VPS/PaaS) tutulur; `packages/core` bir `Settings` (pydantic-settings) katmanıyla okur.
- **Anahtar gruplar:** DB, Redis, R2/S3, LLM API (zero-retention başlıkları dâhil), Langfuse, Sentry, Auth, ödeme sağlayıcı, webhook secret.

### C.6 Observability Standartları

- **Yapılandırılmış loglama** (JSON): her log satırında korelasyon kimlikleri — **`tenant_id`, `job_id`, `trace_id`, `request_id`**. (Sentry'e PII sızdırmadan.)
- **Sentry:** backend + frontend istisnaları; `tenant_id` bağlamı eklenir, PII maskelenir.
- **Langfuse:** her LLM çağrısı için trace/span, token maliyeti, gecikme, çıktı kalitesi (§6.11).
- **Metrik:** kuyruk derinliği, iş süreleri, işleme başarı oranı, belge başına maliyet (Prometheus/Grafana veya hosted).
- **Uptime:** erişilebilirlik izleyici + uyarı.

### C.7 Güvenlik Varsayılanları (her görevde)

- **RLS-önce:** yeni kiracı-özel tablo → aynı PR'da `tenant_id` + RLS politikası + izolasyon testi (aksi hâlde merge yok).
- **İmzalı URL:** nesne depolamaya yalnızca süre-sınırlı imzalı URL ile erişim (§10.2).
- **Zero-retention LLM:** her LLM entegrasyonunda veri-saklamama/eğitimde-kullanmama ayarı doğrulanır (§10.3).
- **En-az-yetki:** RBAC (admin/üye/izleyici), kısa ömürlü token (§10.5).
- **AuditLog:** kritik işlemler (yükleme, export, silme, rol değişimi) kim-ne-zaman kaydı (§10.5).

### C.8 Kodlama Standartları & İnceleme

- **Tip her yerde:** Python `mypy --strict`, TS `strict`. `Any` gerekçesiz kullanılmaz.
- **Şema-önce:** API ve ajan I/O'su önce Pydantic şemasıyla tanımlanır (sözleşme).
- **Küçük PR'lar:** tek sorumluluk; gözden geçirilebilir boyut.
- **Kendi-inceleme kontrol listesi** (solo dev): güvenlik (RLS/sır) · test · observability · geri-alınabilirlik · dokümantasyon.

---
## D. Fazlar

Fazlar Ürün Planı §12 ile birebir hizalıdır. Her faz aynı şablonu taşır: **Amaç & Doğrulanan Risk → Sprint kırılımı → alan-bazlı görev listeleri → Çıktılar → Çıkış Kapısı → ADR/Skill**. Süreler tam-zamanlı varsayımıdır; paralel yük varsa ölçeklenir (§12).

Görev alanı etiketleri: `Backend/API` · `AI/ML` · `Veri` · `Frontend` · `DevOps` · `Güvenlik`.

---

### Faz 0 — Temeller (Hafta 0–2)

**Amaç.** Çalışan bir iskelet + çok-kiracılı kimlik + uçtan uca dosya yükleme kurmak ve **en riskli teknik varsayımı erkenden yoklamak**: gerçek şartnamelerde parsing fizibilitesi.
**Doğrulanan Risk (§12.6).** Ortam & parsing fizibilitesi. Docling + VLM çıktısı gerçek TR şartnamelerinde yeterli mi?

#### Sprint 0.1 (Hafta 1) — İskelet, ortam, CI/CD

`DevOps`
- [ ] Monorepo iskeleti (B.1 ağacı): `apps/`, `packages/`, `infra/`, `docs/adr/`, `evals/`, `scripts/`.
- [ ] `uv` ile Python workspace (`packages/core`, `apps/api`, `apps/worker`); `pnpm` ile TS workspace (`apps/web`, `packages/api-client`).
- [ ] `ruff` + `mypy` + `pytest` (Python) ve `eslint` + `prettier` + `tsc` + `vitest` (TS) yapılandırması; `pre-commit` + `gitleaks`.
- [ ] `docker-compose.yml`: `postgres`(pgvector) + `redis` + `api` + `worker` + `web`, healthcheck'lerle. `docker compose up` tek komutla ayağa kalkar.
- [ ] `.github/workflows/ci.yml` iskeleti (C.4 aşamaları — başlangıçta lint+tip+test+build).
- [ ] `.env.example` + `Settings` (pydantic-settings) katmanı; `README.md` kurulum bölümü.

`Backend/API`
- [ ] FastAPI iskeleti: `/api/v1` router yapısı, sağlık uçları (`/healthz`, `/readyz`), tutarlı hata modeli + Pydantic error şeması (§9.1).
- [ ] Alembic kurulumu; ilk boş migration + `pgvector` extension migration'ı.

`Frontend`
- [x] Next.js 15 (App Router) + Tailwind 4 + shadcn/ui iskeleti; temel layout, tema, TanStack Query provider. Demo: tip-güvenli istemciyle canlı sistem durumu + giriş sayfası.
- [x] `packages/api-client` üretim script'i (OpenAPI→TS, `openapi-typescript` + `openapi-fetch`) ve CI drift kontrolü (B.5).

**Çıktı:** `docker compose up` ile ayağa kalkan **tam yığın** (postgres/redis/migrate/api/worker/web); üretilen tip-güvenli API istemcisi; frontend CI job'ı (lint/tip/build + api-client drift). Docker web imajı (standalone) build + servis testinden geçti.

#### Sprint 0.2 (Hafta 2) — Auth, çok-kiracılılık, yükleme, parsing spike

`Güvenlik` `Veri`
- [ ] Veri modeli çekirdeği (§8.1): `Organization(Tenant)`, `User`, `Membership/Role` + SQLAlchemy modelleri.
- [ ] **RLS temeli:** `tenant_id` konvansiyonu + PostgreSQL RLS politika şablonu; session'a `tenant_id` enjekte eden middleware (skill: `multi-tenant-fastapi`).
- [ ] **Kiracılar-arası izolasyon testi:** bir kiracının diğerinin verisini göremediğini doğrulayan entegrasyon testi (bu faz kapısının olmazsa-olmazı).

`Backend/API`
- [ ] Auth.js (NextAuth) entegrasyonu + oturum/JWT; `/api/v1` istekleri kiracı bağlamıyla yetkilendirilir (§9.1).
- [ ] RBAC iskeleti: admin/üye/izleyici; kaynak-bazlı yetki dekoratörü.
- [ ] `Document` + `Tender` modelleri; `POST /api/v1/tenders`, `POST /api/v1/tenders/{id}/documents` (imzalı URL ile yükleme başlatma).

`DevOps` `Güvenlik`
- [ ] Cloudflare R2 (S3-uyumlu) entegrasyonu; kiracı-ön-ekli yollar + **süre-sınırlı imzalı URL** (§10.2).
- [ ] Uçtan uca yükleme akışı: web'den dosya → R2 → DB'de `Document` kaydı + dosya türü/sayfa sayısı tespiti.

`AI/ML` (Spike — zaman-kutulu, ~2 gün)
- [ ] 2–3 gerçek TR şartnamesi topla (1 dijital PDF, 1 taranmış, 1 tablo-yoğun). → `spike-docs/`'a bırak.
- [x] Docling dijital parsing yolu kuruldu (`DoclingParser`, page+bbox+yapı); taranmış/VLM yolu (`do_ocr=True`) hazır — gerçek taranmışta doğrulama Faz 1'e.
- [x] **Konum koordinatı (bounding box) çıkarılabiliyor mu** doğrulandı — sentetik TR şartnamesinde **%100 bbox kapsamı** (`scripts/parsing_spike.py` + regresyon testi). Gerçek dokümanla teyit bekliyor.
- [x] Spike bulguları `docs/adr/0004-hybrid-parsing.md`'ye işlendi (Durum: Önerilen).

> **Spike durumu (2026-07-03):** Ayrıştırma harness'ı kuruldu ve dijital yolda page+bbox fizibilitesi kanıtlandı. **Kalan:** Berkay'in gerçek şartnamelerini (`spike-docs/`) çalıştırıp taranmış yolu + gerçek-doküman doğruluğunu teyit etmek (Faz 0 çıkış kapısı).

**Çıktı:** Girişten yüklemeye çalışan dikey dilim; RLS izolasyon testi yeşil; parsing fizibilite raporu.

#### Faz 0 — Çıkış Kapısı (neredeyse tamam)

- [x] `docker compose up` temiz ayağa kalkıyor (tam yığın doğrulandı: api `/healthz` 200, web 200). CI: backend+contract+frontend+security job'ları yeşil (yerelde eşdeğer koşuldu; GitHub'da `git init` sonrası çalışacak).
- [~] Kullanıcı giriş yapıp bir dosyayı R2'ye yükleyebiliyor; DB'de kiracıya bağlı kayıt oluşuyor. → Giriş UI'ı + backend uçları (imzalı-URL yükleme) hazır ve testli; **gerçek R2'ye canlı PUT Berkay'in R2 kimlik bilgilerini bekliyor.**
- [x] **Kiracılar-arası veri sızıntısı testi geçiyor** (RLS aktif) — testcontainers entegrasyon testiyle kanıtlı.
- [~] Parsing spike: **dijitalde %100 bbox kapsamı kanıtlandı**; en az bir gerçek dijital + bir taranmış şartname **Berkay'in dokümanlarını bekliyor** (`spike-docs/`). OCR yolu kod-hazır; motor kurulunca `--ocr` ile çalışır.

> **Gate kalanı (2 madde, ikisi de Berkay'in girdisine bağlı):** (1) gerçek R2 kimlik bilgileriyle canlı yükleme; (2) gerçek şartname PDF'leriyle parsing (özellikle 1 taranmış). Kod ve altyapı ikisi için de hazır.

**İlgili ADR'ler:** ADR-0001 (monorepo), ADR-0003 (RLS çok-kiracılılık), ADR-0009 (FastAPI+Celery), ADR-0010 (tip-güvenli API sözleşmesi).
**Kurulacak skill'ler:** `multi-tenant-fastapi`, `docker-compose-scaffold`, `github-actions-cicd`, `rest-api-conventions`.

---

### Faz 1 — Çekirdek İşleme Hattı (Hafta 3–6)

**Amaç.** Yüklenen dokümanı asenkron olarak **ayrıştır → parçala → gömül → indeksle** hattından geçiren, durumunu canlı yansıtan çekirdeği kurmak; ve **AI kalitesini ölçülebilir kılan golden-set'i** başlatmak.
**Doğrulanan Risk (§12.6).** İşleme hattı & ölçek; hibrit parsing gerçek çeşitlilikte çalışıyor mu.

#### Sprint 1.1 (Hafta 3) — Asenkron hat & durum makinesi

`Backend/API` `DevOps`
- [ ] Celery + Redis kuyruğu; worker giriş noktası (`apps/worker`).
- [ ] **İş durum makinesi** (§5.5): `queued → parsing → indexing → extracting → review_ready → failed`; `Job` modeli + geçiş kuralları.
- [ ] **Idempotent task tasarımı:** bir adım hata alırsa tüm işi tekrarlamadan yeniden deneme; retry/backoff (skill: `async-job-state-machine`).
- [ ] `GET /api/v1/jobs/{jobId}` durum sorgulama + `Idempotency-Key` ile yükleme güvenliği (§9.1).

`Frontend`
- [ ] **SSE canlı durum:** `GET /api/v1/tenders/{id}/stream`; TanStack Query ile senkron durum bileşeni; yeniden bağlanma mantığı (skill: `sse-live-status`).
- [ ] Yükleme sonrası ilerleme ekranı (queued→…→review_ready canlı).

#### Sprint 1.2 (Hafta 4) — Hibrit parsing + izlenebilirlik

`AI/ML`
- [ ] **Sayfa-bazlı yönlendirme:** "dijital metin var mı?" tespiti → dijital=Docling, taranmış/karmaşık=VLM/OCR (§6.2) (skill: `hybrid-document-parsing`).
- [ ] **Konum koordinatı standardı:** her `ParsedElement` için sayfa + bounding box; `ParsedElement` modeli (§8.1).
- [ ] Fallback zinciri + hata dayanıklılığı; parsing çıktısının regresyonu için test dokümanları.

`Veri`
- [ ] `ParsedElement` tablosu + ilişkiler (`Document 1—N ParsedElement`).

#### Sprint 1.3 (Hafta 5) — Chunking + embedding + pgvector

`AI/ML` `Veri`
- [ ] **Yapı-farkında chunking** (§6.3): başlık/madde/tablo sınırına göre bölme + metadata zenginleştirme (bölüm başlığı + konum) (skill: `structure-aware-chunking`).
- [ ] **BGE-M3 embedding** (OSS, çok dilli) entegrasyonu; yönetilen modele geçiş opsiyonu soyutlanır (§6.4).
- [ ] `Chunk` + `Embedding` modelleri; **pgvector indeksleme** (ivfflat/hnsw), tenant-scoped index stratejisi (§6.5) (skill: `pgvector-schema-migrations`).
- [ ] `Indexing Worker`: chunk→embedding→pgvector yazma; durum makinesine `indexing` entegrasyonu.

#### Sprint 1.4 (Hafta 6) — Golden-set & değerlendirme iskeleti

`AI/ML`
- [ ] **Golden-set v1** (§6.10): birkaç gerçek şartnameyi el ile etiketle (beklenen gereksinim/belge/risk çıktıları) — format `evals/` altında standart.
- [ ] Değerlendirme iskeleti: precision/recall + **kaçırılan zorunlu belge oranı** (kritik metrik) hesaplayan script (skill: `golden-set-eval`).
- [ ] `evals/`'i CI'a iskelet olarak bağla (Faz 2'de ajanlar gelince aktif kapı olacak).

`DevOps`
- [ ] Sentry entegrasyonu (backend/frontend); `tenant_id` bağlamı, PII maskeleme (skill: `sentry-error-tracking`).

**Çıktı:** Bir doküman yüklenince otomatik parse→chunk→embed→index olup `review_ready`'ye ulaşıyor; durum canlı izleniyor; golden-set + eval script çalışıyor.

#### Faz 1 — Çıkış Kapısı ✅

- [ ] Gerçek bir şartname (dijital **ve** taranmış) uçtan uca hattan geçip pgvector'a indeksleniyor.
- [ ] Her `ParsedElement`/`Chunk` **sayfa + konum** taşıyor (izlenebilirlik verisi hazır).
- [ ] İş durum makinesi tüm geçişleri canlı (SSE) yansıtıyor; bir adım hatasında iş idempotent şekilde yeniden denenebiliyor.
- [ ] Golden-set v1 etiketli; eval script precision/recall + kaçırılan zorunlu belge oranı üretiyor.

**İlgili ADR'ler:** ADR-0002 (pgvector), ADR-0004 (hibrit parsing), ADR-0008 (BGE-M3 embedding).
**Kurulacak skill'ler:** `async-job-state-machine`, `hybrid-document-parsing`, `structure-aware-chunking`, `pgvector-schema-migrations`, `golden-set-eval`, `sse-live-status`, `sentry-error-tracking`.

---
### Faz 2 — Çıkarım & Analiz (Hafta 7–10) — ⭐ EN KRİTİK FAZ

**Amaç.** Ürünün kalbi: RAG ile ilgili bağlamı getirip **uzmanlaşmış çıkarım ajanlarını** çalıştırmak; her bulguyu **zorunlu grounding** + şema doğrulamayla üretmek; kaliteyi ve maliyeti ölçülebilir kılmak.
**Doğrulanan Risk (§12.6).** **AI doğruluğu — projenin en kritik riski.** Kaçırılan zorunlu madde oranı kabul edilebilir mi? Grounding hallucination'ı yapısal olarak sınırlıyor mu?

> Bu faz, A.4/5. ilke gereği ürünün "yaşar mı" sorusunu yanıtlar. Çıkış Kapısı ölçütleri diğer fazlardan daha katıdır.

#### Sprint 2.1 (Hafta 7) — Hibrit getirim + orkestrasyon iskeleti

`AI/ML`
- [ ] **Hibrit getirim** (§6.6): semantic (pgvector) + anahtar kelime (BM25) birleştirme + **reranker**; ihale/mevzuat terimlerine özel test sorguları (skill: `hybrid-retrieval-rerank`).
- [ ] **LangGraph orkestrasyon iskeleti** (§6.7): durumlu, dallanabilir, yeniden denenebilir graph; ajanlar-arası bağlam paylaşımı (skill: `langgraph-extraction-agents`).
- [ ] `Extraction Orchestrator`: durum makinesine `extracting` entegrasyonu; RAG bağlamını her ajana besleme.

#### Sprint 2.2 (Hafta 8) — Çıkarım ajanları + grounding

`AI/ML`
- [ ] **Grounding altyapısı** (§6.9) — tüm ajanların temeli: her çıkarılan öğe bir kaynak `ParsedElement`'e bağlanmak **zorunda**; bağlanamayan "düşük güven" işaretlenir veya gösterilmez (skill: `structured-output-grounding`).
- [ ] **Şema zorlaması:** her ajan çıktısı önceden tanımlı Pydantic/JSON şemasına uymak zorunda; uymayan reddedilir ve yeniden istenir (tool use / structured outputs).
- [ ] **Requirement Extractor** → gereksinim listesi: metin, tip (teknik/idari/mali), zorunluluk, kaynak konum (§6.7, §8.1 `Requirement`).
- [ ] **Deliverables Extractor** → belge/sertifika/teminat listesi + kaynak (`Deliverable`).
- [ ] İlgili uçlar: `GET /api/v1/tenders/{id}/requirements`, `.../deliverables` (kaynaklarıyla).

#### Sprint 2.3 (Hafta 9) — Risk, takvim, gap analizi

`AI/ML`
- [ ] **Risk Detector** → cezai şart, olağandışı/riskli maddeler + önem derecesi + kaynak (`RiskFlag`); `GET .../risks`.
- [ ] **Timeline Extractor** → ihale tarihi, teklif son tarihi, teslim/garanti süreleri.
- [ ] **Compliance Checker** (temel gap analizi §6.7): `CapabilityProfile`'a karşı karşılanıyor/kısmi/karşılanmıyor + gerekçe (`ComplianceResult`).
- [ ] `CapabilityProfile` modeli + `GET/POST /api/v1/capability-profile` (firma yetkinlik profili).
- [ ] (Ops.) **Cost Estimator** → kaba maliyet göstergesi + varsayımlar.

`Veri`
- [ ] `Requirement`, `Deliverable`, `RiskFlag`, `ComplianceResult` tabloları; her biri `N—1` kaynak `ParsedElement` ilişkisi (§8.2).

#### Sprint 2.4 (Hafta 10) — Maliyet, gözlemlenebilirlik, eval kapısı

`AI/ML` `Güvenlik`
- [ ] **Langfuse** tam entegrasyon (§6.11): her LLM çağrısı trace + token maliyeti + gecikme; prompt versiyonlama (`packages/prompts`) (skill: `langfuse-observability`).
- [ ] **Model yönlendirme** (§6.8): basit triyaj ucuz modele, derin analiz Claude'a; **prompt caching** tekrarlayan sistem promptu + doküman bağlamı için (skill: `llm-cost-routing`).
- [ ] **Zero-retention doğrulaması** (§10.3): LLM çağrılarında veri-saklamama/no-training ayarı + veri minimizasyonu (gereksiz PII maskeleme) (skill: `zero-retention-llm-config`).
- [ ] **AI regresyon kapısını AKTİF et:** golden-set testi CI'da bloke edici hâle gelir; prompt/model değişikliği kaliteyi düşürürse pipeline kırılır (E bölümü).

**Çıktı:** Bir şartname yüklenince gereksinim + belge + risk + takvim + temel gap, **her biri kaynağa bağlı** olarak üretiliyor; maliyet ve kalite Langfuse'da izleniyor; eval kapısı aktif.

#### Faz 2 — Çıkış Kapısı ✅ (en katı)

- [ ] Golden-set üzerinde ajanlar çalışıyor ve metrikler ölçülüyor: **precision/recall + kaçırılan zorunlu belge oranı + kaynak-eşleme doğruluğu**.
- [ ] **Grounding zorunluluğu kanıtlı:** kaynağa bağlanamayan hiçbir bulgu API'den dönmüyor (test ile doğrulanıyor).
- [ ] Şema-dışı LLM çıktısı reddedilip yeniden isteniyor (test ile doğrulanıyor).
- [ ] Belge başına maliyet Langfuse'da görünüyor ve hedef marj bandında (§13.2).
- [ ] Zero-retention ayarı tüm LLM çağrılarında doğrulandı.
- [ ] AI regresyon kapısı CI'da bloke edici olarak çalışıyor.

**İlgili ADR'ler:** ADR-0005 (LangGraph), ADR-0006 (zorunlu grounding), ADR-0007 (zero-retention LLM).
**Kurulacak skill'ler:** `langgraph-extraction-agents`, `structured-output-grounding`, `hybrid-retrieval-rerank`, `langfuse-observability`, `llm-cost-routing`, `zero-retention-llm-config`.

---

### Faz 3 — İnceleme UI + Export + Ödeme (Hafta 11–13)

**Amaç.** Çıkarım sonuçlarını **kaynak izlenebilirliğiyle** insana sunmak, insan-döngüde onay/düzeltmeyi mümkün kılmak, Word/Excel export ve temel ödeme/kota ile ürünü **kullanılabilir ve gelir-hazır** hâle getirmek.
**Doğrulanan Risk (§12.6).** Kullanılabilirlik & değer; kullanıcı bulgulara güveniyor ve iş akışını tamamlıyor mu.

#### Sprint 3.1 (Hafta 11) — İnceleme ekranı + kaynak vurgusu

`Frontend`
- [ ] **İnceleme ekranı**: bulgular ↔ doküman önizleme yan yana (§4.2, §7.1).
- [ ] **Kaynak vurgusu**: react-pdf/PDF.js üzerine bounding-box vurgu katmanı; bulguya tıkla → doküman tam maddede açılıp vurgulanıyor; sayfa senkronizasyonu; yüzlerce sayfada performans (skill: `document-preview-highlight`).
- [ ] Bulgu listeleri: gereksinim/belge/risk/takvim sekmeleri; tip/zorunluluk filtreleri.

#### Sprint 3.2 (Hafta 12) — İnsan-döngüde onay + export

`Frontend` `Backend/API`
- [ ] **Onay/düzeltme akışı** (§4.3): üç durum (onay bekliyor/onaylandı/düzeltildi); optimistic update; toplu onay/red; düzenleme geçmişi (skill: `review-approval-workflow-ui`).
- [ ] `PATCH /api/v1/requirements/{id}` (ve diğer bulgu türleri) — onayla/düzelt; `AuditLog` kaydı.
- [ ] **Word/Excel export** (§4.1): onaylı analizden yapılandırılmış rapor; `POST /api/v1/tenders/{id}/export` (skill'ler: `docx`, `xlsx`).
- [ ] **`tenderiq-report-template`**: firma logosu, gereksinim/risk/belge tabloları, kaynak referansları (sayfa no) footnote olarak (proje-özel export şablonu).
- [ ] (Temel) işbirliği/yorum: ekip üyesinin bulguya not düşmesi.

#### Sprint 3.3 (Hafta 13) — Abonelik, kota, ödeme

`Backend/API` `Güvenlik`
- [ ] `Subscription` + `UsageRecord` modelleri; belge/sayfa **kota takibi**; `GET /api/v1/usage`.
- [ ] **Ödeme entegrasyonu** (§14.3): iyzico/PayTR; webhook doğrulama; abonelik↔kota senkronizasyonu; `UsageRecord` güncelleme (skill: `payment-integration-tr`).
- [ ] Kota aşımı kuralları (adil kullanım / ek ücret) ve kullanıcıya gösterim.

**Çıktı:** Kullanıcı analizi inceleyip onaylayabiliyor, Word/Excel indirebiliyor; abonelik/kota ve ödeme temel düzeyde çalışıyor.

#### Faz 3 — Çıkış Kapısı ✅

- [ ] Bulguya tıklayınca doküman **tam kaynağında** vurgulanıyor (citation-first UX kanıtlı).
- [ ] Kullanıcı bir bulguyu onaylayıp/düzeltip export edebiliyor; export'ta kaynak referansları görünüyor.
- [ ] Uçtan uca akış (yükle→işle→incele→onayla→export) E2E testte (Playwright) yeşil.
- [ ] Kota takibi + en az bir ödeme sağlayıcı (test modunda) uçtan uca çalışıyor.

**İlgili ADR'ler:** (gerekirse) ADR — export şablonu, ödeme sağlayıcı seçimi.
**Kurulacak skill'ler:** `document-preview-highlight`, `review-approval-workflow-ui`, `docx`/`xlsx` + `tenderiq-report-template`, `payment-integration-tr`.

---

### Faz 4 — Beta & İlk Müşteriler (Hafta 14+)

**Amaç.** Gerçek kullanıcılarla doğruluğu kalibre etmek, güven/uyum belgelerini yayına almak ve ilk ödeyen müşteriye geçmek.
**Doğrulanan Risk (§12.6).** Pazar/ödeme isteği; ürün gerçek dokümanlarda güven veriyor ve satın alınıyor mu.

#### Görevler

`Ürün/Beta`
- [ ] 3–5 **design partner** ile kapalı beta (§15.2); gerçek dokümanlarla doğruluk kalibrasyonu.
- [ ] Geri bildirim döngüsü: golden-set'i gerçek örneklerle genişlet; çıkarım kalitesi + UX iyileştirmeleri (kullanıcı düzeltmeleri geri-besleme verisi olur, §4.3).

`Güvenlik` `Uyumluluk`
- [ ] **Güven merkezi (trust page)**: verinin nasıl işlendiği, zero-retention, alt-işleyen listesi (§10.3) (skill: `trust-page-content`).
- [ ] **KVKK paketi** (§10.4): aydınlatma metni, açık rıza akışları, veri sahibi hakları, **kalıcı silme (hard delete) akışı** (skill'ler: `kvkk-compliance-checklist`, `soft-delete-kvkk-erasure`).
- [ ] Kurumsal müşteriler için DPA taslağı.

`Backend/API` `DevOps`
- [ ] `soft-delete` + zamanlanmış `hard-delete` job'ı; ilişkili tüm tablolarda (Document, Chunk, Embedding, ParsedElement) kademeli silme (§8.3).
- [ ] Fiyatlandırmanın canlıya alınması; production'a onaylı deploy; yedek geri-yükleme testi (§11.5).

**Çıktı:** Kapalı beta çalışıyor; trust page + KVKK/DPA yayında; en az bir ödeyen müşteriye geçiş.

#### Faz 4 — Çıkış Kapısı ✅

- [ ] En az 3 design partner gerçek dokümanlarla ürünü kullandı; kaçırılan zorunlu madde oranı hedefe yaklaştı.
- [ ] Trust page + KVKK aydınlatma + hard-delete akışı canlı ve test edilmiş.
- [ ] Ödeme canlı; ilk ödeyen müşteri (veya net sözlü taahhüt) mevcut.
- [ ] Yedeklerin periyodik geri-yükleme testi yapıldı (§11.5).

**Kurulacak skill'ler:** `kvkk-compliance-checklist`, `soft-delete-kvkk-erasure`, `trust-page-content`, `zero-retention-llm-config` (doğrulama).

---
## E. AI Değerlendirme & Kalite Kapıları

> "AI çalışıyor mu?" sorusu **ölçülebilir** olmalı (Ürün Planı §6.10, §17.1). Bu bölüm fazlar-arasıdır: Faz 1'de iskelet kurulur, Faz 2'de bloke edici kapıya döner, Faz 4'te gerçek örneklerle büyür.

### E.1 Golden-Set

- **Ne:** El ile etiketlenmiş gerçek şartname örnekleri + beklenen çıktılar (gereksinim/belge/risk/takvim + kaynak konum).
- **Nerede:** `evals/golden-set/` — her örnek: kaynak doküman + `expected.json` (şema: `packages/core/schemas`).
- **Büyüme:** Faz 1'de birkaç örnek → Faz 4'te beta dokümanları ve kullanıcı düzeltmeleriyle sürekli genişler.

### E.2 Metrikler

| Metrik | Tanım | Hedef |
|---|---|---|
| **Kaçırılan zorunlu belge/gereksinim oranı** | Beklenen zorunlu öğelerin kaçı bulunamadı | **En düşük — en kritik metrik** |
| Precision / Recall | Çıkarım doğruluğu | Yüksek; sürekli izlenir |
| Kaynak-eşleme doğruluğu | Bulgunun bağlandığı konum gerçekten doğru mu | Yüksek |
| Belge başına maliyet | Langfuse token maliyeti | Marj bandında (§13.2) |

### E.3 LLM-as-Judge & Regresyon

- **LLM-as-judge:** ölçeklenebilir otomatik kalite puanlaması için ikinci model (§6.10).
- **Regresyon kapısı (CI):** her prompt/model/parametre değişiminde golden-set otomatik koşar; kalite düşüşü pipeline'ı **bloke eder** (C.4 adım 5). Faz 2 Sprint 2.4'te aktifleşir.
- **Prompt versiyonlama:** `packages/prompts` + Langfuse; A/B karşılaştırma ve geri alma mümkün (§6.11).

---

## F. Güvenlik & KVKK Yürütme Kontrol Listesi

Güvenlik bir "özellik" değil, kurumsal satın almanın ön koşuludur (Ürün Planı §10). Aşağıdaki tehdit→önlem eşlemesi görevlere bağlanır.

| Tehdit (§10.1) | Önlem | Sahip Faz |
|---|---|---|
| Kiracılar-arası veri sızıntısı | PostgreSQL RLS + `tenant_id`; imzalı, kiracı-ön-ekli depolama | Faz 0 (+ her yeni tabloda) |
| Yetkisiz erişim | RBAC, en-az-yetki, oturum/JWT süre sınırı | Faz 0 |
| Doküman ele geçirme | At-rest + in-transit şifreleme; süre-sınırlı imzalı URL | Faz 0 |
| LLM üzerinden veri kaçağı | Zero-retention + no-training + veri minimizasyonu | Faz 2 (her LLM entegrasyonunda) |
| Bağımlılık/tedarik zinciri | CI güvenlik taraması + sabitlenmiş sürümler | Faz 0 (sürekli) |
| Sır sızması | Merkezî sır yönetimi; `gitleaks`; repoda sır yok | Faz 0 (sürekli) |

**Tekrarlayan güvenlik kuralları (her PR'da):**
- [ ] Yeni kiracı-özel tablo → `tenant_id` + RLS politikası + izolasyon testi **aynı PR'da**.
- [ ] Yeni LLM çağrısı → zero-retention doğrulandı + veri minimizasyonu.
- [ ] Yeni dosya erişimi → yalnızca imzalı, süre-sınırlı URL.
- [ ] Kritik işlem (yükleme/export/silme/rol) → `AuditLog` kaydı.

**KVKK (Faz 4 öncesi tasarımdan itibaren akılda, §10.4):** aydınlatma metni · açık rıza · veri sahibi hakları · **hard-delete akışı** · saklama süreleri + otomatik temizlik · alt-işleyen listesi · DPA.

---

## G. Mimari Karar Kayıtları (ADR) — İlk Set

`docs/adr/` altında, her biri kısa formatla (Bağlam · Karar · Gerekçe · Alternatifler · Sonuç · Durum). Başlangıçta hepsi **Durum: Önerilen/Kabul**; ölçek büyüdükçe yeniden değerlendirilir.

| ADR | Karar | Özet gerekçe | Yükseltme yolu |
|---|---|---|---|
| **0001** | Monorepo (apps + packages) | Solo dev için tek CI/sürüm, kolay paylaşım | Gerekirse paket ayrıştırma |
| **0002** | pgvector (özel vektör DB yerine) | Birleşik yığın, düşük operasyonel yük; MVP'ye yeterli (§6.5) | Ölçekte Qdrant'a taşıma |
| **0003** | Çok-kiracılılık = tenant_id + RLS | Tek şema + güçlü DB-katmanı izolasyon (§5.4) | Şema/DB-per-tenant |
| **0004** | Hibrit parsing (Docling + VLM fallback) | Ücretsiz OSS + zor girdide yüksek doğruluk (§6.2) | Tümüyle yönetilen/self-host |
| **0005** | LangGraph orkestrasyon | Durumlu, dallanabilir, yeniden denenebilir ajan akışı (§6.7) | — |
| **0006** | Zorunlu grounding | Kaynaksız bulgu gösterilmez — güvenin yapısal temeli (§6.9) | (değişmez ilke) |
| **0007** | Zero-retention LLM | Hassas doküman gizliliği; no-training (§10.3) | Self-host/yerel model |
| **0008** | BGE-M3 embedding (OSS) | Çok dilli, maliyet-hassas, Türkçe iyi (§6.4) | Yönetilen embedding |
| **0009** | FastAPI + Celery/Redis | Async-önce API + olgun kuyruk; mevcut deneyim (§7.2) | — |
| **0010** | Tip-güvenli API sözleşmesi (OpenAPI→TS) | Backend↔frontend drift'ini yapısal önleme (B.5) | — |

---

## H. Riskler (Yürütme Odaklı)

Ürün Planı §16 riskleri → bu plandaki azaltıcı görevlere ve fazlara bağlanır.

| Risk | Etki | Yürütmedeki azaltma | Nerede |
|---|---|---|---|
| Çıkarım doğruluğu yetersiz (kaçırılan zorunlu madde) | Yüksek — güven çöker | Grounding zorunluluğu + insan-döngüde + golden-set/regresyon; en kritik metrik olarak takip | Faz 1 eval → **Faz 2 kapısı** |
| LLM hallucination | Yüksek | Kaynaksız iddia gösterilmez + şema doğrulama | Faz 2 (ADR-0006) |
| Veri gizliliği / güven bariyeri | Yüksek | Zero-retention + KVKK/DPA + trust page + (ileri) self-host | Faz 2 + Faz 4 |
| LLM/işleme maliyeti marjı bozar | Orta-Yüksek | Model yönlendirme + prompt caching + OSS parsing + kota bazlı fiyat | Faz 2 Sprint 2.4 |
| Tek geliştirici bant genişliği | Orta-Yüksek | Dar MVP + hazır altyapı + faz planı + CI/CD otomasyonu | Tüm fazlar |
| Yavaş benimseme / güven eksikliği | Orta | Design partner referansları + demo + ROI mesajı | Faz 4 |
| Rekabet (global oyuncu TR'ye girer) | Orta | Yerel mevzuat + dil + fiyat hendeği; hız + dikey derinlik | Strateji (§2.4) |
| Doküman format kaosu | Orta | Hibrit parsing + golden-set genişletme + kullanıcı düzeltmesi geri-beslemesi | Faz 1 + Faz 4 |

---

## I. Kilometre Taşları & İlk 30/60/90 Gün

Ürün Planı §18 ile hizalı somut kontrol noktaları.

| Kilometre taşı | Faz | Kanıt |
|---|---|---|
| **M0 — İskelet & Yükleme** | Faz 0 sonu | `docker compose up` + RLS izolasyon testi + parsing spike raporu |
| **M1 — Çekirdek Hat** | Faz 1 sonu | Doküman uçtan uca indeksleniyor + golden-set/eval çalışıyor |
| **M2 — AI Doğruluğu Kanıtı** | Faz 2 sonu | Grounding'li çıkarım + ölçülen metrikler + aktif regresyon kapısı |
| **M3 — Kullanılabilir Ürün** | Faz 3 sonu | İnceleme+kaynak vurgusu + export + ödeme; E2E yeşil |
| **M4 — İlk Müşteri** | Faz 4 | Kapalı beta + trust/KVKK + ilk ödeyen müşteri |

**İlk 30 Gün:** Repo + CI/CD + Docker + auth/çok-kiracılılık iskeleti · uçtan uca yükleme & R2 · 3–5 gerçek şartname ile parsing spike · ilk golden-set etiketleme + eval iskeleti.
**İlk 60 Gün:** Asenkron hat + indeksleme + hibrit parsing · ilk çıkarım ajanları (gereksinim + belge) + grounding · Langfuse ile maliyet/kalite ölçümü.
**İlk 90 Gün:** Risk + takvim + temel gap ajanları · inceleme ekranı + kaynak vurgusu + Word/Excel export · ödeme/kota temel + ilk design partner ile kapalı beta.

---

## J. Ekler

### J.1 Skill Kurulum Sırası (özet)

`TenderIQ_ClaudeCode_Skills.md` ile birebir eşlenir:

1. **Faz 0:** `multi-tenant-fastapi`, `docker-compose-scaffold`, `github-actions-cicd`, `rest-api-conventions`.
2. **Faz 1:** `hybrid-document-parsing`, `structure-aware-chunking`, `pgvector-schema-migrations`, `async-job-state-machine`, `golden-set-eval`, `sse-live-status`, `sentry-error-tracking`.
3. **Faz 2:** `langgraph-extraction-agents`, `structured-output-grounding`, `hybrid-retrieval-rerank`, `langfuse-observability`, `llm-cost-routing`, `zero-retention-llm-config`.
4. **Faz 3:** `document-preview-highlight`, `review-approval-workflow-ui`, `docx`/`xlsx` + `tenderiq-report-template`, `payment-integration-tr`.
5. **Faz 4:** `kvkk-compliance-checklist`, `soft-delete-kvkk-erasure`, `trust-page-content`.

### J.2 Tekrar Kullanılabilir Kontrol Listesi Şablonları

**Yeni tablo eklerken:** `tenant_id` kolonu → RLS politikası → izolasyon testi → Alembic migration → soft-delete alanı (gerekiyorsa).
**Yeni çıkarım ajanı eklerken:** Pydantic çıktı şeması → grounding (kaynak konum zorunlu) → şema-dışı çıktı reddi → golden-set beklentisi → Langfuse trace → regresyon testi.
**Yeni endpoint eklerken:** `/api/v1` altında → Pydantic request/response + hata şeması → kiracı yetki kontrolü → (yazma ise) `Idempotency-Key` → OpenAPI güncel → `api-client` yeniden üretim → AuditLog (kritikse).

### J.3 Terimler

Terim sözlüğü için Ürün Planı **Ek A**'ya bakınız (RFP, EKAP, Parsing, OCR, VLM, Chunking, Embedding, RAG, Grounding, RLS, RBAC, Zero-retention, KVKK, MRR/NRR/CAC/LTV).

### J.4 Kaynak Belgeler

- `TenderIQ_Proje_Plani.docx` — v1.0 stratejik ürün ve teknik plan (bu belgenin kaynağı).
- `TenderIQ_ClaudeCode_Skills.md` — faz-bazlı Claude Code skill haritası.

---

> **Tek cümlelik yürütme özeti:** Dar bir dikeyde (TR kamu BT/yazılım ihaleleri), kaynağına kadar izlenebilir ve KVKK-uyumlu bir AI şartname analiz aracıyla başla; **AI doğruluğunu Faz 2'de ölçülebilir biçimde kanıtla**; sabit maliyeti düşük tutup ilk ödeyen müşterilerle finanse ederek büyü.

*TenderIQ — Geliştirme Planı v1.0 · Temmuz 2026 · Berkay (Scryne). Kaynak: TenderIQ Proje Planı v1.0.*
