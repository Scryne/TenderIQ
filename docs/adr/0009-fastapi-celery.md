# ADR-0009: Backend — FastAPI + Celery/Redis

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-03
- **Karar veren:** Berkay (Scryne)

## Bağlam
Doküman işleme dakikalarca sürebilir (yüzlerce sayfa); senkron istek/yanıt uygun
değildir. API async-öncelikli olmalı ve uzun işler arka planda kuyrukla yürümelidir.

## Karar
- **API:** FastAPI (async-öncelikli, otomatik OpenAPI/şema, Pydantic doğrulama).
- **Asenkron işleme:** Celery + Redis (broker/backend). İş durum makinesi
  (`queued→parsing→indexing→extracting→review_ready→failed`) task'ları idempotent
  tasarlanır; bir adım hata alırsa tüm iş tekrarlanmadan yeniden denenir.
- **ORM/migrasyon:** SQLAlchemy 2.0 (async runtime) + Alembic (senkron migration).

## Sonuçlar
**Olumlu:** Mevcut deneyimle (Celery/Redis) uyum; olgun kuyruk; otomatik API dokümanı;
tip-güvenli sözleşme temeli.
**Ödünler:** Async + sync sınırlarının (ör. Alembic senkron) yönetimi; Windows'ta
psycopg async event-loop uyumu için selector politikası shim'i gerekir (main.py).

## Alternatifler
- **Flask:** Deneyim transfer olur ama async ve otomatik şema için FastAPI üstün.
- **RQ / Dramatiq:** Daha basit ama Celery'nin olgunluğu ve mevcut deneyim tercih edildi.

## İlgili
Geliştirme Planı §B.3, Faz 1 (durum makinesi); Ürün Planı §5.5, §7.2.
