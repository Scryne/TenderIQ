# ADR-0004: Hibrit Doküman Ayrıştırma (Docling + VLM/OCR fallback)

- **Durum:** Önerilen (dijital yol spike ile doğrulandı; taranmış/gerçek-doküman doğrulaması Faz 1'e taşındı)
- **Tarih:** 2026-07-03
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

## Açık Riskler / Sonraki Doğrulama
- **Gerçek TR şartnameleri henüz koşulmadı.** 2–3 gerçek doküman (1 dijital, 1 taranmış,
  1 tablo-yoğun) `spike-docs/`'a konup çalıştırılacak — Faz 0 çıkış kapısının kalan maddesi.
- **Taranmış / VLM yolu** gerçek taranmış dokümanla doğrulanmadı (OCR kalitesi, bbox
  isabeti) → Faz 1 Sprint 1.2.
- **Karmaşık tablolar** (birleşik/iç içe hücreler) gerçek fiyat cetvellerinde test edilecek.
- **Performans/maliyet:** yüzlerce sayfalık dokümanda Docling süresi/belleği ölçülmedi
  (§12.6 ölçek riski) → Faz 1.
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
