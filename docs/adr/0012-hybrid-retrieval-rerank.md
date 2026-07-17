# ADR-0012: Hibrit Getirim — pgvector (semantik) + süreç-içi BM25 + RRF + Cross-Encoder Reranker

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-17 (Sprint 2.1)
- **Karar veren:** Berkay (Scryne)

## Bağlam
Çıkarım ajanlarının bağlam kalitesi = ürün kalitesi (§6.6; kaçırılan zorunlu
madde riski getirimde başlar). Salt semantik getirim tam terim/numara
isabetinde zayıftır ("Madde 26", "%3", "ISO 27001"); salt anahtar kelime
Türkçe morfolojide zayıftır ("teminatı" ≠ "teminat"). Getirim kapsamı her
zaman **tek ihalenin dokümanlarıdır** (10²–10³ chunk) — küresel arama değil.

## Karar 1 — İki yol + RRF birleştirme
- **Semantik:** pgvector cosine (HNSW, ADR-0002/0008); model filtresi zorunlu
  (`Embedding.model`), kiracı filtresi RLS'ten (ADR-0003).
- **Anahtar kelime:** **süreç-içi Okapi BM25** (`tenderiq_core/retrieval/keyword.py`),
  TR-farkında tokenizasyonla (İ/I katlaması; noktalama böler, gövde eki
  stem'lenmez — morfolojiyi semantik yol taşır). **Postgres FTS değil**, çünkü:
  korpus belleğe sığar, skor deterministiktir (CI'da tekrarlanabilir), TR
  tokenizasyon kontrolü bizdedir ve ek indeks/migration gerekmez. 1M+ chunk'lık
  kiracılar-üstü arama ihtiyacı doğarsa FTS/GIN yükseltme yoludur.
- **Birleştirme:** Reciprocal Rank Fusion (k=60) — skorları değil SIRALARI
  birleştirir; ölçek normalizasyonu istemez, iki listede birden geçen adayı
  doğal öne çeker. Eşitlikler chunk `seq`'iyle kırılır (deterministik).
- İki yol da embedding ile aynı metni görür (bölüm başlığı öne eklenmiş —
  `ChunkDraft.embedding_input` ile aynı kural).

## Karar 2 — Reranker: BGE reranker v2-m3 (cross-encoder), kapatılabilir
- RRF'in ilk ~32 adayı `BAAI/bge-reranker-v2-m3` ile yeniden sıralanır
  (çok dilli, BGE-M3 ailesi; sentence-transformers `CrossEncoder`, lazy yükleme).
- Embedding katmanıyla aynı desen: `Reranker` protokolü + `create_reranker()`
  fabrikası; `RETRIEVAL_RERANKER_PROVIDER=none` reranker'ı kapatır (RRF sırası
  nihai olur) — hafif ortamlar/CI testleri bu modda koşar. Paketleme: kök
  `embedding` grubu (torch'u BGE-M3 ile paylaşır; yalnız worker imajı).
- Veri süreç dışına çıkmaz (KVKK yüzeyi büyümez; zero-retention tartışması
  reranker için hiç açılmaz).

## Karar 3 — Korpus modeli ve oturum sınırı
- Korpus faz başında TEK sorguyla yüklenir (`load_corpus`), BM25 indeksi
  bellekte kurulur; sorgu başına yalnız kısa pgvector SQL'i oturum açar
  (closure enjeksiyonu — uzun süren embedding/rerank hesabı transaction
  DIŞINDA, Sprint 1.2/1.3 deseniyle simetrik).
- Ajan başına bağlam: sorgu şablonu birleşimi + chunk başına en iyi skor +
  tavan (`RETRIEVAL_AGENT_CONTEXT_LIMIT`). Tüm eşikler ayarlardan; kalibrasyon
  golden-set ile Sprint 2.4'te.

**Alternatifler:**
- **BGE-M3 sparse (lexical) çıktısı** BM25 yerine: tek modelden iki temsil
  cazip ama sparse vektör saklama/sorgulama altyapısı (ek kolon + skorlama)
  kurmayı gerektirir; BM25 sıfır bağımlılıkla aynı işi görür. Golden-set'te
  anahtar-kelime bacağı zayıf çıkarsa yeniden değerlendirilir.
- **Yönetilen reranker (Cohere Rerank, Voyage):** kalite iyi ama belge başına
  yinelenen maliyet + veri işleyici sözleşmesi; OSS-önce ilkesine aykırı.

## Sonuçlar
**Olumlu:** tam terim + semantik isabet birlikte; deterministik/test edilebilir;
sıfır ek altyapı (Redis/ES yok); reranker kapatılabilir olduğundan geliştirme
hafif kalır.
**Ödünler:** BM25 indeksi her extracting koşumunda yeniden kurulur (küçük korpusta
ihmal edilebilir); reranker CPU'da aday başına ~10-50 ms (32 aday × 16 sorgu ≈
saniyeler — asenkron hat içinde kabul edilebilir, GPU yolu ADR-0011 ile ortak);
RRF/k ve top-k eşikleri kalibre edilmedi (2.4 golden-set kapısında).

## İlgili
ADR-0002 (pgvector), ADR-0005 (LangGraph), ADR-0008 (BGE-M3), Geliştirme Planı
Sprint 2.1, §6.6.
Kod: `packages/core/src/tenderiq_core/retrieval/`,
`apps/worker/src/tenderiq_worker/extraction.py`.
