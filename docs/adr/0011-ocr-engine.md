# ADR-0011: OCR Motoru (EasyOCR) ve OCR Kapasite Yolu (CPU-önce, GPU/yönetilen-sonra)

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-16 (Sprint 1.2)
- **Karar veren:** Berkay (Scryne)

## Bağlam
Gerçek doküman spike'ı (ADR-0004, 2026-07-04) korpusun **~%54'ünün taranmış** olduğunu
gösterdi: OCR bir fallback değil, **çoğunluk yoldur**. Sprint 1.2 hibrit hattı
(sayfa-bazlı yönlendirme → Docling `do_ocr=True`) için iki karar gerekiyor:

1. **Motor seçimi:** OCR motoru bildirilmiş, kilitlenmiş bir bağımlılık olmalı
   (ad-hoc `uv pip install` bir sonraki `uv sync`'te budanıyor — spike'ta yaşandı).
2. **Kapasite/dağıtım:** dev ortamında CPU OCR **~20–22 sn/sayfa** ölçüldü; ölçekte
   bu süre sürdürülemez. GPU mu, yönetilen OCR mi?

## Karar 1 — Motor: EasyOCR (`tr,en`)
- **EasyOCR** Docling'in birincil OCR motoru olarak kullanılır; dil listesi
  `DoclingParser(ocr_lang=...)` parametresiyle verilir ve `PARSING_OCR_LANGUAGES`
  ayarından gelir (varsayılan `tr,en`).
- Paketleme: `packages/core`'un `ocr` extra'sı (`easyocr>=1.7.0`); kök `ocr`
  dependency-group'u bunu işaret eder. Worker imajı `--group parsing --group ocr`
  ile kurulur; **API imajı bu yığını taşımaz**.

**Gerekçe:** EasyOCR, spike'ta **gerçek TR şartnameleriyle doğrulanmış tek motor**:
temiz taramada neredeyse kusursuz Türkçe (Ğ/İ/Ü/Ş doğru), %100 bbox, Docling'le yerli
entegrasyon (`EasyOcrOptions(lang=[...])`). Torch zaten Docling'le imajda olduğundan
marjinal maliyeti düşüktür ve GPU'ya geçişte **aynı motor hızlanır** (torch CUDA).

**Alternatifler:**
- **RapidOCR (onnxruntime):** daha hafif/hızlı CPU profili; ama Türkçe (diakritik)
  kalitesi doğrulanmadı — PaddleOCR latin modellerinin TR performansı belirsiz.
  Doğrulanmamış motorla çoğunluk-yolu riske atmak yerine reddedildi; CPU maliyeti
  sorun olursa TR golden-set ile kıyaslanmak üzere aday kalır.
- **Tesseract:** kurulum sistem bağımlılığı; spike öncesi bilinen zayıf yapı/kalite.
- **Salt VLM:** sayfa başı LLM maliyeti çoğunluk yol için ekonomik değil (ADR-0004:
  VLM yalnızca gürültülü taramada fallback).

## Karar 2 — Kapasite yolu: CPU-önce; GA öncesi GPU worker, yönetilen OCR fallback
Aşamalı yol (maliyet-hassas, OSS-önce ilkesiyle uyumlu):

1. **Şimdi (Faz 1–2, dev + kapalı beta):** CPU OCR **kabul edilir**. Hat asenkron
   (Celery) ve kullanıcı beklentisi "dakikalar" olduğundan 20 sn/sayfa, düşük
   hacimde (günde onlarca belge) kuyruğu tıkamaz. Ek donanım/servis maliyeti: 0.
2. **GA öncesi (Faz 4 kapısı):** birincil plan **GPU worker** — worker imajının
   CUDA-torch varyantı + GPU'lu tek node (EasyOCR GPU'da ~10-20x hızlanır). Motor ve
   kod değişmez; yalnızca imaj/altyapı değişir.
3. **Fallback opsiyonu:** yönetilen OCR/parse (Azure Document Intelligence vb.)
   yalnızca (a) GPU işletim yükü tek kişilik ekibe ağır gelirse ya da (b) gürültülü
   taramalarda kalite yetmezse devreye alınır — ikincisi zaten Faz 2 **VLM fallback**
   kancasıyla (`HybridDocumentParser(vlm_parser=...)`) aynı yuvaya oturur.
   Zero-retention/DPA şartı aranır (ADR-0007 ilkesi).

**Tetik metriği (karar ne zaman yeniden açılır):** kuyruk gecikmesi p95 > 15 dk
**veya** günlük taranmış sayfa > ~500 olduğunda 2. adım uygulanır.

## Sonuçlar
**Olumlu:** doğrulanmış TR kalitesi; bağımlılık kilitli ve tekrarlanabilir; GPU'ya
kod değişikliksiz geçiş; API imajı hafif kalır.
**Ödünler:** worker imajı büyük (torch + easyocr modelleri); CPU döneminde büyük
taranmış belgeler dakikalar sürer; EasyOCR ilk çalıştırmada model indirir
(imaja gömme/ön-ısıtma Faz 4 optimizasyonu).

## İlgili
ADR-0004 (hibrit parsing — spike bulguları), Geliştirme Planı Sprint 1.2, §6.2.
Kod: `packages/core/src/tenderiq_core/parsing/hybrid.py`, `docling_parser.py`
(`ocr_lang`), `infra/docker/worker.Dockerfile` (parsing+ocr grupları).
