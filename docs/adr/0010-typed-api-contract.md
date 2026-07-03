# ADR-0010: Tip-güvenli API sözleşmesi (OpenAPI → TypeScript)

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-03
- **Karar veren:** Berkay (Scryne)

## Bağlam
Ayrı frontend (TS) ve backend (Python) arasında sözleşme kayması (drift), sessiz
çalışma-zamanı hatalarının başlıca kaynağıdır. Tek doğruluk kaynağı gerekir.

## Karar
Tek doğruluk kaynağı, FastAPI'nin Pydantic modellerinden ürettiği **OpenAPI şemasıdır**.
`scripts/export_openapi.py` şemayı `packages/api-client/openapi.json`'a yazar; buradan
TypeScript istemci/tipler üretilir. `apps/web` backend'e yalnızca bu üretilen istemci
üzerinden erişir (ham `fetch` ile endpoint çağrısı yasak).

**CI kapısı:** `contract` job'ı şemayı yeniden üretir ve commit'lenenle karşılaştırır;
fark varsa pipeline kırılır → şema değişince istemci güncellenmek zorundadır.

## Sonuçlar
**Olumlu:** Backend↔frontend drift'i yapısal olarak imkânsızlaşır; tip güvenliği
uçtan uca taşınır.
**Ödünler:** Şema değişiminde istemci yeniden üretim adımı; CI'da ek job.

## Alternatifler
- **Elle yazılan TS tipleri:** Hızlı ama kaçınılmaz drift.
- **tRPC benzeri tek-dil çözümü:** Python backend ile uyumsuz.

## İlgili
Geliştirme Planı §B.5; `scripts/export_openapi.py`, `.github/workflows/ci.yml`.
