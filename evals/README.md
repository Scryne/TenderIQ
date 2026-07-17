# evals/ — Golden-set & AI Kalite Değerlendirmesi (§6.10)

AI çıkarım kalitesini **ölçülebilir** kılan katman: el ile etiketlenmiş beklenen
çıktılar (golden-set) + deterministik değerlendirme scripti. Faz 2'de extraction
ajanları geldiğinde CI'da **bloke edici regresyon kapısı** olacak (Sprint 2.4);
o zamana dek iskelet, sample fixture ile format/script doğrulaması yapar.

## Dizin yapısı

```
evals/
├─ run_eval.py            # değerlendirme scripti (format sözleşmesi de burada)
├─ golden/
│  ├─ sample/             # SENTETİK örnek case — commit edilir, CI fixture'ı
│  └─ private/            # GERÇEK şartname etiketleri — KVKK, commit EDİLMEZ
├─ predictions/
│  └─ sample/             # örnek ajan çıktısı — commit edilir, CI fixture'ı
└─ tests/                 # eşleme + metrik birim testleri
```

## Format (schema_version=1)

**Golden case** (`golden/**/<case_id>.json`): bir dokümanın beklenen çıktıları.
Şema `run_eval.py` içindeki pydantic modelleridir (`GoldenCase`): `case_id`,
`document` (filename/kind/source/page_count) ve `labels`:

- `requirements`: `{id, text, type: technical|administrative|financial, mandatory, page}`
- `deliverables`: `{id, name, mandatory, page}` — zorunlu belge/sertifika/teminat
- `risks`: `{id, description, severity: low|medium|high, page}`

`page` izlenebilirlik notudur; eşlemede kullanılmaz. Etiket metnini dokümandaki
ifadeye yakın yazın — eşleme metin benzerliğiyle yapılır.

**Prediction** (`predictions/**/<case_id>.json`): ajan çıktısının metin temsili
(`PredictionSet`): `case_id` + kategori başına metin listesi. Faz 2'de
orkestratör bu dosyaları üretecek.

## Metrikler

- Kategori başına **precision / recall / F1** (case'ler arası mikro-ortalama).
- **Kaçırılan zorunlu belge oranı** (kritik metrik, §12.6): eşleşmeyen zorunlu
  `deliverable` / toplam zorunlu `deliverable`.
- Eşleme: normalize metin üzerinde bire-bir açgözlü eşleme
  (SequenceMatcher ∨ token Jaccard ≥ `--threshold`, varsayılan 0.6). LLM yok —
  CI'da deterministik.

## Çalıştırma

```bash
# İskelet doğrulaması (CI'daki adım):
uv run python evals/run_eval.py --golden evals/golden/sample --predictions evals/predictions/sample

# Gerçek etiketlerle (private/, ajanlar Faz 2'de prediction üretecek):
uv run python evals/run_eval.py --golden evals/golden/private --predictions <ajan-çıktı-dizini> --report spike-out/eval.json

# Faz 2 CI kapısı (Sprint 2.4'te aktifleşir):
uv run python evals/run_eval.py ... --gate --min-recall 0.8 --max-missed-mandatory 0.05
```

## Etiketleme kuralları (golden-set v1)

1. Kaynak PDF `spike-docs/`ta durur (gitignore'lu); JSON etiketi de gerçek
   doküman içeriği taşıdığından `golden/private/` altında kalır (gitignore'lu).
2. Her zorunlu belge ("...sunulması zorunludur", "teklifle birlikte verilecektir")
   `deliverables`'a `mandatory: true` ile girer — kritik metrik buradan hesaplanır.
3. Cezai şart, ağır kısıt, olağandışı yükümlülükler `risks`'e girer.
4. Etiket, dokümandaki ifadeye sadık kalır (özet değil alıntıya yakın) ve `page`
   ile kaynağını gösterir.
