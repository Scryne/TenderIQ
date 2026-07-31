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

## 4. Kota kalibrasyonu — kotalar bütçeden TÜRETİLİR (Tur 16)

**Karar verildi: kotalar bütçeye indirildi.** Gerekçe: kota kullanıcıya verilen
**sözdür**, bütçe **gerçek kısıttır**; tutulamayan söz iptal ve iade olarak geri
döner. "Bütçeleri kotaya çıkar" seçeneği kapatıldı çünkü ücretsiz kademede
doğrudan zarar tavanını 4,6 katına çıkarıyor, Pro'da ise 1560 TL maliyet
1500 TL gelirin üstünde kalıyordu (negatif marj).

### Ölçülen ortalama

Tur 15 ölçümündeki, **metni çıkarılabilen 11 gerçek doküman** (şartname +
sözleşme + teklif formları — gerçekçi bir ihale dosya seti) üzerinden, kur 42
ve muhafazakâr tokenizer oranıyla:

```
ortalama maliyet : 8,28 TL / doküman   (medyan 5,49)
ortalama uzunluk : 6,5 sayfa           (medyan 2,0)
```

Ortalama medyandan yüksek: set birkaç uzun şartname (29, 15, 12 sayfa) ile çok
sayıda 1–2 sayfalık form içeriyor. **Ortalama kullanıldı**, çünkü kota her
dokümanı sayar ve kullanıcı karışık bir set yükler.

### Türetme

`billing/plans.py` kotayı artık **hesaplar**:

```
doküman kotası = ⌊bütçe ÷ ORTALAMA_MALİYET⌋
sayfa kotası   = max(doküman × ORTALAMA_SAYFA, TİPİK_ŞARTNAME_SAYFASI)
```

| Plan | Bütçe | Doküman | Sayfa | Kotanın tam maliyeti |
|---|---|---|---|---|
| Ücretsiz | 25 TL | **3** | **35** | 24,9 TL ✅ |
| Pro | 500 TL | **60** | **390** | 498,0 TL ✅ |
| Kurumsal | sınırsız | sınırsız | sınırsız | — |

Aşağı yuvarlama bilinçli: yukarı yuvarlamak kotayı yeniden bütçenin üstüne
çıkarırdı.

**Sayfa kotasının tabanı neden var.** Ortalamadan türetilen sayfa kotası
ücretsiz kademede ~20 sayfa veriyordu ve 29 sayfalık tipik bir şartnameyi
reddediyordu — bütçesinin (24,7 TL < 25 TL) finanse ettiği tek işi sayfa limiti
bloke ediyordu. Bu yüzden sayfa kotası `TYPICAL_LARGE_DOCUMENT_PAGES` (35)
altına inemez.

**Kota bir TAVAN, bütçe BAĞLAYICI kısıttır.** Doğrusal bir (doküman, sayfa)
kotası, sabit + değişken bileşenli bir maliyeti tam olarak temsil edemez:
ücretsiz kullanıcı ya ~3 küçük doküman ya ~1 orta şartname işleyebilir, ikisini
birden değil. Bu ödünü kota sayıları değil **bütçe** çözer; arayüz (`/usage`)
ikisini birlikte gösterir.

### Bu GEÇİCİ bir kalibrasyondur

Sayılar `billing/plans.py`de sabit yazılı DEĞİL, `MEASURED_AVERAGE_ANALYSIS_
COST_TRY` sabitinden türetilir. Maliyet düştüğünde (§6'daki keşif: ucuz modele
inme, istem önbellekleme) **yalnız o sabit düşürülür** ve üç planın kotası da
birlikte yükselir. Kotayı plan tablosuna elle yazmak, o günü üç ayrı yerde
güncellemek demekti.

İki test bu hizalamayı korur (`test_billing_quota.py`): kotanın tamamı ortalama
maliyette bütçeyi aşamaz, ve sayfa kotası tek bir tipik şartnamenin altına
inemez. Üçüncü bir test (`test_kota_metni_denetimi.py`) landing ve kayıt
ekranındaki sayıların plan kaydıyla aynı kalmasını zorlar — kota hukuki
metinlerin dayandığı bir vaattir, eski sayı tutulmayan bir taahhüttür.

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
