# ADR-0004: Hibrit Doküman Ayrıştırma (Docling + VLM/OCR fallback)

- **Durum:** Kabul (2026-07-04 — dijital **ve** taranmış yol gerçek TR şartnameleriyle doğrulandı; bkz. §"Gerçek Doküman Spike Bulguları")
- **Tarih:** 2026-07-03 (güncelleme: 2026-07-04 gerçek doküman doğrulaması)
- **Karar veren:** Berkay (Scryne)

## Bağlam
Şartnameler heterojendir: metin katmanlı **dijital** PDF, **taranmış** (görüntü) PDF ve
**tablo-yoğun** dokümanlar (fiyat cetveli, teknik tablolar) bir arada gelir. Ürünün
yapısal temeli citation-first'tür: her bulgu bir kaynağa (sayfa + konum) bağlanmak
**zorundadır** (§6.9, ADR-0006). Bu nedenle ayrıştırma katmanı yalnızca metin değil,
**her öğe için sayfa + bounding box** üretmek zorundadır.

Bu, projenin **en riskli teknik varsayımıdır** (A.4/5, §12.6): gerçek TR şartnamelerinde
yeterli metin **ve konum koordinatı** çıkarılabilir mi? Kullanıcı maliyet-hassas ve
OSS-önce yaklaşımı tercih eder → ücretsiz/açık kaynak ayrıştırma birincil yol olmalıdır.

## Karar
- **Docling (OSS) birincil ayrıştırıcıdır.** Dijital PDF'lerde her öğe (başlık, paragraf,
  madde, tablo) için **sayfa + bbox + okuma sırası** çıkarır.
- **Sayfa-bazlı hibrit yönlendirme (§6.2):** "dijital metin var mı" tespiti (`pypdf`) →
  dijital sayfa = Docling (`do_ocr=False`); taranmış/karmaşık = **VLM/OCR** yolu
  (Docling `do_ocr=True` veya VLM fallback). Faz 0'da yönlendirme doküman düzeyindedir;
  gerçek sayfa-bazlı yönlendirme Faz 1 Sprint 1.2'de.
- **bbox TOPLEFT origin'e normalize edilir** → Faz 3'teki PDF.js/react-pdf vurgu
  katmanına doğrudan eşlenir (dönüşüm ayrıştırma anında bir kez yapılır).
- **Sözleşme sabittir:** `DocumentParser` Protocol + `ParsedDocument` /
  `ParsedElement(text, page, bbox, kind, section)`. Somut uygulama (Docling/VLM/yönetilen)
  değişse de tüketiciler (chunking, indexing) etkilenmez.
- **Paketleme:** Docling ağırdır (torch/transformers). Faz 0'da opsiyonel `parsing`
  bağımlılık grubu (`uv sync --group parsing`); docling importları **lazy** tutulur, böylece
  `apps/api` docling'siz çalışır. Faz 1'de docling `packages/core`'un opsiyonel extra'sına
  taşınıp yalnızca `apps/worker` tarafından tüketilecek.

## Spike Bulguları (2026-07-03)
Gerçekçi bir sentetik TR şartnamesi (2 sayfa: başlıklar, paragraflar, madde listesi,
fiyat cetveli tablosu, cezai şart maddesi) Docling ile ayrıştırıldı:

| Ölçüt | Sonuç |
|---|---|
| Sayfa yönlendirme | 2/2 dijital doğru tespit → Docling(`do_ocr=False`) |
| Öğe çıkarımı | 13 öğe: 5 başlık, 4 paragraf, 3 madde, 1 tablo |
| **BBOX kapsamı** | **%100** — her öğe sayfa + konum taşıyor |
| Türkçe metin | Kusursuz (İ, ş, ğ, ç, ü, ı doğru çıktı) |
| Tablo yapısı | Algılandı, satır/sütun markdown olarak çıkarıldı |
| Bölüm metadata | Başlıklar sonraki öğelere `section` olarak eşlendi |

**Sonuç:** Dijital yolda kaynak izlenebilirliğinin (page + bbox) teknik fizibilitesi
**kanıtlandı**. Kanıt: `scripts/parsing_spike.py` (çalıştırılabilir spike) +
`packages/core/tests/integration/test_docling_parser.py` (kalıcı regresyon testi,
`integration` işaretli).

## Gerçek Doküman Spike Bulguları (2026-07-04)
Berkay'in yüklediği **24 gerçek TR şartnamesi** (`spike-docs/`; Sağlık Bakanlığı /
Malatya İl Sağlık Müdürlüğü ağırlıklı: idari şartname, sözleşme tasarısı, teknik
şartname, yaklaşık maliyet cetvelleri, teklif mektubu, personel/hizmet şartnameleri)
`pypdf` ile triyaj edildi, sonra Docling ile ayrıştırıldı.

**Korpus dağılımı — kritik strateji bulgusu:** 24 belgenin **11'i dijital, 13'ü taranmış
(~%54)**. Yani bu dikeyde **OCR bir "fallback" değil, çoğunluk yoldur** (ıslak imza + mühür
zorunluluğu → yazdır-tara döngüsü). Maliyet/throughput bütçesi buna göre kurulmalı.

**Dijital yol (7 belge, ~67 sayfa; `do_ocr=False`):**

| Belge | Sayfa | Öğe | Tablo | BBOX |
|---|---|---|---|---|
| idari şartname | 15 | 325 | 2 | **%100** |
| sözleşme tasarısı | 12 | 265 | 2 | **%100** |
| teknik şartname-1 | 29 | 646 | 0 | **%100** |
| 3-kalem malzeme | 3 | 29 | 0 | **%100** |
| yaklaşık maliyet cetveli | 2 | 105 | 5 | **%100** |
| yaklaşık maliyet (istek) | 4 | 25 | 4 | **%100** |
| üst yazı yaklaşık maliyet | 2 | 20 | 1 | **%100** |

**Taranmış yol (2 belge, 12 sayfa; Docling `do_ocr=True` + EasyOCR `lang=['tr','en']`):**

| Belge | Sayfa | Öğe | BBOX | Süre | Türkçe kalite |
|---|---|---|---|---|---|
| bt-raporlama (teleradyoloji) | 6 | 75 | **%100** | 120s | Orta — gürültülü tarama; diakritik hataları (ğ→g, ş→$, İ→i) |
| tıbbi sekreter kıyafet | 6 | 140 | **%100** | 136s | İyi — temiz taramada neredeyse kusursuz (Ğ/İ/Ü/Ş doğru) |

**Sonuç:** Her iki yolda da **%100 bbox kapsamı** — kaynak izlenebilirliği (page + bbox)
gerçek dokümanlarda kanıtlandı. Başlık/paragraf/madde/tablo/bölüm yapısı **OCR'lı içerikte
bile** çıkarılıyor. Faz 0 parsing çıkış kapısı **karşılandı**.

**Nüanslar / doğrulanan kararlar:**
- **Türkçe OCR kalitesi tarama kalitesine bağlı:** temiz → neredeyse kusursuz; gürültülü →
  diakritik hataları. Retrieval/embedding (BGE-M3 diakritik-toleranslı) için yeterli; ama
  **birebir citation için gürültülü taramalarda VLM fallback gerekli** → ADR-0004 hibrit
  kararı doğrulandı (salt-OCR yetmez).
- **Performans:** dev ortamında torch **CPU-only** ("no accelerator found") → ~20–22 sn/sayfa
  OCR. %54 taranmış korpusta ölçekte darboğaz/maliyet → Faz 1'de GPU (CUDA torch) **veya**
  yönetilen OCR kararı.
- **Paketleme:** OCR motoru (EasyOCR/RapidOCR) **bildirilmiş bağımlılık** olmalı (ör. ayrı
  `ocr` grubu); ad-hoc `uv pip install` bir sonraki `uv sync`'te budanıyor. Motor seçimi
  (EasyOCR vs RapidOCR vs VLM) bu spike'ın beslediği **Faz 1 Sprint 1.2** kararı.

## Açık Riskler / Sonraki Doğrulama
- **Karmaşık tablolar** (birleşik/iç içe hücreler) gerçek fiyat cetvellerinde derinlemesine
  test edilecek; ilk cetvellerde satır/sütun çıkarımı çalışıyor → Faz 1.
- **Taranmış yolda birebir-citation kalitesi:** gürültülü taramalarda VLM fallback + OCR
  motor seçimi + Türkçe dil ayarı (`DoclingParser`'a `ocr_lang` parametresi) → Faz 1 Sprint 1.2.
- **Performans/maliyet:** OCR sayfa-başı süre ölçüldü (CPU ~20 sn); GPU/yönetilen ile
  ölçekleme ve yüzlerce sayfalık belgede bellek profili → Faz 1.
- **Windows/OneDrive notu:** proje OneDrive altında olduğundan `.venv` senkron/budama
  kırılganlığı yaşandı (parsing grubu + easyocr kayboldu, `uv sync --group parsing` ile geri
  kuruldu). Üretim worker'ı Linux; dev için `.venv`'i OneDrive dışına almak önerilir.
- **Windows notu:** HuggingFace model önbelleği Developer Mode olmadan sembolik link
  kuramaz (zararsız disk-verimliliği uyarısı). Üretim worker'ı Linux olduğundan etkisiz.

## Sonuçlar
**Olumlu:** OSS/ücretsiz birincil yol (maliyet-hassas); güçlü yapı + garanti bbox;
sözleşme soyutlaması uygulama değişimini ucuzlatır; api docling'e bağlı değil.
**Ödünler:** Docling ağır bağımlılıktır (kurulum boyutu, ilk çağrıda model indirimi);
worker imajı büyür; hibrit yönlendirme ek karmaşıklık getirir.

## Alternatifler
- **Yalnızca yönetilen (LlamaParse / Azure Document Intelligence):** Kolay entegrasyon ama
  sayfa-başı ücret + veri gizliliği (zero-retention, ADR-0007) endişesi. Maliyet-hassas
  MVP'de birincil değil; zor girdilerde **fallback** opsiyon olarak açık tutulur.
- **Salt OCR (Tesseract):** Yapı/tablo/okuma sırası zayıf; bbox var ama semantik yok.
- **Salt `pypdf`/`pdfplumber`:** Dijitalde hızlı; tablo/yapı ve taranmışta yetersiz.
  Yalnızca dijital/taranmış **yönlendirme tespiti** için yardımcı olarak kullanılır.

## İlgili
Geliştirme Planı §6.2, §12.6, A.4/5; Sprint 0.2 (#15) ve Faz 1 Sprint 1.2; ADR-0006
(zorunlu grounding). Kod: `packages/core/src/tenderiq_core/parsing/`,
`scripts/parsing_spike.py`.
