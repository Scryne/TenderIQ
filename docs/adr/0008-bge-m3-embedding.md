# ADR-0008: Embedding Modeli — BGE-M3 (OSS, yerel) + Yönetilen Geçiş Opsiyonu

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-17 (Sprint 1.3)
- **Karar veren:** Berkay (Scryne)

## Bağlam
RAG hattı (§6.4) chunk'ları yoğun vektörlere gömüp pgvector'da (ADR-0002)
indeksler. İhale/şartname korpusu ağırlıkla **Türkçe**, mevzuat/ticari terminoloji
yoğun; model çok dilli olmalı ve maliyet-hassas ilke (OSS-önce) gereği belge
başına embedding maliyeti sıfıra yakın tutulmalı. Ayrıca uzun maddeler için
geniş bağlam penceresi gerekir.

## Karar 1 — Model: BGE-M3 (yoğun vektör, 1024 boyut)
- **BAAI/bge-m3**, `sentence-transformers` üzerinden **süreç içinde (worker)**
  çalıştırılır; vektörler **L2-normalize** yazılır → benzerlik **cosine**
  (pgvector `vector_cosine_ops` HNSW indeksiyle tutarlı).
- MVP'de yalnızca **yoğun (dense)** çıktı kullanılır; Sprint 2.1'deki hibrit
  getirimde anahtar-kelime bacağı BM25'ten gelir (BGE-M3'ün sparse çıktısı
  gerekirse o sprintte değerlendirilir).
- Paketleme: `packages/core`'un `embedding` extra'sı (`sentence-transformers`);
  kök `embedding` dependency-group'u bunu işaret eder. Worker imajı
  `--group parsing --group ocr --group embedding` ile kurulur; **API imajı bu
  yığını taşımaz**. Torch zaten docling ile imajda — marjinal maliyet düşük.

**Gerekçe:** 100+ dil desteğinde güçlü çok dilli getirim kalitesi (MIRACL/MTEB
çok dilli kıyaslarında açık kaynak lider grubunda; Türkçe dâhil), 8192 token
bağlam, ücretsiz/OSS, veri dışarı çıkmaz (KVKK yüzeyi küçülür — §10.3
zero-retention tartışması embedding için hiç açılmaz).

**Alternatifler:**
- **Yönetilen embedding API'leri (Voyage, Cohere Embed v3, OpenAI
  text-embedding-3):** kalite iyi ama belge başına yinelenen maliyet + veri
  işleyiciye DPA/zero-retention şartı + ağ gecikmesi. Yükseltme yolu olarak
  saklandı (Karar 2).
- **multilingual-e5-large:** iyi çok dilli taban ama 512 token pencere uzun
  maddelerde kırpma riski; BGE-M3'ün genişliği yapı-farkında chunk'larla daha
  uyumlu.

## Karar 2 — Soyutlama: sağlayıcı fabrikası + boyut sözleşmesi
- Hat, somut modele değil `EmbeddingModel` protokolüne bağlıdır
  (`tenderiq_core/indexing/embedding.py`); `create_embedding_model()` fabrikası
  `EMBEDDING_PROVIDER` ayarını okur (`local` | `managed`). Yönetilene geçiş =
  fabrikaya yeni dal; çağıran kod (worker indexing fazı) değişmez.
- **Boyut sözleşmesi:** DB kolonu sabittir (`vector(1024)`, migration 0006 ↔
  `models.embedding.EMBEDDING_DIM` ↔ `EMBEDDING_DIM` ayarı). Farklı boyutlu
  modele geçiş migration ister; `embedding` tablosu `(chunk_id, model)` tekilliği
  sayesinde **aynı chunk'ın iki modelle vektörünü yan yana** tutabilir — geçişte
  yeniden indeksleme bitene dek eski model hizmet vermeye devam eder.
- Model çıktısı yapılandırılan boyutla uyuşmazsa yazım **hata ile durur**
  (sessiz bozuk veri yerine `EmbeddingDimensionError`).

## Kapasite yolu (ADR-0011 ile aynı desen: CPU-önce)
1. **Şimdi (Faz 1–2):** CPU'da batch embedding kabul edilir (hat asenkron;
   chunk başına ~yüzlerce ms). Ek maliyet: 0.
2. **Ölçekte:** OCR için gelecek GPU worker'ı (ADR-0011) embedding'i de
   hızlandırır — aynı imaj, aynı torch.
3. **Fallback:** işletim yükü ağırlaşır ya da kalite yetmezse `managed`
   sağlayıcı dalı açılır (zero-retention/DPA şartıyla, ADR-0007 ilkesi).

## Sonuçlar
**Olumlu:** sıfır marjinal maliyet; veri süreç dışına çıkmaz; çok dilli güçlü
taban; model geçişi için şema/sözleşme hazır.
**Ödünler:** worker imajı büyür (ST + model ağırlıkları ~2 GB, ilk koşumda
indirilir — imaja gömme/ön-ısıtma Faz 4 optimizasyonu); CPU'da büyük dokümanın
embedding'i saniyeler-dakikalar alır; boyut değişikliği migration ister.

## İlgili
ADR-0002 (pgvector), Geliştirme Planı Sprint 1.3, §6.4–6.5.
Kod: `packages/core/src/tenderiq_core/indexing/embedding.py`,
`packages/core/src/tenderiq_core/models/embedding.py`,
`migrations/versions/0006_chunk_embedding.py`,
`apps/worker/src/tenderiq_worker/indexing.py`,
`infra/docker/worker.Dockerfile` (embedding grubu).
