# ADR-0002: Vektör deposu olarak pgvector

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-03
- **Karar veren:** Berkay (Scryne)

## Bağlam
RAG hattı, doküman parçalarının (chunk) embedding vektörlerini saklayıp anlamsal
arama yapmayı gerektirir. Seçenekler: ayrı bir vektör veritabanı (Qdrant/Weaviate/
Pinecone) veya PostgreSQL eklentisi pgvector.

## Karar
Başlangıçta **pgvector** kullanılır. Yapısal veri ve vektörler aynı PostgreSQL'de
tutulur. `0001_pgvector` migration'ı `CREATE EXTENSION vector` ile eklentiyi kurar.

## Sonuçlar
**Olumlu:** Tek veritabanı → tek geliştirici için minimum operasyonel yük; işlemsel
tutarlılık (vektör + metadata aynı transaction); RLS ile kiracı izolasyonu doğrudan
uygulanabilir.
**Ödünler:** Çok yüksek ölçekte özel vektör DB'lerin bazı performans/özellikleri
eksik kalabilir.

## Alternatifler
- **Qdrant/Weaviate/Pinecone:** Güçlü ama ayrı servis, ayrı izolasyon modeli, ek
  operasyon. Ölçek büyüdüğünde geçiş için mimari hazır tutulur (retrieval katmanı
  soyutlanır).

## İlgili
Geliştirme Planı §B.1 (`packages/core/indexing`), Ürün Planı §6.5.
