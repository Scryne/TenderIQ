# LLM maliyet tavanı — ölçüm, fiyat doğrulaması ve kalibrasyon

> Bu belge **ölçüme dayalı**dır. Her sayı tarih + "nasıl ölçüldü" taşır.
> Tavanın kendisi `packages/core/src/tenderiq_core/services/llm_budget.py`,
> fiyat tablosu `config/llm-pricing.json`.

## 1. Fiyat doğrulaması (Tur 15, 2026-07-31)

| Model | Girdi $/Mtok | Çıktı $/Mtok | Durum | Kaynak |
|---|---|---|---|---|
| `claude-opus-4-8` | 5.00 | 25.00 | ✅ doğrulandı | [Anthropic fiyat sayfası](https://platform.claude.com/docs/en/about-claude/pricing.md) |
| `claude-opus-5` | 5.00 | 25.00 | ✅ doğrulandı | aynı |
| `claude-sonnet-5` | 3.00 | 15.00 | ✅ doğrulandı (standart) | aynı |
| `claude-haiku-4-5` | 1.00 | 5.00 | ✅ doğrulandı | aynı |
| `qwen2.5:7b-instruct-q5_K_M` | 0.00 | 0.00 | ✅ tanımı gereği | yerel Ollama; token başına sağlayıcı ücreti yok |
| `qwen/qwen3.5-122b-a10b` | 0.00 | 0.00 | ❌ **DOĞRULANAMADI** | aşağıya bakın |

**Doğrulama kuralı.** `verified: true` yapan satır `source` (sağlayıcının KENDİ
fiyat sayfası) ve `verified_at` alanlarını doldurmak zorundadır. Kod bunu
zorlar: kaynaksız bir `verified: true` **doğrulanmamış sayılır**
(`llm/pricing.py`), yani bayrağı elle çevirmek tavanı denetlenemez bir sayının
üstüne oturtmaya yetmez.

**Sonuç: yayın birincil modelinin fiyatı artık doğrulanmıştır** — Tur 14'ten
devreden "tavan doğrulanmamış sayıların üstünde duruyor" GA engeli, üretim
yolunda kullanılan model için **kalktı**.

### `qwen/qwen3.5-122b-a10b` neden doğrulanamadı

NVIDIA, `build.nvidia.com` barındırılan katalogu için token başına **yayımlanmış
bir fiyat sunmuyor**; erişim denemeleri (2026-07-31):

- `build.nvidia.com/pricing` → bağlantı düştü (ECONNRESET)
- `www.nvidia.com/en-us/ai/nim-pricing/` → HTTP 404
- `build.nvidia.com` → zaman aşımı

Üçüncü taraf fiyat toplayıcıları $0.04–$1.20/Mtok aralığı bildiriyor, ancak
bunlar **sağlayıcı kaynağı değildir** ve tabloya yazılmadı — doğrulanmamış bir
sayıyı doğrulanmış gibi göstermek, kapatılmaya çalışılan borcun ta kendisidir.

Tablodaki `0.0` değeri **"ücretsiz olduğu doğrulandı" anlamına gelmez**;
`verified: false` olduğu için kayıtlar `pricing_status="unverified"` ile
işaretlenir ve tutar bir TAHMİN sayılır.

**Risk sınırlı**: bu model **dev katmanıdır**; üretim birincil modeli
`LLM_PRIMARY_MODEL=claude-opus-4-8`. Üretim yoluna alınacaksa fiyat **önce**
doğrulanmalıdır.

**Devredilen iş:** NVIDIA hesabının faturalandırma sayfasından (hesap
kullanıcıda) gerçek birim fiyatın okunması.

## 2. Bir analizin gerçek maliyeti (Tur 15 ölçümü)

**Nasıl ölçüldü.** `spike-docs/` altındaki gerçek şartnameler ayrıştırıldı,
üretimdeki gerçek kod yollarıyla (`indexing.chunking.chunk_elements`,
`agents.prompts.*`, `Settings.effective_agent_context_limit()`) ajan istemleri
birebir kuruldu ve karakter sayıldı. Bir analiz **5 LLM çağrısıdır**: dört
çıkarım ajanı (requirements/deliverables/risks/timeline) + compliance.

**Tokenizer uyarısı.** Karakter→token dönüşümü bir **tahmindir**: makinede
Anthropic kimlik bilgisi olmadığı için `count_tokens` ile birebir sayım
yapılamadı. Türkçe sondan eklemeli ve Claude 4.7+ tokenizer'ı aynı metin için
~%30 fazla token üretiyor (fiyat sayfası notu), bu yüzden **muhafazakâr**
2,5 karakter/token kullanıldı. Bulgu sayısı (`sayfa × 1,4`) da bir varsayımdır.

| Doküman | Sayfa | Maliyet (kur 42) |
|---|---|---|
| `ornek_sartname.pdf` | 2 | ~5,1 TL |
| `yaklasik-maliyet-teklif-istegipdf.pdf` | 4 | ~5,8 TL |
| `sozlesme-tasarisi-2-6428pdf.pdf` | 12 | ~10,3 TL |
| `idari-sartname-6428pdf.pdf` | 15 | ~13,2 TL |
| `teknik-sartname-1pdf.pdf` | 29 | ~24,7 TL |

Kur duyarlılığı (29 sayfalık şartname): kur 35 → 15,6 TL · kur 42 → 18,7 TL ·
kur 50 → 22,2 TL (orta tokenizer oranıyla 13–18,5 TL).

**En kötü hâl** (12 chunk bağlam dolu + `LLM_MAX_OUTPUT_TOKENS=16000` beş
çağrıda da dolu): **$2,24 ≈ 94 TL** (kur 42).

### Neyin ölçeklendiği

Ajan bağlamı `RETRIEVAL_AGENT_CONTEXT_LIMIT` (12 chunk) ile **tavanlıdır** —
doküman büyüdükçe **büyümez**. Sayfa sayısıyla ölçeklenen şey **bulgu
sayısıdır**: çıktı token'ları ve compliance isteminin gereksinim listesi.
Rezervasyon formülü bu yapıyı izler.

## 3. Rezervasyon: neden sabit tutar yetmedi

Tur 14'te rezervasyon sabit **5,0 TL**'ydi. Ölçüm gösterdi ki bu, tipik bir
şartnamenin gerçek maliyetinin **2–5 katı altında** (en kötü hâlde ~19 katı
altında). Aşım `eşzamanlılık × tahmin` ile sınırlı olduğundan, tahmin gerçeğin
altında kalınca **bu sınır anlamını yitirir**: tavan koruyor *görünür*, korumaz.

Yeni formül (`services/llm_budget.estimate_job_micros`):

```
tahmin = min(TABAN + sayfa × SAYFA_BASINA, TAVAN)
       = min(5,0 TL + sayfa × 0,6 TL, 60 TL)
```

| Sayfa | Rezervasyon | Ölçülen maliyet |
|---|---|---|
| 2 | 6,2 TL | ~5,1 TL |
| 12 | 12,2 TL | ~10,3 TL |
| 29 | 22,4 TL | ~24,7 TL |
| 66 | 44,6 TL | ~46,1 TL |
| bilinmiyor | **60 TL** (tavan) | — |

`page_count` yoksa tahmin **tavana** çıkar: bilinmeyen boyutu ucuz saymak, tam
da korunmak istenen aşımı üretirdi (fail-closed).

## 4. Açık sorun: plan kotaları kendi bütçeleriyle tutarsız

**Bu bir ürün/fiyatlandırma kararıdır ve henüz verilmemiştir.**

| Plan | Doküman kotası | LLM bütçesi | Bütçenin fiilen finanse ettiği |
|---|---|---|---|
| Ücretsiz | 5 doküman / 150 sayfa | 25 TL | **~1 tipik analiz** |
| Pro | 100 doküman / 5000 sayfa | 500 TL | **~30 analiz** |

Yani her iki planda da **bütçe, doküman kotasından ~3–5 kat önce dolar**.
Kullanıcıya "ayda 5 doküman" denip 1 doküman sonrası ret görmesi, tavanın
davranışı doğru olsa bile bir **vaat uyuşmazlığıdır**.

Seçenekler (biri seçilmeli):

1. **Kotaları bütçeye indir** — ücretsiz: 1 doküman / ~30 sayfa; Pro: ~30
   doküman. Dürüst, gelir etkisi yok, pazarlama vaadi küçülür.
2. **Bütçeleri kotaya çıkar** — ücretsiz ~115 TL, Pro ~1560 TL. Ücretsiz
   kademede kayıt açık olduğu için bu **doğrudan zarar tavanını 4,6 katına**
   çıkarır; Pro'da 1560 TL maliyet 1500 TL gelirin ÜSTÜNDE (negatif marj).
3. **Karma** — kotayı bir miktar indir, bütçeyi bir miktar çıkar.

Ölçüm 1 numaralı seçeneği destekliyor; ancak karar fiyatlandırmadır ve
bu turda **verilmedi**. Tavanın davranışı her hâlükârda doğrudur: ret açıktır,
bildirim gider, `/usage` ekranı (J.6 madde 3) kalan bütçeyi gösterir.

## 5. Kur (`LLM_USD_TRY_RATE`) — statik, elle, izlenen

Kur **otomatik çekilmez**: dış servis bağımlılığı bilinçli olarak eklenmedi
(bir kur API'sinin kesintisi analizleri durdurabilirdi). Bedeli, kurun sessizce
bayatlamasıdır; bu bedel şöyle görünür kılındı:

- `LLM_USD_TRY_RATE_DATE` — kurun elle güncellendiği tarih.
- `LLM_USD_TRY_RATE_MAX_AGE_DAYS` — bayatlık eşiği (varsayılan **30 gün**;
  TL oynaklığında bir aydan eski kur tavanı belirgin şekilde yanıltır).
- Açılışta (API + worker) `log_pricing_posture()` üç hâli raporlar ve `ops`
  sayaçlarına yazar: `llm_pricing_fx_missing`, `llm_pricing_fx_stale`,
  `llm_pricing_unverified`.

**Kim güncelleyecek:** operatör, **aylık faturalama dönemi başlamadan önce**.
`LLM_USD_TRY_RATE` boş bırakılırsa her kayıt `no_fx_rate` ile 0 TL yazılır,
harcama toplamı sıfır kalır ve **tavan hiç dolmaz** — açılışta `error`
seviyesinde uyarı üretilir (`llm_kuru_tanimsiz_tavan_fiilen_yok`).

## 6. Ölçümü yeniden üretmek

Ölçüm betiği bu turda geçici çalışma alanında koştu (repoya girmedi; girdisi
`spike-docs/` altındaki gerçek şartnamelerdir). Yeniden üretmek için: gerçek
kod yollarıyla (`chunk_elements` + `AGENT_INSTRUCTIONS` + `build_context_block`)
5 çağrılık istem kurulur, karakter sayılır, 2,5 karakter/token ile token'a
çevrilir ve doğrulanmış fiyatlarla çarpılır. Anthropic kimlik bilgisi olan bir
ortamda `client.messages.count_tokens` ile **birebir** sayım yapılmalı ve bu
belgedeki tahminler onunla değiştirilmelidir.
