# ADR-0005: Çıkarım Orkestrasyonu — LangGraph (durumlu, dallanabilir, yeniden denenebilir)

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-17 (Sprint 2.1)
- **Karar veren:** Berkay (Scryne)

## Bağlam
Faz 2'nin kalbi, uzmanlaşmış çıkarım ajanlarının (gereksinim/belge/risk/takvim,
§6.7) RAG bağlamıyla beslenip **her bulguyu kaynağa bağlayarak** çalışmasıdır.
Orkestrasyonun gereksinimleri: ajanlar arası bağlam paylaşımı, paralel koşum
(ajanlar bağımsız), düğüm düzeyi yeniden deneme (LLM geçici hataları) ve
Celery'nin faz-düzeyi idempotent retry'ıyla uyum (§5.5).

## Karar 1 — LangGraph, `StateGraph` + pydantic durum
- Orkestrasyon `langgraph.StateGraph` ile kurulur; durum **pydantic**
  `ExtractionState`'tir (şema-önce, C.8; checkpointing'e hazır serileştirme).
- Topoloji derleme anında sabitlenir (deterministik):
  `retrieve_context → agent_<ad> (paralel) → finalize`. Paralel ajan çıktıları
  **reducer'larla** birleşir: `findings` sözlük-birleşimi, `errors` liste-eki.
- **Bağımlılık enjeksiyonu:** graph, LLM'e/DB'ye/embedding'e doğrudan bağlanmaz;
  `ContextRetriever` ve `AgentRunner` protokolleri enjekte edilir. Birim
  testleri sahtelerle koşar; Sprint 2.2 LLM'li koşucuları aynı protokole kaydeder.

## Karar 2 — Çifte yeniden-deneme katmanı
- **Düğüm içi:** ajan düğümleri `RetryPolicy(max_attempts=3, backoff)` taşır —
  LLM rate-limit/ağ hataları graph içinde emilir.
- **Faz düzeyi:** kalıcı hata graph'tan yükselir → Celery task backoff'la TÜM
  extracting fazını yeniden dener (faz idempotent: 2.1 iskeleti DB'ye yazmaz;
  2.2 bulgu yazımı delete+insert deseniyle idempotent olacak).
- **Hata kanalı ayrımı:** istisna = yeniden denemeye değer; durumdaki `errors`
  listesi = ölümcül olmayan ama görünür kalması gereken sorun (ör. 2.2'de
  grounding reddi). Orkestratör bugün boş-olmayan `errors`'ı faz hatası sayar
  (iskelette bu kanala meşru yazan yok — katı başla, 2.2'de gevşet).

## Karar 3 — Paketleme: `langgraph` core'un SABİT bağımlılığıdır (extra değil)
Ağır yığınlar (docling/OCR/embedding) extra'dır çünkü torch taşır; langgraph
ise saf-Python ve hafiftir (langchain-core + msgpack düzeyi). Extra yapmak,
CI'ın varsayılan kurulumuyla (dev-only `uv sync`) koşan pipeline entegrasyon
testini extracting fazında kırardı. API imajına da girer ama kullanılmaz —
kabul edilen küçük maliyet.

**Alternatifler:**
- **El yazması orkestrasyon (asyncio/Celery chord):** bugün yeterdi ama durum
  paylaşımı, dallanma, düğüm retry'ı ve (ileride) checkpoint/insan-onayı
  duraklarını kendimiz yazardık; LangGraph bunları standartlaştırıyor (§7.5).
- **LangChain AgentExecutor / CrewAI vb.:** ya fazla serbest (döngüsel ajan
  otonomisi — bizim akış deterministik) ya da ek çatı kilidi. LangGraph, graph'ı
  bizim çizdiğimiz kadar deterministik tutuyor.

## Sonuçlar
**Olumlu:** ajan ekleme = koşucu kaydı (topoloji kodu değişmez); paralel koşum
bedava; test edilebilirlik yüksek (protokoller); 2.2 grounding/şema zorlaması
düğüm sınırında doğal yerini bulur.
**Ödünler:** langgraph+langchain-core bağımlılık yüzeyi (sürüm kilidi uv.lock'ta);
API imajında kullanılmayan ~birkaç MB; LangGraph API evrimi (1.x) takip ister.

## İlgili
ADR-0009 (FastAPI+Celery), ADR-0012 (hibrit getirim), Geliştirme Planı Sprint 2.1, §6.7.
Kod: `packages/core/src/tenderiq_core/agents/` (graph/state/context),
`apps/worker/src/tenderiq_worker/extraction.py`.
