# ADR-0001: Monorepo (apps + packages)

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-03
- **Karar veren:** Berkay (Scryne)

## Bağlam
TenderIQ; Next.js frontend, FastAPI API ve Celery worker'dan oluşur. API ve worker
aynı domain modelini, şemaları ve servisleri paylaşır. Tek geliştirici için sürüm
uyumu, ortak kod paylaşımı ve tek CI hattı önemlidir.

## Karar
Tek bir **monorepo** kullanılır. Uygulamalar `apps/*` altında ince giriş noktalarıdır;
paylaşılan ağır Python mantığı `packages/core` içinde toplanır. Frontend, backend'e
yalnızca üretilen `packages/api-client` üzerinden erişir.

- Python: `uv` workspace (`packages/core`, `apps/api`, `apps/worker`).
- TypeScript: `pnpm` workspace (`apps/web`, `packages/api-client`).

## Sonuçlar
**Olumlu:** Tek sürüm/CI, kolay kod paylaşımı, atomik değişiklikler (API + istemci
birlikte güncellenir), düşük operasyonel yük.
**Ödünler:** Repo büyür; araç zinciri (uv + pnpm) birlikte yönetilir; dağıtımda
uygulama bazlı imaj sınırları netleştirilmelidir (ayrı Dockerfile'larla çözüldü).

## Alternatifler
- **Polyrepo:** Bağımsız dağıtım ama şema senkronizasyonu ve koordinasyon yükü yüksek.
- **Tek paket (apps ayrımı yok):** API ve worker'ı ayıramamak ölçeklenmeyi zorlaştırır.

## İlgili
Geliştirme Planı §B.1, §B.2.
