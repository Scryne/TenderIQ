# TenderIQ — Claude Code için Skill Haritası

Proje planını (v1.0) baz alarak, Claude Code'da `/mnt/skills` altına (veya proje içindeki `.claude/skills/` klasörüne) eklemen gereken skill'leri, mimarindeki 5 katmana göre gruplandırdım. Her biri için: **neden gerekli**, **skill içeriğinde ne olmalı**, **öncelik**.

> Not: Bunların çoğu "hazır indirilecek" skill değil, kendi projene özel yazman gereken (skill-creator ile üretebileceğin) custom skill'ler. Bazıları ise genel iyi pratik skill'leri (herkesin projesine uyarlanabilir).

---

## 1. Öncelik Sırası (Faz Planına Göre)

| Faz | Hafta | O fazda en kritik skill'ler |
|---|---|---|
| Faz 0 | 0-2 | `multi-tenant-fastapi`, `docker-compose-scaffold`, `github-actions-cicd` |
| Faz 1 | 3-6 | `hybrid-document-parsing`, `chunking-strategy`, `pgvector-indexing`, `celery-async-jobs` |
| Faz 2 | 7-10 | `langgraph-extraction-agents`, `structured-output-grounding`, `golden-set-eval`, `langfuse-observability` |
| Faz 3 | 11-13 | `review-ui-source-highlight`, `docx-xlsx-export`, `payment-integration-tr` |
| Faz 4 | 14+ | `kvkk-compliance-checklist`, `trust-page-content` |

---

## 2. Backend / API Katmanı (FastAPI, Python)

### `multi-tenant-fastapi`
- **Neden:** Tüm veri modeli `tenant_id` + PostgreSQL RLS üzerine kurulu. Bu yanlış kurulursa kiracılar arası veri sızıntısı riski var (Bölüm 10.1'deki en kritik tehdit).
- **İçerik:** RLS politika şablonları, SQLAlchemy session'a `tenant_id` enjekte eden middleware, her yeni tablo eklendiğinde RLS policy oluşturmayı hatırlatan checklist, test şablonu (bir kiracının diğerinin verisini göremediğini doğrulayan).
- **Öncelik:** Yüksek — Faz 0.

### `async-job-state-machine`
- **Neden:** `queued → parsing → indexing → extracting → review_ready → failed` durum makinesi tüm ürünün omurgası (Bölüm 5.5).
- **İçerik:** Celery task idempotency pattern'leri, SSE/WebSocket ile durum yayınlama, retry/backoff stratejisi, hata durumunda kısmi iş tekrarını önleme.
- **Öncelik:** Yüksek — Faz 1.

### `rest-api-conventions`
- **Neden:** Bölüm 9.1'de tanımlanan ilkeleri (Idempotency-Key, 202 + job id, tutarlı hata modeli, `/api/v1` versiyonlama) her yeni endpoint'te tutarlı uygulamak için.
- **İçerik:** Pydantic response/error şemaları, FastAPI router şablonu, OpenAPI doc otomasyonu.
- **Öncelik:** Orta — Faz 0-1.

---

## 3. AI / ML İşleme Hattı (Projenin Kalbi — Bölüm 6)

### `hybrid-document-parsing`
- **Neden:** Docling (dijital) + VLM/LlamaParse (taranmış) yönlendirmesi hattın kalite darboğazı. Yanlış yönlendirme her şeyi zehirliyor.
- **İçerik:** Sayfa bazında "dijital metin var mı" tespiti, bounding-box/konum koordinatı çıkarma standardı, hata durumunda fallback zinciri, test dokümanları ile regresyon kontrolü.
- **Öncelik:** Kritik — Faz 0 (spike) ve Faz 1.

### `structure-aware-chunking`
- **Neden:** Naif chunking gereksinimi cümle ortasından bölüp anlamı bozuyor (Bölüm 6.3).
- **İçerik:** Başlık/madde/tablo sınırına göre bölme kuralları, metadata zenginleştirme (bölüm başlığı + konum), chunk boyutu/overlap parametreleri.
- **Öncelik:** Yüksek — Faz 1.

### `langgraph-extraction-agents`
- **Neden:** 6 farklı ajan (Requirement, Deliverables, Risk, Timeline, Compliance, Cost) LangGraph ile orkestrasyon gerektiriyor (Bölüm 6.7).
- **İçerik:** Her ajan için Pydantic şema şablonu, durumlu graph tasarım pattern'i, ajan hata durumunda yeniden deneme/dallanma mantığı, ajanlar arası bağlam paylaşımı.
- **Öncelik:** Kritik — Faz 2.

### `structured-output-grounding`
- **Neden:** Ürünün güven temeli burada (Bölüm 6.9, 4.2). Kaynağa bağlanamayan hiçbir bulgu gösterilmemeli — bu kural her yeni ajanda tekrar tekrar uygulanacak.
- **İçerik:** Şema doğrulama + reddetme/yeniden isteme mantığı, "kaynak konum zorunlu" alan kontrolü, düşük-güven işaretleme kuralları, grounding testi şablonları.
- **Öncelik:** Kritik — Faz 2.

### `hybrid-retrieval-rerank`
- **Neden:** Sadece semantik arama madde kodu/standart numarası gibi tam eşleşmeleri kaçırıyor (Bölüm 6.6).
- **İçerik:** BM25 + semantic arama birleştirme, reranker entegrasyonu, ihale/mevzuat terimlerine özel test sorguları.
- **Öncelik:** Orta — Faz 2.

### `golden-set-eval`
- **Neden:** "AI çalışıyor mu?" sorusu ölçülebilir olmalı (Bölüm 6.10); en kritik metrik "kaçırılan zorunlu belge oranı".
- **İçerik:** Etiketlenmiş örnek şartname formatı, precision/recall hesaplama scripti, LLM-as-judge prompt şablonu, her prompt/model değişikliğinde otomatik regresyon testi.
- **Öncelik:** Yüksek — Faz 1 sonundan itibaren sürekli.

### `llm-cost-routing`
- **Neden:** Belge başına maliyet marjı doğrudan tehdit ediyor (Bölüm 13, Risk tablosu). Model yönlendirme + prompt caching zorunlu.
- **İçerik:** Basit/karmaşık görev ayrımı kuralları, prompt caching şablonları, Langfuse ile maliyet izleme entegrasyonu.
- **Öncelik:** Orta — Faz 2-3.

### `langfuse-observability`
- **Neden:** Her LLM çağrısının izlenmesi (Bölüm 6.11) hem maliyet hem kalite kör noktasını kapatıyor.
- **İçerik:** Trace/span kurulum şablonu, prompt versiyonlama pattern'i, dashboard sorguları.
- **Öncelik:** Orta — Faz 2.

---

## 4. Veri Katmanı

### `pgvector-schema-migrations`
- **Neden:** Alembic ile pgvector kolonları, RLS politikaları ve embedding boyutlarının tutarlı yönetimi (Bölüm 8, 6.5).
- **İçerik:** Migration şablonları, vektör index (ivfflat/hnsw) oluşturma kuralları, tenant-scoped index stratejisi.
- **Öncelik:** Yüksek — Faz 1.

### `soft-delete-kvkk-erasure`
- **Neden:** KVKK silme talepleri için kalıcı silme akışı ayrı bir teknik gereksinim (Bölüm 8.3, 10.4).
- **İçerik:** Soft-delete pattern'i + zamanlanmış hard-delete job'ı, ilişkili tüm tablolarda (Document, Chunk, Embedding, ParsedElement) kademeli silme.
- **Öncelik:** Orta — Faz 3-4.

---

## 5. Frontend (Next.js / React)

### `document-preview-highlight`
- **Neden:** Kaynak izlenebilirliğinin görsel karşılığı — kullanıcı bulguya tıklayınca dokümanın tam yerinin vurgulanması (Bölüm 4.2, 7.1). Ürünün en farklılaştırıcı UX'i.
- **İçerik:** PDF.js/react-pdf üzerine bounding-box vurgu katmanı, sayfa senkronizasyonu, performans (yüzlerce sayfalık PDF) optimizasyonları.
- **Öncelik:** Yüksek — Faz 3.

### `review-approval-workflow-ui`
- **Neden:** İnsan-döngüde doğrulama üç durumlu (bekliyor/onaylandı/düzeltildi) akış gerektiriyor (Bölüm 4.3).
- **İçerik:** Optimistic update pattern'i, toplu onay/red, düzenleme geçmişi UI şablonları.
- **Öncelik:** Orta — Faz 3.

### `sse-live-status`
- **Neden:** İş durumu makinesinin canlı yansıtılması (Bölüm 5.5, 9.3) TanStack Query ile senkron çalışmalı.
- **İçerik:** SSE bağlantı yönetimi, yeniden bağlanma mantığı, durum-bazlı UI bileşenleri.
- **Öncelik:** Orta — Faz 1-3 arası.

---

## 6. Doküman Üretimi / Dışa Aktarım

### `docx` / `xlsx` (Anthropic'in hazır skill'leri)
- **Neden:** Bölüm 4.1'de "Dışa aktarım: Word/Excel formatında yapılandırılmış rapor" MVP zorunluluğu. Bu skill'ler zaten Claude Code'da mevcut — kendi export şablonlarını bunların üzerine inşa edebilirsin.
- **Ek olarak oluşturman gereken:** `tenderiq-report-template` — firma logosu, gereksinim/risk/belge tablolarının tutarlı biçimlendirmesi, kaynak referanslarının (sayfa no) footnote olarak eklenmesi için proje-özel şablon skill'i.
- **Öncelik:** Yüksek — Faz 3.

---

## 7. DevOps / Altyapı

### `docker-compose-scaffold`
- **Neden:** Tüm servislerin (API, worker, DB, Redis, frontend) tutarlı yerel ortamı (Bölüm 11.2).
- **İçerik:** Servis bazlı Dockerfile şablonları, healthcheck'ler, .env yönetimi.
- **Öncelik:** Yüksek — Faz 0.

### `github-actions-cicd`
- **Neden:** Lint → test (altın-set regresyonu dahil) → güvenlik taraması → build → deploy hattı (Bölüm 11.3).
- **İçerik:** Workflow şablonları, AI regresyon testinin CI'a entegrasyonu, staging/production ayrımı.
- **Öncelik:** Yüksek — Faz 0.

### `sentry-error-tracking`
- **Neden:** Backend/frontend hata izleme (Bölüm 11.6).
- **İçerik:** Kurulum şablonu, tenant_id'yi hata bağlamına ekleme (debug kolaylığı, ama PII sızdırmadan).
- **Öncelik:** Düşük-Orta — Faz 1.

---

## 8. Güvenlik / Uyumluluk

### `kvkk-compliance-checklist`
- **Neden:** Bölüm 10.4 — aydınlatma metni, açık rıza, veri sahibi hakları, saklama politikaları teknik değil ama ürüne gömülü olması gerekiyor.
- **İçerik:** Her yeni veri toplama noktasında kontrol listesi, DPA şablonu, alt-işleyen (sub-processor) listesi güncelleme hatırlatıcısı.
- **Öncelik:** Orta — Faz 4 öncesi ama tasarım aşamasından itibaren akılda tutulmalı.

### `zero-retention-llm-config`
- **Neden:** Hassas ihale dokümanlarının LLM sağlayıcısına gönderilmesi en büyük güven riski (Bölüm 10.3).
- **İçerik:** API çağrılarında veri saklamama/eğitimde kullanmama ayarlarının doğrulanması, veri minimizasyonu (gereksiz PII maskeleme) kuralları.
- **Öncelik:** Yüksek — Faz 2'den itibaren her LLM entegrasyonunda.

---

## 9. Ödeme / İş Modeli

### `payment-integration-tr`
- **Neden:** iyzico/PayTR (yerel) + Stripe (global) hibrit entegrasyonu, kota takibiyle bağlantılı (Bölüm 14.3).
- **İçerik:** Abonelik/kota senkronizasyon pattern'i, webhook doğrulama, UsageRecord güncelleme mantığı.
- **Öncelik:** Orta — Faz 3.

---

## Özet — Kurulum Sırası Önerisi

1. **Hemen (Faz 0):** `multi-tenant-fastapi`, `docker-compose-scaffold`, `github-actions-cicd`
2. **Faz 1'de ekle:** `hybrid-document-parsing`, `structure-aware-chunking`, `pgvector-schema-migrations`, `async-job-state-machine`, `golden-set-eval`
3. **Faz 2'de ekle:** `langgraph-extraction-agents`, `structured-output-grounding`, `hybrid-retrieval-rerank`, `langfuse-observability`, `zero-retention-llm-config`
4. **Faz 3'te ekle:** `document-preview-highlight`, `review-approval-workflow-ui`, `docx`/`xlsx` + `tenderiq-report-template`, `payment-integration-tr`
5. **Faz 4'te ekle:** `kvkk-compliance-checklist`

Bunların hepsini kendin sıfırdan yazmak zorunda değilsin — Claude Code'daki **skill-creator** aracını kullanarak, bu listedeki her madde için "neden/içerik" kısmını prompt olarak verip skill iskeletini otomatik oluşturtabilirsin, sonra kendi kod pattern'lerinle doldurursun.
