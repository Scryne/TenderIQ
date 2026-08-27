# DURUM — TenderIQ — Türkçe kamu ihale analizi

> **Ne bu dosya:** sertifika değil **envanter**. 2026-08-27 denetiminde ölçülen gerçek durum.
> "Çalışmıyor" yazan satır kusur değil, kayıt. Kapanış standardı:
> `ScryneOS/🎯 100-Command-Center/Kapanis-Standardi.md`

**Ölçüm tarihi:** 2026-08-27
**Tek cümle:** Denetimin en sağlam projesi: 413 test geçiyor, tip denetimi temiz, web derleniyor.

## Ne çalışıyor

- **Python testleri: 413 geçti**, 187 deselect. Süre 4 dk 8 sn.
- **`web:typecheck` temiz** · **`web:build` başarılı.** Rotalar: `/tenders` · `/tenders/[id]` ·
  `/tenders/[id]/review` · `/settings` · `/usage` · `/trust` · `/sartlar` ·
  `/verify-email` + middleware (90 kB).
- Monorepo yapısı düzgün: `apps/` · `packages/` · `e2e/` · `evals/` · `infra/` · `migrations/`.
- Depodaki en büyük kod tabanı (8033 dosya, 376 test dosyası).

## Ne çalışmıyor / doğrulanmadı

- **187 deselect edilen test koşmadı** — muhtemelen DB/entegrasyon isteyenler, doğrulanmadı.
- **E2E koşulmadı** (`test:e2e`, `e2e:seed`) — gerçek tarayıcı akışı doğrulanmamış durumda.
- Uygulama ayağa kaldırılmadı.

## Ne yarım

- `LEGAL_TODO.md` açık — hukuki maddeler kapanmamış.
- `feat/faz3-sprint-3.3` dalı duruyor.
- 9 dosyada commit edilmemiş değişiklik vardı (CSP, login formu, middleware, e2e) —
  bu denetimde commit edildi.

## Sonraki adım

`test:e2e` koştur. Geçerse bu proje kapanış standardına en yakın olan.
