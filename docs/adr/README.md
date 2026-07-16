# Mimari Karar Kayıtları (ADR)

Bu klasör, TenderIQ'nun önemli teknik kararlarını gerekçe ve alternatifleriyle
kayıt altına alır. Amaç: "neden böyle yaptık?" sorusunu gelecekte tek bakışta
yanıtlamak ve kararları bilinçli biçimde yeniden değerlendirebilmek.

## Format

Her ADR şu bölümleri taşır: **Durum · Bağlam · Karar · Sonuçlar · Alternatifler**.
Durum değerleri: `Önerilen` → `Kabul edildi` → (gerekirse) `Yerini aldı: ADR-XXXX`.

Yeni ADR eklerken bir sonraki numarayı kullanın (`docs/adr/NNNN-kisa-baslik.md`).

## Dizin

| ADR | Başlık | Durum |
|---|---|---|
| [0001](0001-monorepo.md) | Monorepo (apps + packages) | Kabul edildi |
| [0002](0002-pgvector.md) | Vektör deposu: pgvector | Kabul edildi |
| [0003](0003-rls-multi-tenancy.md) | Çok-kiracılılık: tenant_id + RLS | Kabul edildi |
| [0004](0004-hybrid-parsing.md) | Hibrit parsing: Docling + VLM/OCR fallback | Kabul edildi |
| [0009](0009-fastapi-celery.md) | Backend: FastAPI + Celery/Redis | Kabul edildi |
| [0010](0010-typed-api-contract.md) | Tip-güvenli API sözleşmesi (OpenAPI→TS) | Kabul edildi |
| [0011](0011-ocr-engine.md) | OCR motoru: EasyOCR + CPU-önce kapasite yolu | Kabul edildi |

> Sonraki set (ilgili fazlarda): 0005 LangGraph, 0006 zorunlu grounding,
> 0007 zero-retention LLM, 0008 BGE-M3 embedding. Bkz. Geliştirme Planı §G.
