# DURUM — TenderIQ

> Envanter, sertifika değil. Ayrıntılı operasyon gerçeği ve tuzaklar: `docs/ops/DURUM.md`.

**Ölçüm tarihi:** 2026-09-25 (denetim turu, commit `a841367`)

**Tek cümle:** Uçtan uca çalışıyor: kurgusal bir şartname yüklendi, ~5 dakikada 34 kaynağa bağlı
bulgu çıktı; testler, tip denetimi, güvenlik taraması ve erişilebilirlik temiz.

## Ne çalışıyor (ölçüldü)

- **Testler:** 415 birim + 183 entegrasyon (testcontainers, gerçek Postgres/Redis) geçti.
- **Web:** `typecheck` · `lint` · üretim `build` (26 rota) temiz.
- **Güvenlik:** trivy fs, HIGH/CRITICAL = 0 (Next 15.5.26, override'lar, `uv lock` yükseltmeleri).
- **Erişilebilirlik:** Lighthouse, üretim derlemesinde 18/18 rota = 100.
- **Uçtan uca:** giriş → ihale → R2'ye yükleme → ayrıştırma (Docling) → indeksleme (BGE-M3) →
  çıkarım (NIM `nemotron-3-super-120b-a12b`) → inceleme ekranında PDF vurgusu → uygunluk analizi
  (yetkinlik profili "ISO 27001 yok" → ilgili madde "Karşılanmıyor").

## Açık kalanlar

- Hukuki metinlerde şirket bilgileri (`LEGAL_TODO.md`): gerçek şirket kurulmadan doldurulamaz.
- Canlı ödeme (iyzico abonelik modülü hesapta kapalı), Resend alan adı doğrulaması.
- NIM fiyatı doğrulanamıyor (sağlayıcı yayımlamıyor); geliştirme katmanı olduğu için engel değil.
- Uzak `feat/faz3-sprint-3.3` dalı ve açık Dependabot PR'ları duruyor.
