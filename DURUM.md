# DURUM — TenderIQ

> Envanter, sertifika değil. Ayrıntılı operasyon gerçeği ve tuzaklar: `docs/ops/DURUM.md`.

**Ölçüm tarihi:** 2026-11-14 (bitirme denetimi; önceki 2026-09-25, `a841367`)

## 2026-11-13/14: bitirme denetimi

- **Bulunan hata (LLM izleme):** Langfuse adaptörü `start_as_current_generation` çağırıyordu; bu metot
  langfuse 4.15.6'da da 5.2.0'da da yok. Anahtar tanımlanınca her LLM çağrısı düşerdi; testteki sahte istemci
  aynı adı taklit ettiği için görünmüyordu. `start_as_current_observation(as_type="generation")`; gerçek
  SDK'nın iki sürümüyle (ağsız) sürüldü.
- **Windows'ta API:** uvicorn 0.36+ olay döngüsünü politikadan değil `--loop`tan kuruyor; Windows varsayılanı
  Proactor → giriş 500. `--loop asyncio:SelectorEventLoop` (`api:dev`, E2E); E2E'de `--reload` kalktı.
- **Yerel önizleme yedeği:** `scripts/yerel_depo.py` (yalnız localhost S3 ucuna yazar) + kurgusal
  `scripts/fixtures/ornek-sartname.pdf` (`scripts/ornek_sartname.mjs`): R2'siz geliştirmede inceleme ekranı
  PDF'i açıp kaynağı vurguluyor.
- **Ön yüz:** favicon yoktu (her sayfada konsol 404); istemci sayfalarında sekme başlığı yalnız "TenderIQ"
  → "<Sayfa> · TenderIQ"; hukuki sayfalarda çift marka; olmayan ihale "Yeniden dene" yerine "İhale
  bulunamadı"; `tw-animate-css` eksikti (diyalog/menü animasyon sınıfları tanımsızdı).
- **Bağımlılık:** Dependabot #52, #53, #54, #55 (langfuse 5) yerelde birleşti; #24 (TypeScript 7) hâlâ üst
  akıma bağlı (typescript-eslint 8.72.2 `<6.1.0`, openapi-typescript 7.13.0 `^5.x`). dnspython 2.9.2
  (CVE-2026-128089).
- **Gezinti:** 24 rota × 390/768/1280/1440 × açık/koyu = 192 kare, taşma 0. Asıl akış tarayıcıda: yükleme
  (imzalı PUT → `/complete` → kuyruk), inceleme (PDF + vurgu), onay, Word/Excel dışa aktarma (kaynak
  sayfa/madde/alıntıyla). **Yerelde sınanamayan:** analiz adımı (worker ayrıştırma grubu docling+torch kurulu
  değil, projede kayıtlı LLM yanıt kipi yok) ve `-m integration` (testcontainers/Docker).
- **Bilerek bırakılan:** `/capability` profil yokken 404 (API sözleşmesi, entegrasyon testi bunu bekliyor;
  tarayıcı konsoluna bir satır düşüyor); inceleme kategori segmenti 1280'de 23 px yatay kaydırma.

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
- Uzak `feat/faz3-sprint-3.3` dalı duruyor. Dependabot: Next 16 (#48), anthropic 2.3 ve openai 3.42 (#49) birleşti;
  karşılanan PR'lar kapatıldı, TypeScript 7 (#24) üst akım desteği bekliyor.
- Anthropic 2.x gerçek API'yle denenmedi: yayın öncesi `live_sandbox` koşusu şart.

## Bağımlılık turu (2026-11-03)

Açık 9 Dependabot PR'ının 6'sı (#45, #44, #28, #36, #35, #33) `denetim/bagimlilik` dalındaki
commit'lerle uygulandı; her biri ayrı commit, Dependabot dalından değil main'den yeniden kilitlendi.

- **Kırmızıların sebebi kod değildi:** #45 pip-audit (`opentelemetry-api` 1.44.0, fastapi 0.162 ile
  üretime girdi → 1.45.2), #44 trivy (main'deki pypdf 6.21.3 → 6.21.4), #36/#35 o tarihteki
  main'in urllib3/langgraph-sdk açıkları. Tek kod kırığı #28: redis 8 tipleri düzelince
  `dead_letter.py`'deki 3 `type: ignore` gereksiz kaldı.
- **Sentry 11 PII duruşu korundu:** `sendDefaultPii` kalktı, yeni `dataCollection`ın varsayılanı
  "her şeyi topla". `src/lib/sentry-data-collection.ts` eski `false` eşlemesinin karşılığı.
- **Gizli kırık düzeltildi:** `brace-expansion: >=5.0.9` override'ı minimatch@3'e 5.x'i zorluyor,
  süslü desende `expand is not a function` veriyordu. Override majör hatlara bölündü; `pnpm audit`
  brace-expansion için temiz.
- **#32/#31 Next 16 — ayrı dalda ele alındı (`claude/keen-johnson-13qdrz`, PR açık, birleştirilmedi).**
  Turbopack'e geçildi (`canvas` takma adı `turbopack.resolveAlias`ta), `middleware.ts` → `proxy.ts`
  (Node çalışma zamanı; depolama origin'i `next.config.ts` `env` ile derlemede dondurulur,
  çalışma anı değeri etkisiz — üretim derlemesinde ölçüldü), eslint yerel flat config,
  react-hooks 7'nin beş hatası kural kapatılmadan düzeltildi. Ayrıntı ve doğrulanamayanlar PR'da.
- **Aşağıdaki erteleme notu geçmiş kayıttır:** #32/#31 Next 16 — Turbopack varsayılan, özel `webpack` yapılandırması
  (pdfjs `canvas` alias'ı) derlemeyi düşürüyor; `middleware` → `proxy` geçişi CSP nonce'una dokunuyor;
  react-hooks 7 beş UI dosyasında hata veriyor (görsel doğrulama turu gerekir). #24 TypeScript 7 —
  `openapi-typescript` (`createKeywordTypeNode` TypeError) ve typescript-eslint (`<6.1.0`) desteklemiyor.
- Doğrulama (yerel): ruff, mypy strict, pytest (414 geçti, 1 atlandı), OpenAPI/TS drift yok,
  golden-set kapısı; web lint, tsc, `next build` (26 rota). Entegrasyon, E2E, trivy CI'da.
- **Yeniden değerlendirme (Next 16 #48 sonrası):** #45, #28, #33, #31, #32 main'de zaten
  karşılanmış (sürümler PR hedefinde ya da üstünde). Kalan iki majör/minör uygulandı:
  **anthropic 1.11 → 2.3 (#36)** — SDK artık `anthropic-version: 2026-10-21` gönderir
  (`temperature`/`top_p`/`top_k` 400 döner; Anthropic dalı göndermiyor) ve anahtarı
  `Authorization: Bearer` ile taşır. `messages.parse` yüzeyi sahte taşıyıcıyla eski/yeni
  karşılaştırıldı, fark yalnız bu iki başlık. **openai 3.23 → 3.42 (#35)** — tel yüzeyi birebir
  aynı. Kalıcı kapı: `packages/core/tests/test_llm_sdk_wire.py` (gerçek SDK, ağ yok).
  #24 TypeScript 7 bilinçli dışarıda.
