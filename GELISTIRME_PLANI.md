# TenderIQ — Geliştirme Planı (Yürütme Eşlikçisi)

> **Yapay Zekâ Destekli İhale ve RFP Analiz Platformu**
> Bu belge, `TenderIQ_Proje_Plani.docx` (v1.0) stratejik ürün planının **yürütülebilir mühendislik karşılığıdır**. Stratejiyi tekrar etmez; onu somut görevlere, kabul kriterlerine, kod mimarisine ve kalite kapılarına dönüştürür.

| Alan | Değer |
|---|---|
| **Belge** | Geliştirme Planı (Engineering Execution Plan) |
| **Sürüm** | v1.1 — Faz 0 kapanışı + kod denetimi bulguları + yayına-alma (production-readiness) yol haritası eklendi |
| **Tarih** | Temmuz 2026 (v1.1: 2026-07-08) |
| **Sahip** | Berkay (GitHub: Scryne) — tek kurucu-geliştirici |
| **Kaynak plan** | `TenderIQ_Proje_Plani.docx` v1.0 (bundan sonra **"Ürün Planı"** ve `§X.Y` ile atıf) |
| **Skill haritası** | `TenderIQ_ClaudeCode_Skills.md` |
| **Durum** | **Faz 2 Çıkış Kapısı doğrulandı 🟡 → Faz 3'e hazır** (2026-07-19: 3 gerçek şartname qwen ile uçtan uca koştu; makine [parse→index→retrieve→ajan→grounding→bulgu→API] + grounding zorunluluğu + şema-ret + zero-retention + bloke edici eval kapısı [exit 2] doğrulandı; `scripts/faz2_gate_check.py`. **Bulunan+düzeltilen bug:** Ollama'da sessiz bağlam kırpması → sağlayıcı-farkında `effective_agent_context_limit` [num_ctx=8192 ⇒ 6 chunk]; grounding 1/14→3/6, süre ~8→~1.5 dk/dok. **qwen baseline** kayıtlı [recall<0.8, kaçırılan-zorunlu=1.0 — beklenen]; kalite/maliyet kapısı Claude yayın fazına bilinçli ertelendi). **Model stratejisi:** dev/test boyunca qwen2.5 birincil; model yönlendirme + prompt caching + kalite kalibrasyonu yayın (Claude) fazında. — sıradaki: **Faz 3 — İnceleme UI + Export + Ödeme** |
| **Hedef** | ~14 haftada MVP + kapalı beta; en riskli varsayımı (AI çıkarım doğruluğu) erken doğrulamak; ardından J bölümüyle **yayınlanabilir (GA) SaaS** |

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
- [J. Yayına Alma — Production-Readiness Yol Haritası](#j-yayına-alma--production-readiness-yol-haritası)
- [K. Ekler](#k-ekler)

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
| Auth | **Backend-JWT (FastAPI + PyJWT + Argon2)** — Faz 0'da uygulanan yol; refresh/oturum sertleştirmesi Faz 3 (bkz. J.2). Auth.js yalnızca web-oturum katmanı olarak Faz 3'te yeniden değerlendirilir | — |
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
- [x] Monorepo iskeleti (B.1 ağacı): `apps/`, `packages/`, `infra/`, `docs/adr/`, `evals/`, `scripts/`.
- [x] `uv` ile Python workspace (`packages/core`, `apps/api`, `apps/worker`); `pnpm` ile TS workspace (`apps/web`, `packages/api-client`).
- [x] `ruff` + `mypy` + `pytest` (Python) ve `eslint` + `prettier` + `tsc` (TS) yapılandırması; `pre-commit` + `gitleaks`. (Vitest: web'e ilk birim test ihtiyacıyla — Faz 1.)
- [x] `docker-compose.yml`: `postgres`(pgvector) + `redis` + `migrate` + `api` + `worker` + `web`, healthcheck'lerle. `docker compose up` tek komutla ayağa kalkar. (2026-07-08: `api` healthcheck + `web`→`api` sağlıklı-bağımlılık eklendi.)
- [x] `.github/workflows/ci.yml` (C.4 aşamaları: lint+tip+migration+test+drift+güvenlik). (2026-07-08: entegrasyon/RLS testleri CI'da zorunlu adım yapıldı.)
- [x] `.env.example` + `Settings` (pydantic-settings) katmanı; `README.md` kurulum bölümü. (2026-07-08: production fail-fast guard — zayıf/eksik `AUTH_SECRET` ve `DEBUG=true` ile prod açılışı engellenir.)

`Backend/API`
- [x] FastAPI iskeleti: `/api/v1` router yapısı, sağlık uçları (`/healthz`, `/readyz`), tutarlı hata modeli + Pydantic error şeması (§9.1).
- [x] Alembic kurulumu; ilk boş migration + `pgvector` extension migration'ı.

`Frontend`
- [x] Next.js 15 (App Router) + Tailwind 4 + shadcn/ui iskeleti; temel layout, tema, TanStack Query provider. Demo: tip-güvenli istemciyle canlı sistem durumu + giriş sayfası.
- [x] `packages/api-client` üretim script'i (OpenAPI→TS, `openapi-typescript` + `openapi-fetch`) ve CI drift kontrolü (B.5).

**Çıktı:** `docker compose up` ile ayağa kalkan **tam yığın** (postgres/redis/migrate/api/worker/web); üretilen tip-güvenli API istemcisi; frontend CI job'ı (lint/tip/build + api-client drift). Docker web imajı (standalone) build + servis testinden geçti.

#### Sprint 0.2 (Hafta 2) — Auth, çok-kiracılılık, yükleme, parsing spike

`Güvenlik` `Veri`
- [x] Veri modeli çekirdeği (§8.1): `Organization(Tenant)`, `User`, `Membership/Role` + SQLAlchemy modelleri.
- [x] **RLS temeli:** `tenant_id` konvansiyonu + PostgreSQL RLS politika şablonu (`FORCE ROW LEVEL SECURITY`, fail-closed); transaction-local `set_config` ile kiracı bağlamı (skill: `multi-tenant-fastapi`). Uygulama non-superuser `tenderiq_app` rolüyle bağlanır (ADR-0003).
- [x] **Kiracılar-arası izolasyon testi:** testcontainers ile DB-katmanı + API-katmanı izolasyon testleri yeşil (2026-07-08'den itibaren CI'da zorunlu adım).

`Backend/API`
- [x] ~~Auth.js (NextAuth)~~ → **Backend-JWT auth uygulandı** (bilinçli sapma): `/auth/register|login|me`, Argon2 parola özeti, HS256 JWT (user+tenant+rol claim'leri). Gerekçe: API-öncelikli tek doğruluk kaynağı, worker/API simetrisi. Oturum sertleştirmesi (refresh/iptal) J.2'de planlı.
- [x] RBAC iskeleti: admin/üye/izleyici; `require_role` bağımlılığı ile kaynak-bazlı yetki.
- [x] `Document` + `Tender` modelleri; `POST /api/v1/tenders`, `POST /api/v1/tenders/{id}/documents` (imzalı URL ile yükleme başlatma).

`DevOps` `Güvenlik`
- [x] Cloudflare R2 (S3-uyumlu) entegrasyonu; kiracı-ön-ekli yollar + **süre-sınırlı imzalı URL** (§10.2). (2026-07-08: istemci dosya adı `safe_key_component` ile temizlenerek anahtara yazılır.)
- [x] Uçtan uca yükleme akışı (backend): imzalı-URL round-trip gerçek R2'de doğrulandı. **Kalan parçalar Faz 1'e taşındı:** web yükleme UI'ı, yükleme-tamamlama ucu (`status=uploaded`, boyut/sayfa tespiti), dosya türü/boyut doğrulaması.

`AI/ML` (Spike — zaman-kutulu, ~2 gün)
- [x] **24 gerçek TR şartnamesi** toplandı (`spike-docs/`; dijital + taranmış + tablo-yoğun karışımı).
- [x] Docling dijital parsing yolu kuruldu (`DoclingParser`, page+bbox+yapı); taranmış/VLM yolu (`do_ocr=True`) **gerçek taranmış dokümanla doğrulandı** (EasyOCR `tr,en`).
- [x] **Konum koordinatı (bounding box) çıkarılabiliyor mu** doğrulandı — **7 gerçek dijital + 2 gerçek taranmış** şartnamede **%100 bbox kapsamı** (`scripts/parsing_spike.py` + regresyon testi).
- [x] Spike bulguları `docs/adr/0004-hybrid-parsing.md`'ye işlendi (Durum: **Kabul**).

> **Spike durumu (2026-07-04):** Gerçek dokümanlarla dijital **ve** taranmış yol doğrulandı; ikisinde de **%100 bbox**. **Kritik bulgu:** korpusun **~%54'ü taranmış** → OCR çoğunluk yol. Türkçe OCR kalitesi tarama kalitesine bağlı (gürültülüde VLM fallback gerekli — ADR-0004 doğrulandı). Perf: dev'de CPU OCR ~20 sn/sayfa → Faz 1'de GPU/yönetilen kararı.

**Çıktı:** Girişten yüklemeye çalışan dikey dilim; RLS izolasyon testi yeşil; parsing fizibilite raporu.

#### Faz 0 — Çıkış Kapısı ✅ TAMAM (2026-07-04)

- [x] `docker compose up` temiz ayağa kalkıyor (tam yığın doğrulandı: api `/healthz` 200, web 200). CI: backend+contract+frontend+security job'ları yeşil (yerelde eşdeğer koşuldu; GitHub'da `git init` sonrası çalışacak).
- [x] Kullanıcı giriş yapıp bir dosyayı R2'ye yükleyebiliyor; DB'de kiracıya bağlı kayıt oluşuyor. → Giriş UI'ı + backend uçları (imzalı-URL yükleme) hazır ve testli; **gerçek R2'ye canlı round-trip doğrulandı** (imzalı PUT 200 → GET 200 içerik eşleşti → temizlik; `StorageService` gerçek yolu).
- [x] **Kiracılar-arası veri sızıntısı testi geçiyor** (RLS aktif) — testcontainers entegrasyon testiyle kanıtlı.
- [x] Parsing spike **tamam**: 7 gerçek dijital + 2 gerçek taranmış şartnamede **%100 bbox kapsamı**; hibrit yönlendirme (dijital=Docling, taranmış=OCR) gerçek dokümanlarda çalışıyor. Korpusun ~%54'ü taranmış (bkz. ADR-0004 gerçek-doküman bulguları).

> **Faz 0 kapandı (2026-07-04):** Dört kapı maddesi de yeşil — tam yığın, RLS izolasyonu, parsing (dijital+taranmış, %100 bbox), R2 canlı yükleme. Yan bulgu: `.env`'den `CORS_ORIGINS` (virgülle ayrılmış) yüklemesini bloke eden pydantic-settings JSON-decode bug'ı düzeltildi (`config.py`, `NoDecode`). **Sıradaki:** Faz 1 Sprint 1.1 (asenkron işleme hattı + iş durum makinesi).

#### Faz 0 — Kapanış Denetimi & Sertleştirme (2026-07-08) ✅

Faz 0 kapanışının ardından kod tabanı uçtan uca denetlendi (güvenlik + doğruluk + CI).
Bulunan tüm bulgular aynı gün düzeltildi ve testle kanıtlandı (19 birim + 5 entegrasyon testi yeşil):

- [x] **Pasif kullanıcı girişi (güvenlik bug'ı):** `is_active=false` kullanıcı, parolası doğruysa giriş yapabiliyordu → `authenticate` artık pasif kullanıcıyı reddediyor (+ entegrasyon testi).
- [x] **JWT şema uyumsuzluğu → 500:** imzası geçerli ama şeması eksik token (ör. `tenant_id` yok) pydantic hatasıyla 500 üretiyordu → `InvalidTokenError`'a sarılıp 401'e eşleniyor; `exp` claim'i artık zorunlu (+2 birim test).
- [x] **Kayıt yarış durumu → 500:** eşzamanlı aynı e-posta/slug kaydında unique kısıt `IntegrityError` 500 dönüyordu → 409 `conflict`'e eşlendi.
- [x] **Kullanıcı numaralandırma yan-kanalı:** e-posta yokken parola özeti doğrulanmadığından yanıt süresi farkı oluşuyordu → dummy-hash ile zamanlama eşitlendi.
- [x] **Depolama anahtarında ham dosya adı:** `a/../b.pdf` gibi girdiler anahtara sızabiliyordu → `safe_key_component` (yol ayraçları/kontrol karakterleri temizlenir; orijinal ad DB'de kalır) (+4 birim test).
- [x] **CI, RLS testlerini hiç koşmuyordu:** `pytest` varsayılanı `-m 'not integration'` olduğundan Faz 0'ın kalbi olan izolasyon testleri CI dışındaydı → backend job'ına zorunlu `pytest -m integration` adımı eklendi (testcontainers).
- [x] **`readyz` her çağrıda yeni engine açıyordu** → uygulamanın havuzlu engine'i yeniden kullanılıyor.
- [x] **Production fail-fast guard:** prod ortamında eksik/kısa (<32 karakter) `AUTH_SECRET` veya `DEBUG=true` ile açılış artık `Settings` doğrulamasında engellenir (+3 birim test).
- [x] **Compose sertleştirme:** `api` servisine healthcheck; `web`, `api` sağlıklı olmadan başlamaz.

> Denetimde tespit edilip **bilinçli olarak faz planına taşınan** (bugün düzeltilmeyen) kalemler J.2 Güvenlik Sertleştirme Backlog'undadır: refresh token/oturum iptali, login rate-limit, e-posta doğrulama, çoklu-organizasyon seçimi, upload tamamlama ucu, AuditLog.

**İlgili ADR'ler:** ADR-0001 (monorepo), ADR-0003 (RLS çok-kiracılılık), ADR-0009 (FastAPI+Celery), ADR-0010 (tip-güvenli API sözleşmesi).
**Kurulacak skill'ler:** `multi-tenant-fastapi`, `docker-compose-scaffold`, `github-actions-cicd`, `rest-api-conventions`.

---

### Faz 1 — Çekirdek İşleme Hattı (Hafta 3–6)

**Amaç.** Yüklenen dokümanı asenkron olarak **ayrıştır → parçala → gömül → indeksle** hattından geçiren, durumunu canlı yansıtan çekirdeği kurmak; ve **AI kalitesini ölçülebilir kılan golden-set'i** başlatmak.
**Doğrulanan Risk (§12.6).** İşleme hattı & ölçek; hibrit parsing gerçek çeşitlilikte çalışıyor mu.

#### Sprint 1.1 (Hafta 3) — Asenkron hat & durum makinesi ✅ (2026-07-16)

`Backend/API` `DevOps`
- [x] Celery + Redis kuyruğu; worker giriş noktası (`apps/worker`) — task ad/kuyruk sözleşmesi `packages/core/queueing.py`'de; API worker kodunu import etmeden `send_task` ile yayınlar.
- [x] **İş durum makinesi** (§5.5): `queued → parsing → indexing → extracting → review_ready → failed`; `Job` modeli + geçiş kuralları (`transition_to`, tanımsız geçiş → hata; `failed → queued` yeniden kuyruklama). Migration `0004_job_audit_log` (RLS dahil).
- [x] **Idempotent task tasarımı:** her faz kendi transaction'ında; task yeniden çalıştığında kaldığı fazdan devam eder (entegrasyon testiyle kanıtlı); retry/backoff (üstel, 5→300 sn, 5 deneme; tükenince `failed` + hata mesajı).
- [x] `GET /api/v1/jobs/{jobId}` durum sorgulama + `Idempotency-Key` ile yükleme güvenliği (tenant+key unique; aynı anahtar mevcut kaydı taze imzalı URL ile döndürür).

`Backend/API` `Güvenlik` (Faz 0 denetiminden devralınan yükleme sertleştirmesi)
- [x] **Yükleme tamamlama ucu:** `POST /api/v1/documents/{id}/complete` — HEAD doğrulama, `size_bytes`, `pending_upload → uploaded`, job kuyruklama (commit SONRASI — görünürlük yarışı yok). Zamanlanmış temizlik: `cleanup_stale_uploads` beat task'ı (saatlik; `pending_upload` > 24 saat → `failed`; RLS gereği kiracı kiracı dolaşır).
- [x] **Dosya doğrulama:** PDF/DOCX/XLSX allowlist (kayıt anında), maksimum boyut (`UPLOAD_MAX_SIZE_BYTES`, 100 MB), magic-bytes kontrolü (ranged GET); doğrulamayı geçemeyen nesne depodan silinir.
- [x] **`AuditLog` modeli + kaydı:** tender/doküman oluşturma, yükleme tamamlama/red; RLS yalnızca SELECT+INSERT (append-only — uygulama rolü kayıt değiştiremez/silemez).
- [x] **Login rate-limit / brute-force koruması:** IP (20/5 dk) + e-posta (5/5 dk) sayaçları (Redis, `429 rate_limited` + `Retry-After`); register dahil; Redis kesintisinde fail-open (loglanır).

`Frontend`
- [x] **Web yükleme UI'ı:** `/tenders` (liste+oluştur) ve `/tenders/[id]` (dosya seç → imzalı PUT → complete); tür seçimi, hata mesajları.
- [x] **SSE canlı durum:** `GET /api/v1/tenders/{id}/stream` (DB poll, değişimde `status` event, heartbeat, `max_ticks` ömür tavanı); web'de `useTenderStream` hook'u — kopunca 3 sn'de yeniden bağlanır.
- [x] Yükleme sonrası ilerleme ekranı (queued→…→review_ready canlı adım göstergesi; hata durumu mesajıyla).
- [x] **Oturum saklama:** token httpOnly cookie'de (`/api/session` route handler'ı yazar; JS token'ı hiç görmez); tüm API çağrıları aynı-origin `/api/v1/[...path]` proxy'sinden (cookie→Authorization çevirisi, SSE dahil akış geçirme); `middleware.ts` korumalı sayfa yönlendirmesi.

> **R2 CORS gereksinimi (2026-07-16):** Tarayıcı imzalı URL'e doğrudan PUT yaptığı için R2 bucket'ında CORS kuralı şarttır (yoksa "Failed to fetch"): `AllowedOrigins` içinde web origin'i (dev: `http://localhost:3000`; staging/prod alan adları J.1'de eklenecek), `AllowedMethods: PUT,GET,HEAD`, `AllowedHeaders: content-type`. `.env`'deki nesne-kapsamlı token bucket ayarı değiştiremez (PutBucketCors → AccessDenied) — kural Cloudflare panelinden yönetilir.
>
> **Sprint 1.1 kapanış notları (2026-07-16):** (1) `RequestContextMiddleware`, `BaseHTTPMiddleware`'den saf ASGI'ye çevrildi — BaseHTTPMiddleware `http.disconnect`'i SSE generator'ına iletmiyordu (test 4 saat asılı kaldı); ayrıca SSE akışına sunucu taraflı ömür tavanı (`max_ticks`, ~15 dk) eklendi ve `pytest-timeout` (300 sn) devrede. (2) Web artık backend'e CORS ile değil aynı-origin Next proxy'siyle konuşur; compose'da web servisine runtime `API_URL=http://api:8000` eklendi. (3) Test durumu: 53 birim + 8 entegrasyon yeşil (uçtan uca akış: kayıt→tender→doküman→complete→pipeline→SSE→RLS izolasyonu; magic-bytes reddi; ara durumdan devam; süpürme task'ı).

#### Sprint 1.2 (Hafta 4) — Hibrit parsing + izlenebilirlik ✅ (2026-07-16)

`AI/ML`
- [x] **Sayfa-bazlı yönlendirme:** "dijital metin var mı?" tespiti (`routing.py`, pypdf) → tümü dijital=Docling(`do_ocr=False`); tek taranmış sayfa bile OCR yolunu açar (`do_ocr=True` yalnız bitmap alanları OCR'lar → dijital sayfalar programatik metnini korur = fiilen sayfa-bazlı rota). `HybridDocumentParser` (`hybrid.py`); öğeler sayfa bazında `digital/scanned` kaynağıyla işaretlenir.
- [x] **OCR paketleme & dil:** **EasyOCR** bildirilmiş bağımlılık (`packages/core` extras: `parsing`/`ocr`; kök gruplar bunları işaret eder; worker imajı `--group parsing --group ocr` ile kurulur — API imajı hafif kalır). `DoclingParser`'a `ocr_lang` parametresi; `PARSING_OCR_LANGUAGES` ayarı (varsayılan `tr,en`). Motor + **GPU vs yönetilen karar → ADR-0011** (CPU-önce; GA öncesi GPU worker; yönetilen/VLM fallback opsiyon).
- [x] **Konum koordinatı standardı:** her öğe sayfa + bbox (TOPLEFT origin) + kaynak; `ParsedElement` ORM modeli (§8.1) parse sözleşmesiyle aynı enum'ları kullanır.
- [x] Fallback zinciri + hata dayanıklılığı: dijital → OCR → (Faz 2'de takılacak) VLM; kalite kapısı = boş çıktı reddi + PDF'te ≥%90 bbox kapsamı; zincir tükenirse `DocumentParsingError` → worker retry/backoff → `failed`. Regresyon: sentetik PDF'lerle birim + docling entegrasyon testleri (gerçek şartnameler KVKK gereği repoya giremez; spike-docs ile elle doğrulanır).

`Veri`
- [x] `parsed_element` tablosu (migration `0005`, RLS'li) + `document.page_count`; `Document 1—N ParsedElement`; idempotent yeniden-parse (delete+insert, `uq_parsed_element_document_seq`). Worker parse fazı canlı: indir → hibrit ayrıştır → öğeleri yaz (`tenderiq_worker/parsing.py`).

> **Sprint 1.2 kapanış notları (2026-07-16):** (1) Uzun indirme/ayrıştırma DB transaction'ı DIŞINDA yapılır; sonuç tek transaction'da yazılır. (2) DOCX/XLSX sayfa haritasına girmez (dijital sayılır) ve bbox kalite kapısından muaftır — akış-tabanlı formatlarda sayfa kavramı yok. (3) Test durumu: 67 birim + 7 entegrasyon yeşil (hibrit zincir/yönlendirme birim testleri; pipeline testi parse verisini ve idempotent yeniden-parse'ı doğrular; docling dijital-yol + hibrit regresyonu). OCR uçtan uca yolu gerçek taranmış şartnameyle elle doğrulanacak (CPU ~20 sn/sayfa — ADR-0011).
>
> **Sprint 1.1/1.2 kod denetimi (2026-07-16, kapanış sonrası):** Çalışma ağacı uçtan uca denetlendi; bulunan hatalar aynı gün düzeltildi (68 birim + 10 entegrasyon testi yeşil):
> (1) **Kayıp kuyruklama:** iş kuyruklaması commit SONRASI yapıldığından broker kesintisinde iş DB'de sonsuza dek `queued` kalabiliyordu → idempotent `complete` artık hâlâ `queued` görünen işi yeniden yayınlar (task idempotent, mükerrer teslim güvenli; entegrasyon testi güncellendi).
> (2) **401 yönlendirme döngüsü:** cookie var ama JWT geçersizken web `/login ↔ /tenders` arasında dönüyordu → proxy 401'de oturum cookie'sini temizler.
> (3) **Rota tespiti kırılganlığı:** bozuk/şifreli PDF'te pypdf hatası hibrit zinciri hiç denemeden düşürüyordu → rota bilinemezse tam zincir (dijital→OCR→VLM) denenir (+1 birim test).
> (4) Parse geçici dosya uzantısı artık (magic-bytes'la doğrulanmış) `content_type`'tan türetilir — kullanıcı dosya adı içerikle çelişebilir. (5) Süpürme task'ı yarım yüklemenin depodaki yetim nesnesini de best-effort siler. (6) Retry'lar arasında `error_message` yazılır (SSE'de sebepsiz takılma görünmez). (7) `get_principal`: imzası geçerli ama claim'i çözümsüz token (ör. kalkmış rol) 500 değil 401 döner. (8) Web: login `next` open-redirect (`//`) koruması; yükleme hatalarında backend mesajı UI'da gösterilir; oturum servisi backend kesintisinde 502 zarfı döner; SSE `not_found`'da "Canlı" rozeti kapanır.
> (9) **Oran sınırlama proxy düzeltmesi:** web istekleri Next proxy'sinden geldiğinden backend hep proxy IP'sini görüyordu (IP limiti tüm web kullanıcıları için ortak havuzdu) → proxy `X-Forwarded-For` iletir; backend `TRUSTED_PROXY_COUNT` ayarıyla (compose api: 1, varsayılan 0=güvenme) XFF'in sondan N girdisine güvenir (+6 birim test). (10) **Başarılı giriş e-posta sayacını sıfırlar** — meşru kullanıcının ardışık girişleri limiti tüketmez (+2 birim test). (11) **`POST /api/v1/jobs/{id}/retry`:** `failed → queued` yeniden kuyruklama artık API'den tetiklenebilir (writer rolü, AuditLog `job.retried`, commit-sonrası yayın; entegrasyon testli). Bilinçli ertelenen: Idempotency-Key'in failed kayıtta ölü sokak kalması ve replay'de gövde-uyuşmazlığı 409'u (web her denemede yeni anahtar üretir; J.2 backlog).

#### Sprint 1.3 (Hafta 5) — Chunking + embedding + pgvector ✅ (2026-07-17)

`AI/ML` `Veri`
- [x] **Yapı-farkında chunking** (§6.3): `tenderiq_core/indexing/chunking.py` — HEADING yeni chunk başlatır + bölüm bağlamını günceller; TABLE tek başına chunk (taşarsa satır sınırından, bindirmesiz); diğer öğeler yalnız öğe sınırında bölünür; tek başına taşan öğe cümle/satır sınırından bindirmeli (`INDEXING_CHUNK_MAX_CHARS=1800`, `INDEXING_CHUNK_OVERLAP_CHARS=200`). Metadata: bölüm başlığı + sayfa aralığı + kaynak `ParsedElement.seq` aralığı (citation zinciri). Yapısal sınırlar arasında bindirme bilinçli yok — bağlamı `section` taşır; embedding girdisine bölüm başlığı öne eklenir.
- [x] **BGE-M3 embedding** (OSS, çok dilli) entegrasyonu: `EmbeddingModel` protokolü + `create_embedding_model()` fabrikası (`EMBEDDING_PROVIDER=local|managed` — yönetilen geçiş opsiyonu soyutlandı, §6.4); sentence-transformers ile lazy yükleme, L2-normalize (cosine), boyut uyuşmazlığında hata. Paketleme: core `embedding` extra'sı + kök `embedding` grubu; yalnız worker imajı kurar. **Karar → ADR-0008**.
- [x] `Chunk` + `Embedding` modelleri; **pgvector indeksleme**: migration `0006_chunk_embedding` (RLS'li) — `vector(1024)` kolonu + **HNSW** `vector_cosine_ops` (m=16, ef_construction=64); indeks küresel, kiracı filtresi RLS'ten (tenant-scoped strateji §6.5; 1M+ chunk eşiği ADR-0002). `(chunk_id, model)` tekilliği model geçişinde çift vektöre izin verir.
- [x] `Indexing Worker`: `tenderiq_worker/indexing.py` — öğeleri oku → chunk → embed (transaction DIŞINDA) → tek transaction'da delete+insert (idempotent; embedding'ler FK cascade). Durum makinesinin `indexing` fazı canlı.

> **Sprint 1.3 kapanış notları (2026-07-17):** (1) Embedding hesabı, parsing'le aynı desenle DB transaction'ı DIŞINDA yapılır; sonuç tek transaction'da yazılır. (2) Boyut sözleşmesi üç yerde kilitli (migration 0006 ↔ `models.embedding.EMBEDDING_DIM` ↔ `EMBEDDING_DIM` ayarı) — farklı boyutlu modele geçiş migration ister (ADR-0008). (3) Test durumu: 98 birim + 11 entegrasyon yeşil; entegrasyon testi chunk+embedding yazımını GERÇEK pgvector'a (vector(1024) sözleşmesi dahil), idempotent yeniden-indekslemeyi ve kiracılar-arası chunk/embedding izolasyonunu doğrular. BGE-M3'ün kendisi testte sahte embedder'la ikame edilir (~2 GB model indirmesi CI'a uygun değil); gerçek modelle uçtan uca yol Faz 1 çıkış kapısında gerçek şartnameyle elle doğrulanacak (CPU-önce kapasite yolu ADR-0008'de).

#### Sprint 1.4 (Hafta 6) — Golden-set & değerlendirme iskeleti ✅ (2026-07-17)

`AI/ML`
- [x] **Golden-set v1** (§6.10): 3 gerçek doküman etiketlendi (idari şartname + sözleşme tasarısı + teknik şartname: 41 gereksinim, 19 belge [14 zorunlu], 14 risk) — format standardı `evals/README.md` + `run_eval.py` pydantic şemaları (`GoldenCase`/`PredictionSet`, schema_version=1). Gerçek etiketler doküman içeriği taşıdığından `evals/golden/private/` altında (gitignore, KVKK); commit'lenen sentetik `sample/` case CI fixture'ıdır.
- [x] Değerlendirme iskeleti: `evals/run_eval.py` — kategori başına precision/recall/F1 (mikro-ortalama) + **kaçırılan zorunlu belge oranı** (kritik metrik). Eşleme deterministik (TR-farkında normalize + SequenceMatcher ∨ token Jaccard ≥ eşik, bire-bir açgözlü) — LLM yok, CI'da tekrarlanabilir. `--gate` bayrağı eşik ihlalinde çıkış kodu 2 üretir.
- [x] `evals/` CI'a iskelet olarak bağlı: backend job'ı sample fixture ile script'i koşar (format+script doğrulaması, kapı DEĞİL); Sprint 2.4'te `--gate` ile bloke edici olacak.

`DevOps`
- [x] **Sentry entegrasyonu:** backend — `tenderiq_core/observability.py` (`init_sentry` DSN yoksa no-op; `send_default_pii=False` + `before_send` scrub: istek gövdesi/cookie/hassas başlık/sorgu dizesi gitmez, kullanıcı yalnız ID) ; `tenant_id`/`user_id` tag'i principal çözümünde, `tenant_id`/`job_id` worker task'ında bağlanır. Frontend — `@sentry/nextjs` (instrumentation + instrumentation-client + global-error; `NEXT_PUBLIC_SENTRY_DSN` boşken tam no-op; replay/APM kapalı). `@sentry/cli` postinstall bilinçli reddedildi (source-map yükleme J.1'de).

> **Sprint 1.4 kapanış notları (2026-07-17):** (1) Eval eşleme eşiği (0.6) sample fixture üzerinde ayarlandı; Faz 2'de gerçek ajan çıktısıyla yeniden kalibre edilecek (eşik `--threshold` ile parametrik). (2) Gate eşikleri (`--min-recall 0.8`, `--max-missed-mandatory 0.05`) başlangıç önerisidir — Sprint 2.4'te ürün kararıyla kesinleşir. (3) Sentry'de `traces_sample_rate=0` (yalnız hata izleme); APM/replay maliyet analizi Faz 4'e ertelendi. (4) pnpm notları: `caniuse-lite` registry aynası eskisinde kaldığından `pnpm-workspace.yaml`'da geçici override var; `@sentry/cli` build script'i bilinçli reddedildi. (5) Test durumu: 113 birim + 11 entegrasyon yeşil.

**Çıktı:** Bir doküman yüklenince otomatik parse→chunk→embed→index olup `review_ready`'ye ulaşıyor; durum canlı izleniyor; golden-set + eval script çalışıyor. ✓ (gerçek dijital + taranmış şartnameyle doğrulandı — Çıkış Kapısı kanıtları aşağıda)

#### Faz 1 — Çıkış Kapısı ✅ (2026-07-17)

- [x] Gerçek bir şartname (dijital **ve** taranmış) uçtan uca hattan geçip pgvector'a indeksleniyor — `scripts/faz1_gate_check.py` gerçek pipeline'ı (`_run_pipeline`) gerçek BGE-M3 ile koşar (tek ikame: yerel dosya sunan depolama). Kanıt (2026-07-17): dijital idari şartname 15 s. → 325 öğe (%100 bbox) → 77 chunk+embedding (189 sn, model indirme dahil); taranmış teknik şartname 6 s. → EasyOCR → 140 öğe (%100 bbox, kaynak=scanned) → 16 chunk+embedding (180 sn). Cosine getirim kanıtı: "geçici teminat oranı ve süresi" sorgusu ilk sırada **Madde 26 - Geçici teminat** chunk'ını döndürdü (benzerlik 0.68, sayfa+bölüm izlenebilir).
- [x] Her `ParsedElement`/`Chunk` **sayfa + konum** taşıyor: öğe → sayfa+bbox+kaynak; chunk → bölüm + sayfa aralığı + kaynak öğe `seq` aralığı (citation zinciri; entegrasyon testli).
- [x] İş durum makinesi tüm geçişleri canlı (SSE) yansıtıyor; hata durumunda retry/backoff + `POST /jobs/{id}/retry` ile idempotent yeniden deneme (Sprint 1.1/1.2'de kanıtlandı; indexing fazı da aynı idempotent desende).
- [x] Golden-set v1 etiketli (3 gerçek doküman, private); eval script precision/recall + kaçırılan zorunlu belge oranı üretiyor ve CI'da iskelet olarak koşuyor.

**İlgili ADR'ler:** ADR-0002 (pgvector), ADR-0004 (hibrit parsing), ADR-0008 (BGE-M3 embedding).
**Kurulacak skill'ler:** `async-job-state-machine`, `hybrid-document-parsing`, `structure-aware-chunking`, `pgvector-schema-migrations`, `golden-set-eval`, `sse-live-status`, `sentry-error-tracking`.

---
### Faz 2 — Çıkarım & Analiz (Hafta 7–10) — ⭐ EN KRİTİK FAZ

**Amaç.** Ürünün kalbi: RAG ile ilgili bağlamı getirip **uzmanlaşmış çıkarım ajanlarını** çalıştırmak; her bulguyu **zorunlu grounding** + şema doğrulamayla üretmek; kaliteyi ve maliyeti ölçülebilir kılmak.
**Doğrulanan Risk (§12.6).** **AI doğruluğu — projenin en kritik riski.** Kaçırılan zorunlu madde oranı kabul edilebilir mi? Grounding hallucination'ı yapısal olarak sınırlıyor mu?

> Bu faz, A.4/5. ilke gereği ürünün "yaşar mı" sorusunu yanıtlar. Çıkış Kapısı ölçütleri diğer fazlardan daha katıdır.

#### Sprint 2.1 (Hafta 7) — Hibrit getirim + orkestrasyon iskeleti ✅ (2026-07-17)

`AI/ML`
- [x] **Hibrit getirim** (§6.6): `tenderiq_core/retrieval/` — semantik (pgvector cosine, model+RLS filtreli) + anahtar kelime (**süreç-içi Okapi BM25**, TR-farkında tokenizasyon: İ/I katlaması, stem'siz — morfolojiyi semantik yol taşır) + **RRF (k=60)** birleştirme + **cross-encoder reranker** (`BAAI/bge-reranker-v2-m3`, `Reranker` protokolü + fabrika, `RETRIEVAL_RERANKER_PROVIDER=none` ile kapatılabilir). Tüm eşikler `RETRIEVAL_*` ayarlarında; ihale/mevzuat terimli birim testleri (geçici teminat, cezai şart, iş deneyim belgesi, SLA...). **Karar → ADR-0012.**
- [x] **LangGraph orkestrasyon iskeleti** (§6.7): `tenderiq_core/agents/` — pydantic `ExtractionState` (reducer'lı: `findings` sözlük-birleşimi, `errors` liste-eki), `build_extraction_graph` (retrieve → paralel ajan düğümleri → finalize; düğüm-içi `RetryPolicy` + Celery faz-düzeyi retry = çifte katman), `ContextRetriever`/`AgentRunner` protokolleriyle bağımlılık enjeksiyonu (testler sahtelerle koşar). `langgraph` core'un sabit bağımlılığı (hafif, saf-Python). **Karar → ADR-0005.**
- [x] `Extraction Orchestrator`: `tenderiq_worker/extraction.py` — `extracting` fazı canlı: korpus tek transaction'da yüklenir, sorgu embedding'i/BM25/rerank transaction DIŞINDA, pgvector sorgusu kısa oturumlu closure; embedder indexing fazıyla paylaşılır (süreç-tekil BGE-M3), reranker süreç-tekil. RAG bağlamı 4 ajan şablonuna TR ihale-alanı sorgularıyla beslenir (`AGENT_QUERY_TEMPLATES`); ajan koşucuları Sprint 2.2'de kaydolacak.

> **Sprint 2.1 kapanış notları (2026-07-17):** (1) BM25 süreç-içidir (Postgres FTS değil): getirim kapsamı tek ihalenin dokümanları (10²–10³ chunk), skor deterministik, TR tokenizasyon kontrolü bizde; 1M+ chunk küresel arama gerekirse FTS/GIN yükseltme yolu ADR-0012'de. (2) İki getirim yolu da embedding ile aynı metni görür (bölüm başlığı öne eklenmiş). (3) Reranker testlerde/CI'da kapalıdır (`none` → RRF sırası nihai); gerçek cross-encoder yolu Faz 2 çıkış kapısında gerçek şartnameyle doğrulanacak. (4) RRF k / top-k / bağlam tavanı eşikleri kalibre edilmedi — Sprint 2.4 golden-set kapısıyla birlikte ayarlanacak. (5) mypy notu: `add_node`'a `Callable` tipli değişken geçmek langgraph 1.2 overload'larında `Never`'a çözülüyor; düğüm fabrikası dönüş tipi `StateNode[ExtractionState, None]` yapıldı (`langgraph.graph._node` — public re-export yok). (6) Test durumu: 145 birim + 11 entegrasyon yeşil; pipeline entegrasyon testi extracting fazını gerçek pgvector üzerinde koşuyor (semantik+BM25 çift yol kanıtı + citation zinciri asertleri).

#### Sprint 2.2 (Hafta 8) — Çıkarım ajanları + grounding ✅ (2026-07-18)

`AI/ML`
- [x] **Grounding altyapısı** (§6.9) — tüm ajanların temeli: `tenderiq_core/agents/grounding.py` — her öğe `source_index` ([KAYNAK n]) + birebir `source_quote` bildirir; alıntı deterministik doğrulanır (LLM'siz: TR İ/I katlaması + tipografik noktalama eşdeğerliği + boşluk normalizasyonu) ve `ParsedElement`e bağlanır. Çözünürlük: **ELEMENT** (tek öğede doğrulandı → bbox'a hazır) / **CHUNK** (öğe sınırı aşan alıntı → aralık başı öğesi) / **UNGROUNDED** (doğrulanamadı → düşük güven: DB'ye `source_element_id=NULL` yazılır, API'den DÖNMEZ). (skill: `structured-output-grounding`)
- [x] **Şema zorlaması:** `tenderiq_core/llm/` — `StructuredLLM` protokolü + `create_structured_llm()` fabrikası (`LLM_PROVIDER=anthropic|none`; testler sahtelerle). İki katman: (1) Anthropic **structured outputs** (`messages.parse`, adaptive thinking) çıktıyı şemaya token düzeyinde kısıtlar; (2) yine de uymayan çıktı (ör. max_tokens kesmesi) doğrulama hatasıyla birlikte **reddedilip yeniden istenir** (`LLM_SCHEMA_MAX_ATTEMPTS=3`; tavan → `SchemaEnforcementError` → Celery retry). `stop_reason=refusal` kalıcı hatadır, istem tekrarlanmaz. Ajan çıktı şemaları `agents/schemas.py` (pydantic); enum'lar `tenderiq_core/findings.py`'de tek kaynak (ORM ↔ ajan sözleşmesi ayrışamaz).
- [x] **Requirement Extractor** → `agents/extractors.py` (`ExtractionRunner`, `AgentRunner` protokolünü uygular): metin, tip (technical/administrative/financial), zorunluluk, kaynak konum (§6.7, §8.1 `Requirement`). TR ihale-alanı istemleri `agents/prompts.py` (Sprint 2.4'te `packages/prompts`e taşınır).
- [x] **Deliverables Extractor** → belge/sertifika/teminat listesi + kaynak (`Deliverable`; kind: document/certificate/guarantee/other).
- [x] İlgili uçlar: `GET /api/v1/tenders/{id}/requirements`, `.../deliverables` — kaynak konum (`FindingSource`: element_id/seq + sayfa + bbox + bölüm + alıntı + çözünürlük) ile; **inner join kaynaksız bulguyu yapısal olarak dışarıda bırakır** (ADR-0006 kanıtı entegrasyon testinde). OpenAPI→TS sözleşmesi yenilendi.

`Veri`
- [x] `Requirement` + `Deliverable` tabloları (migration `0007`, RLS'li): `N—1` kaynak `ParsedElement` (UNGROUNDED'da NULL), `uq_*_document_seq` idempotency kilidi; extracting fazı bulguları tek transaction'da delete+insert yazar. Re-parse öğeleri yenilediğinde türetilmiş bulgular FK cascade ile silinir (bayat kaynağa işaret eden bulgu kalamaz) — fazın yeniden koşumu yeni öğelere bağlayarak yeniden üretir (entegrasyon testli).

> **Sprint 2.2 kapanış notları (2026-07-18):** (1) LLM istemcisi `anthropic` SDK'sıyla (`claude-opus-4-8`, `messages.parse` + structured outputs + adaptive thinking; non-streaming güvenli tavan `LLM_MAX_OUTPUT_TOKENS=16000`); istemci süreç-tekil, `LLM_PROVIDER=none` extracting fazını 2.1 iskelet moduna düşürür (testler/CI/anahtarsız dev). (2) UNGROUNDED bulgular bilinçli olarak DB'ye yazılır (gözlemlenebilirlik + Sprint 2.4 eval'inde hallucination oranı ölçümü) ama hiçbir API yanıtına giremez. (3) Enum'lar `tenderiq_core/findings.py`'ye alındı (models ← agents bağımlılık yönü, B.2 — döngüsel import kırıldı). (4) Gerçek Claude çağrısıyla uçtan uca yol Faz 2 çıkış kapısında gerçek şartnameyle doğrulanacak; golden-set kalibrasyonu ve prompt/eşik ayarı Sprint 2.4'te. (5) Test durumu: 169 birim + 11 entegrasyon yeşil — şema-ret/yeniden-isteme, refusal, grounding TR katlaması, ajan koşucuları sahte LLM'le birim; pipeline entegrasyon testi bulgu yazımı + cascade + idempotent yeniden-çıkarım + grounding'li API uçları + kiracı izolasyonunu gerçek pgvector üzerinde doğrular.

#### Sprint 2.3 (Hafta 9) — Risk, takvim, gap analizi ✅ (2026-07-19)

`AI/ML`
- [x] **Risk Detector** → cezai şart, olağandışı/riskli maddeler + önem derecesi (`RiskSeverity`) + tür (`RiskCategory`) + kaynak (`RiskFlag`); `GET .../risks`. Requirements/Deliverables ile aynı `ExtractionRunner` + zorunlu grounding kalıbı (grafiğe paralel eklendi).
- [x] **Timeline Extractor** → ihale tarihi, son teklif tarihi, teslim/garanti süreleri (`TimelineKind`); `GET .../timeline`. `value_text` ham metindir (TR tarih/süre çeşitliliği; birebir alıntı grounding'i ayrıştırmadan önce). Plan Veri bölümünde tablo saymamış ama Faz 2 çıktısı "takvim, kaynağa bağlı" dediği için `TimelineEvent` tablosu eklendi (grounding-first zorunluluğu).
- [x] **Compliance Checker** (temel gap analizi §6.7): `agents/compliance.py` — çıkarılmış GROUNDED gereksinimleri `CapabilityProfile`'a karşı değerlendirir (met/partial/unmet + gerekçe → `ComplianceResult`); `GET .../compliance`. Bağlamdan çıkarım DEĞİL → grafiğe girmez; grafik sonrası sıralı worker adımı (gereksinime + dış profil girdisine bağımlı). Grounding değerlendirilen gereksinimden DEVRALINIR (yeni kaynak üretmez).
- [x] `CapabilityProfile` modeli (kiracı-tekil, RLS) + `GET/POST /api/v1/capability-profile` (POST upsert; firma yetkinlik profili — dokümandan çıkarılmaz, kullanıcı girer).
- [ ] (Ops.) **Cost Estimator** → kaba maliyet göstergesi + varsayımlar. **Bilinçli ertelendi** (opsiyonel; kapsam odağı korundu — Sprint 2.4/Faz 3'te değerlendirilir).

`Veri`
- [x] `RiskFlag`, `TimelineEvent`, `ComplianceResult` tabloları (migration `0008`, RLS'li); üçü de `requirement`/`deliverable` grounding + idempotency sözleşmesini paylaşır (`N—1` kaynak `ParsedElement`, `uq_*_document_seq`, re-parse cascade). `CapabilityProfile` ayrı yapıda (bulgu değil, `uq_capability_profile_tenant`). Enum'lar `tenderiq_core/findings.py`'de tek kaynak (`RiskSeverity`/`RiskCategory`/`TimelineKind`/`ComplianceStatus`).

> **Sprint 2.3 kapanış notları (2026-07-19):** (1) Risk/Timeline, worker'daki `_write_findings` genel `_ExtractionFindingSpec` tablosuna alındı — dört çıkarım bulgusu tek idempotent delete+insert döngüsü paylaşır. (2) Compliance yalnız bir `CapabilityProfile` tanımlıysa üretilir; profil yoksa faz bayat sonuçları yine temizler (idempotency). LLM çağrısı transaction DIŞINDA (parsing/indexing deseniyle simetrik); ajan devre dışıyken (`LLM_PROVIDER=none`) compliance da atlanır. (3) Yeni ayar gerekmedi — compliance aynı `StructuredLLM`'i kullanır (Claude birincil / Ollama dev). (4) Golden-set kalibrasyonu + prompt/eşik ayarı ve gerçek Claude çağrısıyla uçtan uca doğrulama Faz 2 çıkış kapısı/Sprint 2.4'te. (5) OpenAPI→TS sözleşmesi yenilendi (5 yeni uç). **Sıradaki: Sprint 2.4** (Langfuse tam entegrasyon + model yönlendirme/prompt caching + zero-retention doğrulaması + AI regresyon kapısını aktif et).

#### Sprint 2.4 (Hafta 10) — Maliyet, gözlemlenebilirlik, eval kapısı ⏳ (2026-07-19: sağlayıcı-agnostik kısımlar TAMAM; Claude'a özgü kısım ertelendi)

> **Model stratejisi kararı (2026-07-19, Berkay):** Proje bitene kadar TÜM dev/test fazlarında **qwen2.5 (Ollama) birincil**; Claude'a yalnız EN SON fazda (yayın öncesi) geçilir. Bu yüzden Sprint 2.4'ün **Claude'a özgü** maddesi (model yönlendirme + prompt caching) bilinçli olarak **yayın fazına ertelendi**; sağlayıcı-agnostik maddeler (Langfuse, zero-retention, eval kapısı) şimdi tamamlandı.

`AI/ML` `Güvenlik`
- [x] **Langfuse** tam entegrasyon (§6.11): sağlayıcı-agnostik tracing seam (`tenderiq_core/llm/tracing.py`) — `LANGFUSE_*` anahtarları yoksa TAMAMEN no-op (langfuse hiç import edilmez; dev/test/CI hesap gerektirmez). Anahtarlar varken her LLM üretimi (qwen dahil) trace edilir: model/gecikme/token; istemciler (Anthropic+Ollama) her çağrıyı `generation()` ile sarar, retry'lar da izlenir. **KVKK/zero-retention:** varsayılan yalnız-metadata; `LANGFUSE_CAPTURE_IO=true` (self-hosted) tam I/O açar. `langfuse` opsiyonel extra (`uv sync --extra langfuse`). Prompt versiyonlama: `PROMPT_VERSION` sabiti + yapılandırılmış log; tam Langfuse-yönetimli prompt registry (`packages/prompts`) yayın fazına ertelendi.
- [ ] **Model yönlendirme** (§6.8): basit triyaj ucuz modele, derin analiz Claude'a; **prompt caching** tekrarlayan sistem promptu + doküman bağlamı için (skill: `llm-cost-routing`). → **Yayın/Claude fazına ERTELENDİ** (Claude'a özgü optimizasyon; qwen tek modelle çalışır). Langfuse token maliyeti ölçümü zaten hazır.
- [x] **Zero-retention doğrulaması** (§10.3): sağlayıcı retention duruşu kurulumda loglanır (`_log_retention_posture`): Ollama = yerel (veri makineden çıkmaz → zero-retention doğası gereği); Anthropic = API varsayılan no-training + ZDR kurumsal anlaşması (yayın öncesi teyit). Veri minimizasyonu: Langfuse `capture_io=false` (doküman içeriği dış buluta gitmez), Sentry gövde/başlık scrub'ı (Sprint 1.4).
- [x] **AI regresyon kapısını AKTİF et:** CI eval adımı `--gate --min-recall 0.8 --max-missed-mandatory 0.05` ile **bloke edici** (E bölümü). Sample fixture "geçer baseline"a yükseltildi; kapı-ihlali tespiti birim testlerde korunur. Gerçek golden-set (private) çıktısı offline üretilip aynı eşiklerle ölçülür; eşikler yayın öncesi Claude çıktısıyla yeniden kalibre edilir.

> **Sprint 2.4 kapanış notları (2026-07-19):** (1) Langfuse SDK yolu (`start_as_current_generation`) tek adaptörde izole; dev'de anahtarsız = hiç çalışmaz (no-op), ilk etkinleştirmede canlı doğrulanmalı. Seam ve istemci enstrümantasyonu sahte tracer'la birim testli (token kaydı + capture_io kapısı). (2) Eval gate: sample'ı "geçer" yaptım, `test_cli_gate_ihlalde_iki_doner` satır-içi kusurlu veriyle yeniden yazıldı (kaçırılan-zorunlu tespiti `test_evaluate_case...`ta korunur). (3) Yeni ayar: `LANGFUSE_CAPTURE_IO` (varsayılan false, KVKK). (4) Test: 186 birim + 11 entegrasyon yeşil. **Sıradaki: Faz 2 Çıkış Kapısı** — gerçek şartname + qwen ile uçtan uca doğrulama, golden-set metrikleri; ardından Faz 3 (İnceleme UI).

**Çıktı:** Bir şartname yüklenince gereksinim + belge + risk + takvim + temel gap, **her biri kaynağa bağlı** olarak üretiliyor; maliyet ve kalite Langfuse'da izleniyor (anahtar tanımlıysa); eval kapısı CI'da bloke edici. Model yönlendirme/prompt caching yayın (Claude) fazında.

#### Faz 2 — Çıkış Kapısı 🟡 (makine + baseline doğrulandı; kalite/maliyet kapısı Claude yayın fazında) (2026-07-19)

- [x] Golden-set üzerinde ajanlar çalışıyor ve metrikler ölçülüyor: **precision/recall + kaçırılan zorunlu belge oranı + kaynak-eşleme doğruluğu** — 3 gerçek şartname (private) qwen ile uçtan uca koştu, `scripts/faz2_gate_check.py` + `evals/run_eval.py` ölçtü (baseline aşağıda). Not: qwen baseline recall'u yayın eşiğinin (0.8) ALTINDA — bu **beklenen** (qwen dev modeli; Claude yayın kalite kapısı). Kaynak-eşleme (sayfa) bulgu üretilen case'lerde **%100** (3-kalem 8/8, sozlesme 1/1).
- [x] **Grounding zorunluluğu kanıtlı:** kaynağa bağlanamayan bulgu API'den dönmüyor — canlıda gözlemlendi (ör. idari: 3 grounded / 3 ungrounded requirement, yalnız grounded API'ye gider) + entegrasyon testi (`test_upload_pipeline_flow`, inner join UNGROUNDED'ı dışlar).
- [x] Şema-dışı LLM çıktısı reddedilip yeniden isteniyor — canlıda gözlemlendi (`llm_sema_ihlali` → retry) + birim testleri (anthropic + ollama + refusal kalıcı hata).
- [ ] Belge başına maliyet Langfuse'da görünüyor ve hedef marj bandında (§13.2) → **Claude yayın fazına ERTELENDİ** (model stratejisi 2026-07-19): tracing seam + token/gecikme kaydı iki sağlayıcıda da hazır ve birim-testli; qwen yerel → marjinal $ maliyet=0 (zero-retention doğası). Canlı Langfuse $ panosu + marj bandı Claude'a özgü (model yönlendirme/prompt caching ile birlikte).
- [x] Zero-retention ayarı tüm LLM çağrılarında doğrulandı — kurulumda loglanıyor (`llm_retention_posture posture=local_zero_retention provider=ollama`, `capture_io=False`); canlı koşumda görüldü.
- [x] AI regresyon kapısı CI'da bloke edici olarak çalışıyor — CI adımı `--gate`; gerçek golden çıktısında **exit code 2** üreterek bloke ettiği gösterildi (recall<0.8 + kaçırılan-zorunlu>0.05).

> **Faz 2 Çıkış Kapısı kapanış notları (2026-07-19):** Gerçek şartnamelerle uçtan uca çıkarım qwen ile doğrulandı; makine (parse→index→retrieve→ajan→grounding→bulgu→API) çalışıyor.
> **(1) Bulunan + düzeltilen bug — sessiz bağlam kırpması:** `ollama_num_ctx=8192` + `retrieval_agent_context_limit=12` (~7k token istem) + `num_predict=4096` num_ctx'i taşırıyordu → Ollama istemi SESSİZCE kırpıyor → model kaynağı göremiyor → grounding çöküyordu (12-chunk'ta requirements 1/14 grounded). Kök neden hafızadaki `qwen-context-budget-risk` idi. **Çözüm:** `Settings.effective_agent_context_limit()` — Ollama'da bağlam tavanını `(num_ctx-num_predict)*3//chunk_chars` ile pencereye sığan chunk sayısına (8192/4096/1800 ⇒ 6) otomatik kısar; geniş-pencereli Claude'da 12 aynen kalır (sağlayıcı-farkında; 3 birim test). Etki: requirements grounding 1/14 → 3/6 ve extraction süresi ~8 dk → ~1.5 dk/doküman.
> **(2) qwen baseline (3 gerçek şartname, private):** requirements P=0.53 R=0.20 F1=0.29; deliverables P=0 R=0 F1=0; risks P=0.13 R=0.07 F1=0.09; **kaçırılan zorunlu belge oranı 1.00 (14/14)**. Düşük — beklenen: (a) qwen 7B sınırı, (b) zorunlu grounding çoğu paraphrase'li bulguyu eler (doğru davranış — kaynaksız gösterme), (c) golden etiketler dokümanın elle-seçilmiş alt kümesi (qwen başka geçerli maddeleri de çıkarır → metin eşleşmez). Bulgu üretilen yerde kalite yüksek: sozlesme risk 8/9 grounded, kaynak-eşleme %100. **Yayın eşiği (recall≥0.8, kaçırılan-zorunlu≤0.05) Claude ile karşılanacak ve eşikler o çıktıyla yeniden kalibre edilecek.**
> **(3) Kapsam:** Compliance yalnız `CapabilityProfile` tanımlıysa üretilir (gate koşumunda profil yok → atlandı; ayrı entegrasyon testinde kanıtlı). Reranker gate koşumunda kapalı (`none`) — qwen ile VRAM çakışmasını önlemek için; RRF sırası nihai. Test durumu: 189 birim + entegrasyon yeşil (3 yeni config testi dahil).
> **Sonuç:** Makine + grounding + ölçüm hattı + zero-retention + bloke edici eval kapısı doğrulandı; qwen baseline'ı kayda geçti; kalite/maliyet kapısı bilinçli olarak Claude yayın fazına bırakıldı. **Sıradaki: Faz 3 — İnceleme UI + Export + Ödeme** (kalite Claude ile yayın öncesi kalibre edilir).

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

#### Sprint 3.3 (Hafta 13) — Abonelik, kota, ödeme + hesap yaşam döngüsü

`Backend/API` `Güvenlik`
- [ ] `Subscription` + `UsageRecord` modelleri; belge/sayfa **kota takibi**; `GET /api/v1/usage`.
- [ ] **Ödeme entegrasyonu** (§14.3): iyzico/PayTR; **webhook imza doğrulama + idempotent işleme** (aynı webhook iki kez gelirse çift faturalama yok); abonelik↔kota senkronizasyonu; `UsageRecord` güncelleme (skill: `payment-integration-tr`).
- [ ] Kota aşımı kuralları (adil kullanım / ek ücret) ve kullanıcıya gösterim; kota **enforcement** (yalnızca gösterim değil — aşımda yükleme reddi/uyarı).

`Güvenlik` (hesap & oturum yaşam döngüsü — beta'ya çıkmadan önce zorunlu; J.2 backlog'undan)
- [ ] **Refresh token + rotasyon:** kısa ömürlü access token (≤1 saat) + tek-kullanımlık refresh token; `POST /auth/refresh`, `POST /auth/logout` (Redis denylist ile iptal).
- [ ] **E-posta doğrulama + parola sıfırlama:** işlemsel e-posta sağlayıcısı (Resend/Postmark/SES) + tek-kullanımlık, süreli token'lar.
- [ ] **Çoklu-organizasyon desteği:** login'de aktif üyelik seçimi + `POST /auth/switch-org` (bugün ilk üyelik rastgele seçiliyor); davet akışı (`Membership` + e-posta daveti).
- [ ] Kullanıcı/organizasyon yönetim ekranları: üye listesi, rol değiştirme (AuditLog'lu), üyelik silme.

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
- [ ] `soft-delete` + zamanlanmış `hard-delete` job'ı; ilişkili tüm tablolarda (Document, Chunk, Embedding, ParsedElement) kademeli silme (§8.3) + R2 nesnelerinin silinmesi.
- [ ] Fiyatlandırmanın canlıya alınması; production'a onaylı deploy; yedek geri-yükleme testi (§11.5).
- [ ] **Yük/dayanıklılık testi:** eşzamanlı yükleme + işleme senaryosu (ör. 10 kiracı × 100'er sayfa); kuyruk derinliği/işleme süresi hedefleri doğrulanır (J.4 SLO'ları).
- [ ] **Güvenlik gözden geçirmesi:** OWASP ASVS-hafif öz-denetim + `security-review` taraması; mümkünse üçüncü-taraf hafif pentest (bütçeye göre).
- [ ] **Status page + uptime izleme** canlı (J.4); olay müdahale runbook'u yazıldı.

> Faz 4 sonu = **kapalı beta**. Halka açık self-service yayına (GA) geçiş, **J bölümündeki kontrol listeleri** tamamlanınca yapılır.

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
| **M0 — İskelet & Yükleme** ✅ (2026-07-04) | Faz 0 sonu | `docker compose up` + RLS izolasyon testi + parsing spike raporu — tamamlandı; 2026-07-08 denetimiyle sertleştirildi |
| **M1 — Çekirdek Hat** ✅ (2026-07-17) | Faz 1 sonu | Doküman uçtan uca indeksleniyor + golden-set/eval çalışıyor — tamamlandı (gerçek dijital+taranmış şartname kanıtıyla) |
| **M2 — AI Doğruluğu Kanıtı** | Faz 2 sonu | Grounding'li çıkarım + ölçülen metrikler + aktif regresyon kapısı |
| **M3 — Kullanılabilir Ürün** | Faz 3 sonu | İnceleme+kaynak vurgusu + export + ödeme; E2E yeşil |
| **M4 — İlk Müşteri** | Faz 4 | Kapalı beta + trust/KVKK + ilk ödeyen müşteri |
| **M5 — GA: Halka Açık SaaS** | J bölümü | J.1–J.6 kontrol listeleri kapalı: staging+prod dağıtımı, yedek/restore tatbikatı, SLO+status page, ToS/KVKK/e-fatura, self-service abonelik |

**İlk 30 Gün:** Repo + CI/CD + Docker + auth/çok-kiracılılık iskeleti · uçtan uca yükleme & R2 · 3–5 gerçek şartname ile parsing spike · ilk golden-set etiketleme + eval iskeleti.
**İlk 60 Gün:** Asenkron hat + indeksleme + hibrit parsing · ilk çıkarım ajanları (gereksinim + belge) + grounding · Langfuse ile maliyet/kalite ölçümü.
**İlk 90 Gün:** Risk + takvim + temel gap ajanları · inceleme ekranı + kaynak vurgusu + Word/Excel export · ödeme/kota temel + ilk design partner ile kapalı beta.

---

## J. Yayına Alma — Production-Readiness Yol Haritası

> Fazlar (D) ürünü **kapalı betaya** taşır; bu bölüm betayı **halka açık, ödeme alan,
> operasyonel olarak ayakta kalabilen bir SaaS'a** taşır. Kalemler faz görevlerine paralel
> ilerler; her birinin "en geç" bağlandığı kapı belirtilir. Solo-dev gerçekçiliği:
> **yönetilen servis > kendi kur**, otomasyon > runbook, az ama bloke edici kontrol.

### J.1 Ortamlar, Dağıtım & Sürümleme

| Kalem | Karar/Görev | En geç |
|---|---|---|
| Staging ortamı | Üretimle aynı compose/imajlar; ayrı DB + R2 bucket + sırlar; anonimleştirilmiş örnek veri | Faz 2 sonu |
| Production barındırma | Tek VPS (Hetzner/DO) + Docker Compose **veya** PaaS (Fly.io/Render) — ADR ile karar; başlangıçta basit tut | Faz 3 sonu |
| `deploy.yml` | main→staging otomatik; production **manual approval** + imaj etiketi (git SHA) + tek komut rollback | Faz 3 sonu |
| TLS & alan adı | `app.` (web), `api.` (API) alt alanları; Caddy/Traefik ile otomatik TLS; HSTS | Faz 3 sonu |
| Migration disiplini | Deploy öncesi `alembic upgrade head` ayrı adım; geriye-uyumlu (expand→migrate→contract) şema değişimi kuralı | Faz 1'den itibaren |
| Ters proxy & SSE | Proxy'de SSE buffering kapalı (`X-Accel-Buffering: no`), uzun bağlantı zaman aşımı ayarlı | Faz 1 (SSE ile) |

- [ ] Barındırma ADR'si (VPS+Compose vs PaaS) yazıldı ve staging kuruldu.
- [ ] `deploy.yml` (staging otomatik / prod onaylı) çalışıyor; rollback prova edildi.
- [ ] Özel alan adı + TLS + güvenlik başlıkları (HSTS, `X-Content-Type-Options`, CSP raporlama modu) canlı.

### J.2 Güvenlik Sertleştirme Backlog'u

Faz 0 denetiminde kapatılanlar için D bölümüne bakınız. Kalan backlog (öncelik sırasıyla):

| # | Kalem | Neden | Nerede |
|---|---|---|---|
| 1 | ~~Login/register **rate-limit** (Redis)~~ ✅ 2026-07-16 | Brute-force & kayıt istismarı | Faz 1 Sprint 1.1 |
| 2 | ~~Yükleme tamamlama + dosya doğrulama (tür/boyut/magic-bytes)~~ ✅ 2026-07-16 | Depolama istismarı, işleme güvenliği | Faz 1 Sprint 1.1 |
| 3 | ~~`AuditLog` (yükleme/silme/rol/export)~~ ✅ 2026-07-16 (yükleme/oluşturma kayıtları; silme/rol/export uçları geldikçe eklenecek) | Kurumsal satış ön koşulu (§10.5) | Faz 1 Sprint 1.1 |
| 4 | Refresh token + rotasyon + logout/iptal (Redis denylist); access token ≤1 saat | 12 saatlik iptal-edilemez JWT beta için kabul edilemez | Faz 3 Sprint 3.3 |
| 5 | E-posta doğrulama + parola sıfırlama | Hesap ele geçirme & spam kayıt | Faz 3 Sprint 3.3 |
| 6 | Çoklu-org seçimi + davet + üye yönetimi (bugün ilk üyelik rastgele) | Çok kullanıcılı kiracılar | Faz 3 Sprint 3.3 |
| 7 | `pip-audit`'i **bloke edici** yap (istisna listesiyle) + Dependabot/Renovate + imaj taraması (trivy) | Tedarik zinciri | Faz 2 sonu |
| 8 | Sır rotasyon prosedürü (AUTH_SECRET, R2, LLM anahtarları) — çift-anahtar destekli | Sızıntı müdahalesi | GA öncesi |
| 9 | (Ops.) 2FA/TOTP — kurumsal müşteri isterse | Satış gereksinimi | Talep gelince |

### J.3 Veri Dayanıklılığı & Felaket Kurtarma

- [ ] **Otomatik DB yedeği:** günlük tam + WAL arşivi (mümkünse yönetilen Postgres'e geçişle bedavaya gelir); yedekler ayrı konumda ve şifreli.
- [ ] **Aylık restore tatbikatı:** yedekten staging'e geri yükleme otomasyonu — "yedek var" değil "geri dönebiliyorum" kanıtı (§11.5).
- [ ] **Hedefler:** RPO ≤ 24 saat (beta) → ≤ 1 saat (GA, WAL ile); RTO ≤ 4 saat.
- [ ] **R2:** bucket versioning + yaşam döngüsü kuralları; hard-delete akışıyla uyumlu.
- [ ] **Veri saklama matrisi (KVKK §10.4):** veri sınıfı → saklama süresi → silme mekanizması tablosu; sözleşme eklerine girer.

### J.4 Gözlemlenebilirlik, SLO & Operasyon

- [ ] **Uptime izleme + uyarı:** dış izleyici (`/healthz`, `/readyz`, web) → e-posta/Telegram; Sentry hata uyarıları.
- [ ] **SLO'lar (beta hedefleri):** API erişilebilirlik ≥ %99,5 · API p95 < 500 ms (LLM uçları hariç) · 100 sayfalık dijital doküman işleme < 10 dk · işleme başarı oranı ≥ %98.
- [ ] **Metrik panosu:** kuyruk derinliği, iş süreleri, hata oranı, belge başına maliyet (Langfuse) — basit Grafana veya hosted eşdeğeri.
- [ ] **Olay müdahale runbook'u:** en olası 5 arıza (DB dolu, kuyruk tıkandı, LLM sağlayıcı kesintisi, OCR patlaması, disk dolu) için teşhis+çözüm adımları.
- [ ] **Status page** (hosted, ör. Instatus/BetterStack) + planlı bakım duyuru kanalı.
- [ ] **Log saklama:** yapılandırılmış loglar merkezî yerde ≥ 30 gün; PII maskeleme doğrulanmış.

### J.5 GA (Halka Açık Yayın) Kontrol Listesi

**Yasal & güven (KVKK odaklı):**
- [ ] Aydınlatma metni + açık rıza akışları + çerez politikası yayında (Faz 4 çıktısı).
- [ ] Kullanım şartları (ToS) + hizmet seviyesi beyanı; kurumsal için DPA şablonu.
- [ ] Trust page: veri işleme akışı, zero-retention LLM, alt-işleyen listesi, veri konumu.
- [ ] VERBİS kaydı gerekliliği değerlendirildi (çalışan sayısı/veri hacmi eşiği).

**Ticari:**
- [ ] Fiyatlandırma sayfası + self-service abonelik + **e-Arşiv/e-Fatura** kesimi (TR zorunluluğu — entegratör: Paraşüt/BizimHesap vb.).
- [ ] Deneme süreci (trial) + kota/plan yükseltme akışı + iptal/iade politikası.

**Ürün & destek:**
- [ ] Onboarding: ilk giriş sihirbazı + örnek şartname ile demo analiz.
- [ ] Destek kanalı (destek e-postası + SSS); hedef ilk-yanıt süresi tanımlı.
- [ ] Ürün analitiği (self-host Plausible/PostHog — KVKK-uyumlu) + funnel: kayıt→ilk yükleme→ilk export.
- [ ] Pazarlama sitesi (landing): değer önerisi + demo video + beta referansları.

**Teknik son kontrol:**
- [ ] J.1–J.4'ün tüm kutuları kapalı; CI'da tüm kapılar (AI regresyonu dâhil) bloke edici.
- [ ] Yük testi GA trafik varsayımıyla tekrarlandı; kota/bütçe alarmları canlı.

### J.6 Ölçek & Maliyet Korkulukları

- [ ] **LLM bütçe alarmı:** kiracı-başına ve toplam günlük token bütçesi; aşımda yumuşak durdurma + uyarı (Langfuse verisiyle).
- [ ] **OCR kapasite planı:** %54 taranmış korpus gerçeğine göre GPU worker havuzu veya yönetilen OCR; sayfa-başına maliyet hedefi belirle (ADR — Faz 1'deki karar).
- [ ] **Kuyruk adaleti:** kiracı-başına eşzamanlılık sınırı (tek büyük kiracı kuyruğu kilitlemesin); öncelik sınıfları (küçük dosya önce).
- [ ] **pgvector büyüme planı:** indeks tipi (HNSW) + `tenant_id` bileşik filtre performansı; 1M chunk üzeri için Qdrant'a taşıma eşiği tanımlı (ADR-0002 yükseltme yolu).
- [ ] **Depolama kotası:** kiracı-başına GB sınırı; plan seviyesine bağlanır.

---

## K. Ekler

### K.1 Skill Kurulum Sırası (özet)

`TenderIQ_ClaudeCode_Skills.md` ile birebir eşlenir:

1. **Faz 0:** `multi-tenant-fastapi`, `docker-compose-scaffold`, `github-actions-cicd`, `rest-api-conventions`.
2. **Faz 1:** `hybrid-document-parsing`, `structure-aware-chunking`, `pgvector-schema-migrations`, `async-job-state-machine`, `golden-set-eval`, `sse-live-status`, `sentry-error-tracking`.
3. **Faz 2:** `langgraph-extraction-agents`, `structured-output-grounding`, `hybrid-retrieval-rerank`, `langfuse-observability`, `llm-cost-routing`, `zero-retention-llm-config`.
4. **Faz 3:** `document-preview-highlight`, `review-approval-workflow-ui`, `docx`/`xlsx` + `tenderiq-report-template`, `payment-integration-tr`.
5. **Faz 4:** `kvkk-compliance-checklist`, `soft-delete-kvkk-erasure`, `trust-page-content`.

### K.2 Tekrar Kullanılabilir Kontrol Listesi Şablonları

**Yeni tablo eklerken:** `tenant_id` kolonu → RLS politikası → izolasyon testi → Alembic migration → soft-delete alanı (gerekiyorsa).
**Yeni çıkarım ajanı eklerken:** Pydantic çıktı şeması → grounding (kaynak konum zorunlu) → şema-dışı çıktı reddi → golden-set beklentisi → Langfuse trace → regresyon testi.
**Yeni endpoint eklerken:** `/api/v1` altında → Pydantic request/response + hata şeması → kiracı yetki kontrolü → (yazma ise) `Idempotency-Key` → OpenAPI güncel → `api-client` yeniden üretim → AuditLog (kritikse).

### K.3 Terimler

Terim sözlüğü için Ürün Planı **Ek A**'ya bakınız (RFP, EKAP, Parsing, OCR, VLM, Chunking, Embedding, RAG, Grounding, RLS, RBAC, Zero-retention, KVKK, MRR/NRR/CAC/LTV).

### K.4 Kaynak Belgeler

- `TenderIQ_Proje_Plani.docx` — v1.0 stratejik ürün ve teknik plan (bu belgenin kaynağı).
- `TenderIQ_ClaudeCode_Skills.md` — faz-bazlı Claude Code skill haritası.

---

> **Tek cümlelik yürütme özeti:** Dar bir dikeyde (TR kamu BT/yazılım ihaleleri), kaynağına kadar izlenebilir ve KVKK-uyumlu bir AI şartname analiz aracıyla başla; **AI doğruluğunu Faz 2'de ölçülebilir biçimde kanıtla**; sabit maliyeti düşük tutup ilk ödeyen müşterilerle finanse ederek büyü; **J bölümüyle betadan halka açık SaaS'a geç**.

*TenderIQ — Geliştirme Planı v1.1 · Temmuz 2026 · Berkay (Scryne). Kaynak: TenderIQ Proje Planı v1.0.*
