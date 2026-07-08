# TenderIQ

**Yapay Zekâ Destekli İhale ve RFP Analiz Platformu** — yüzlerce sayfalık Türkçe ihale/RFP
dokümanlarını dakikalar içinde analiz eder; gereksinim, risk, teslim-belge ve uygunluk
boşluklarını **kaynağına kadar izlenebilir** (citation-first) biçimde çıkarır. KVKK-uyumlu,
çok-kiracılı SaaS.

> 📄 Strateji ve ürün planı: [`TenderIQ_Proje_Plani.docx`](TenderIQ_Proje_Plani.docx) ·
> 🛠️ Yürütme planı: [`GELISTIRME_PLANI.md`](GELISTIRME_PLANI.md) ·
> 🧭 Mimari kararlar: [`docs/adr/`](docs/adr/)

## Mimari

Monorepo; `apps/*` ince giriş noktaları, paylaşılan Python mantığı `packages/core`'da.
Frontend backend'e yalnızca üretilen `packages/api-client` üzerinden erişir (tip-güvenli sözleşme).

| Katman | Teknoloji |
|---|---|
| Frontend | Next.js (App Router) + React + TypeScript + Tailwind/shadcn |
| API | FastAPI (async) — `/api/v1`, sağlık uçları, tutarlı hata modeli, SSE |
| Worker | Celery + Redis — asenkron işleme hattı |
| Çekirdek | SQLAlchemy 2.0 (async) · Pydantic · yapılandırılmış loglama (structlog) |
| Veri | PostgreSQL 16 + pgvector · Redis · Cloudflare R2 (S3-uyumlu) |
| AI (Faz 1+) | Docling/VLM parsing · BGE-M3 embedding · LangGraph · Claude · Langfuse |

## Önkoşullar

- **Python 3.12+** ve [**uv**](https://docs.astral.sh/uv/) (`pip install uv`)
- **Node 22+** ve **pnpm** (`npm install -g pnpm`)
- **Docker** + **Docker Compose** (yerel PostgreSQL/Redis için)
- **Git**

## Hızlı Başlangıç

```bash
# 1) (İlk kez) Git deposu başlat
git init

# 2) Ortam değişkenleri
cp .env.example .env        # gerekli sırları doldurun (yerel için varsayılanlar çalışır)

# 3) Backend bağımlılıkları (uv workspace — tek venv)
uv sync

# 4) Yerel altyapıyı başlat (PostgreSQL + pgvector, Redis)
docker compose -f infra/compose/docker-compose.yml up -d postgres redis

# 5) Veritabanı migration'ları
uv run alembic upgrade head

# 6) API'yi çalıştır → http://localhost:8000/docs
pnpm api:dev

# 7) (Ayrı terminal) Worker'ı çalıştır
pnpm worker:dev
```

**Tam Docker (isteğe bağlı):** `pnpm up` tüm servisleri (db + redis + migrate + api + worker)
imajları derleyerek ayağa kaldırır; `pnpm down` durdurur.

> **RLS notu:** Uygulama, RLS'ye tabi `tenderiq_app` rolüyle (`DATABASE_URL`) bağlanır;
> migration'lar ayrıcalıklı `tenderiq` rolüyle (`DATABASE_ADMIN_URL`) çalışır. Rolü Postgres
> init script'i oluşturur — eski bir veri hacminiz varsa bir kez
> `docker compose -f infra/compose/docker-compose.yml down -v` ile sıfırlayın (ADR-0003).

## Komutlar

| Komut | İşlev |
|---|---|
| `pnpm lint:py` / `pnpm format:py` | Ruff lint / biçimlendirme |
| `pnpm typecheck:py` | Mypy (strict) |
| `pnpm test:py` | Pytest |
| `pnpm api:dev` / `pnpm worker:dev` | API (uvicorn) / Celery worker |
| `pnpm openapi:export` | OpenAPI şemasını `packages/api-client/openapi.json`'a üret |
| `pnpm up` / `pnpm down` / `pnpm logs` | Docker Compose yaşam döngüsü |
| `uv run alembic upgrade head` | Migration'ları uygula |
| `uvx pre-commit install` | Git hook'larını kur (ruff, mypy, gitleaks) |

## Proje Yapısı

```
tender-iq/
├─ apps/
│  ├─ web/        # Next.js frontend
│  ├─ api/        # FastAPI — /api/v1, health, hata modeli, SSE
│  └─ worker/     # Celery worker — işleme hattı task'ları
├─ packages/
│  ├─ core/       # Ortak Python: config, loglama, db, servisler, AI hattı
│  └─ api-client/ # OpenAPI'dan üretilen TypeScript istemci
├─ migrations/    # Alembic (pgvector + RLS)
├─ evals/         # AI golden-set + değerlendirme (Faz 1)
├─ infra/         # Dockerfile'lar + docker-compose
├─ docs/adr/      # Mimari Karar Kayıtları
└─ scripts/       # Yardımcı scriptler
```

## Test & Kalite

- **Lint/format:** Ruff · **Tip:** Mypy strict · **Test:** Pytest (+ testcontainers, Faz 1)
- **CI** (`.github/workflows/ci.yml`): lint → tip → migration → test · OpenAPI drift · gitleaks + pip-audit
- **AI kalite kapısı** (Faz 2): golden-set regresyonu prompt/model değişiminde bloke eder

## Yol Haritası (özet)

| Faz | Kapsam | Durum |
|---|---|---|
| 0 | Temeller: monorepo, auth+RLS, yükleme, parsing spike | ✅ Tamam (2026-07-04; 2026-07-08 denetimiyle sertleştirildi) |
| **1** | Çekirdek işleme hattı (parse→chunk→embed→index) + golden-set | 🚧 Sırada |
| 2 | Çıkarım ajanları + zorunlu grounding + eval (en kritik) | ⏳ |
| 3 | İnceleme UI + kaynak vurgusu + export + ödeme + hesap yaşam döngüsü | ⏳ |
| 4 | Beta + ilk müşteriler + KVKK/trust | ⏳ |
| GA | Yayına alma: dağıtım/DR/SLO/yasal-ticari kontrol listeleri (plan §J) | ⏳ |

Ayrıntı için [`GELISTIRME_PLANI.md`](GELISTIRME_PLANI.md).

---

© 2026 Berkay (Scryne) · İç kullanım — ticari sırlar içerir.
