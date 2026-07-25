# DESIGN.md — Frontend & UI/UX Çalışma Kuralları

> **Bu dosya bir referans değil, bir sözleşmedir.**
> Bu depoda UI üreten her ajan (Claude Code dahil) bu dosyayı okumak ve
> uygulamak zorundadır. Buradaki kurallarla çelişen bir çıktı = hatalı çıktı.
>
> Sürüm: 1.1 · Sahip: @Scryne
> Bölüm 8'deki ölçüler 30 profesyonel dashboard ekranından çıkarılmıştır —
> tahmin değildir, tartışmaya açık değildir.

---

## İÇİNDEKİLER

| # | Bölüm | Ne zaman okunur |
|---|-------|-----------------|
| 0 | [Nasıl kullanılır](#0-nasıl-kullanılır) | İlk kurulumda |
| 1 | [Altın kural: neden tasarımlar kötü çıkıyor](#1-altın-kural) | Bir kez, dikkatle |
| 2 | [MCP kurulumu](#2-mcp-kurulumu) | Proje başlangıcı |
| 3 | [Skill kurulumu ve önceliklendirme](#3-skill-kurulumu-ve-önceliklendirme) | Proje başlangıcı |
| 4 | [PROJE BRIEF — doldurulacak](#4-proje-brief--doldurulacak) | **Her yeni projede zorunlu** |
| 5 | [Tasarım token sistemi](#5-tasarım-token-sistemi) | Kod yazmadan önce |
| 6 | [Tipografi](#6-tipografi) | Kod yazmadan önce |
| 7 | [Layout & grid](#7-layout--grid) | Sayfa iskeleti kurarken |
| 8 | [Bileşen spesifikasyonları](#8-bileşen-spesifikasyonları) | Bileşen yazarken |
| 9 | [Sayfa şablonları](#9-sayfa-şablonları) | Yeni sayfa açarken |
| 10 | [Durum tasarımı: boş / yükleniyor / hata](#10-durum-tasarımı) | Her sayfada |
| 11 | [Hareket & animasyon](#11-hareket--animasyon) | Etkileşim eklerken |
| 12 | [Erişilebilirlik](#12-erişilebilirlik) | Her PR'da |
| 13 | [ANTI-SLOP: yasak listesi](#13-anti-slop-yasak-listesi) | **Her çıktıdan önce** |
| 14 | [Görsel doğrulama döngüsü](#14-görsel-doğrulama-döngüsü) | **Her UI görevinin sonunda zorunlu** |
| 15 | [Definition of Done](#15-definition-of-done) | Görev kapatırken |
| 16 | [Prompt kütüphanesi](#16-prompt-kütüphanesi) | Claude Code'a iş verirken |
| 17 | [Referans kaynakları](#17-referans-kaynakları) | İlham ararken |
| A | [Ek A: Tailwind'siz / Ant Design projeleri](#ek-a-tailwindsiz--ant-design-projeleri) | FabrikaOS tipi projeler |
| B | [Ek B: Türkçe arayüz kuralları](#ek-b-türkçe-arayüz-kuralları) | Metin yazarken |

---

## 0. Nasıl kullanılır

### Dosya yerleşimi

```
proje-kökü/
├── CLAUDE.md              ← 3 satırlık pointer (aşağıda)
├── DESIGN.md              ← bu dosya
├── .mcp.json              ← MCP tanımları (Bölüm 2)
├── .claude/
│   ├── skills/            ← kurulan skill'ler (Bölüm 3)
│   └── commands/
│       ├── ui-audit.md    ← /ui-audit slash komutu
│       └── ui-build.md    ← /ui-build slash komutu
└── design/
    ├── refs/              ← referans ekran görüntüleri (ZORUNLU)
    ├── shots/             ← ajanın kendi aldığı screenshot'lar
    └── decisions.md       ← tasarım kararları günlüğü
```

### CLAUDE.md'ye eklenecek satırlar

```md
## Frontend kuralları
UI/frontend içeren HER görevde, kod yazmadan önce `DESIGN.md` dosyasını
baştan sona oku. DESIGN.md Bölüm 13 (Anti-slop) ve Bölüm 14 (Görsel
doğrulama) atlanamaz. Görev, Bölüm 15'teki Definition of Done sağlanmadan
"bitti" sayılmaz.
```

### Akış

```
1. BRIEF doldur (Bölüm 4)        ─┐
2. Token'ları sabitle (Bölüm 5-6) ├─ bir kez, proje başında
3. refs/ klasörünü doldur         ─┘
                    ↓
4. /ui-build <sayfa adı>          ─┐
5. Ajan plan sunar → onayla       ├─ her sayfa için
6. Ajan kodlar                    │
7. Ajan screenshot alır + kritik  │
8. Ajan düzeltir → tekrar 7       ─┘
                    ↓
9. /ui-audit → DoD kontrolü
```

---

## 1. ALTIN KURAL

> **Beğendiğin tasarımlar "daha iyi bir model" ile değil, "daha iyi bir
> girdi ve geri bildirim döngüsü" ile üretiliyor.**

40 tane skill kurmak sorunu çözmez — aksine context'i şişirir ve ajanın
dikkatini dağıtır. Gerçekte fark yaratan 5 kaldıraç şunlardır:

| # | Kaldıraç | Neden kritik |
|---|----------|--------------|
| **1** | **Referans görseller** | Ajan "güzel"i tarif edemez, **taklit** edebilir. `design/refs/` boşsa çıktı jenerik olur. Bu tek başına kalitenin ~%40'ı. |
| **2** | **Sabit token sistemi** | Her sayfada yeniden renk/spacing seçen ajan tutarsız üretir. Token'lar bir kez sabitlenir, sonra sadece kullanılır. ~%25. |
| **3** | **Görsel geri bildirim döngüsü** | Ajan kendi çıktısını **göremezse** hizasız, taşan, kırık layout üretir ve fark etmez. Chrome DevTools MCP + screenshot şart. ~%20. |
| **4** | **Anti-slop yasak listesi** | Modelin default'a kayma eğilimini kesen açık negatif kurallar. ~%10. |
| **5** | **Bileşen kaynağı (shadcn/21st MCP)** | Hallüsine prop yerine gerçek, çalışan bileşen kodu. ~%5. |

**Skill'ler bu 5 kaldıracın yerine geçmez, üzerine biner.** Önce 1–5'i
kur, sonra 6–8 skill ekle. Fazlası zarar.

### Anlaşılması gereken ikinci gerçek

Beğendiğin ekranlar (Linear, Stripe, Vercel, 21st.dev'deki işler) tek bir
şeyi çok iyi yapıyor: **kısıtlama.** 3 renk, 2 font, 4 spacing değeri, 2
gölge seviyesi. Kötü AI çıktısı ise 9 renk, 6 font boyutu, rastgele
padding ve her karta gradient koyar. Kalite = az sayıda karar, tutarlı
uygulanmış.

---

## 2. MCP KURULUMU

### 2.1 Zorunlu üçlü

Bu üçü olmadan bu dosyanın yarısı çalışmaz.

**`.mcp.json`** (proje kökü, git'e commit edilir):

```json
{
  "mcpServers": {
    "shadcn": {
      "command": "npx",
      "args": ["shadcn@latest", "mcp"]
    },
    "chrome-devtools": {
      "command": "npx",
      "args": ["chrome-devtools-mcp@latest", "--autoConnect"]
    },
    "magic": {
      "command": "npx",
      "args": ["-y", "@21st-dev/magic@latest"],
      "env": { "API_KEY": "${MAGIC_21ST_API_KEY}" }
    }
  }
}
```

> API anahtarını dosyaya **yazma**. `.env.claude` içine koy, shell'de
> `export MAGIC_21ST_API_KEY=...` ile ver ve `.env.claude`'u
> `.gitignore`'a ekle.

**CLI ile alternatif kurulum:**

```bash
# shadcn (resmî yol)
npx shadcn@latest mcp init --client claude

# Chrome DevTools — görsel geri bildirim döngüsünün motoru
claude mcp add chrome-devtools -- npx chrome-devtools-mcp@latest --autoConnect

# 21st.dev Magic — önce https://21st.dev/magic/console adresinden key al
npx @21st-dev/cli@latest install claude --api-key <KEY>
```

Kurulumdan sonra Claude Code'da `/mcp` yaz, üçünün de **Connected**
göründüğünü doğrula.

### 2.2 Her MCP ne için kullanılır (ve ne için kullanılmaz)

| MCP | KULLAN | KULLANMA |
|-----|--------|----------|
| **shadcn** | Bileşen/blok kaynak kodunu **gerçekten** okumak, registry'den kurmak, prop imzalarını doğrulamak | Tasarım kararı vermek için. shadcn default görünümü = slop'un tanımı. Sadece **yapı** al, stili sen ver. |
| **chrome-devtools** | Screenshot, responsive test (375/768/1440), console hatası, computed style incelemesi, Lighthouse | Sayfa içeriği okumak için (yavaş); `take_snapshot` daha hızlı |
| **magic (21st.dev)** | Tek bir karmaşık bileşenin ilk taslağı, marka logosu SVG'si (`logo_search`), referans arama | Tüm sayfayı ürettirmek için. Çıktısı **her zaman** Bölüm 5 token'larına göre yeniden yazılır. |

### 2.3 Opsiyonel dördüncü

Figma mockup'ın varsa: **Figma Dev Mode MCP**. Yoksa kurma — boşuna
context yer.

### 2.4 Kritik uyarı

21st.dev Magic gibi harici kod üreten MCP'lerin çıktısında **prompt
injection riski** var. Ürettiği kodu commit'lemeden önce oku. Bunu
CLAUDE.md'ye de yaz.

---

## 3. SKILL KURULUMU VE ÖNCELİKLENDİRME

### 3.1 Çekirdek set (kur — 7 adet)

Bunlar birbirini tekrar etmez, birlikte tam kapsam verir:

| Skill | Rolü | Ne zaman tetiklenir |
|-------|------|---------------------|
| `frontend-design` | **Omurga.** Görsel yön, tipografi, "şablon kokusunu" kırma | Her yeni ekran/landing |
| `design-system` | Token üretimi ve tutarlılık denetimi | Proje başlangıcı, token değişimi |
| `enterprise-dashboard-design` | Yoğun veri, tablo, yerleşim | Dashboard/panel sayfaları |
| `dashboard-ux` | Bilgi hiyerarşisi, drill-down, eşik/alert mantığı | KPI ve izleme ekranları |
| `dataviz` | Grafik tipi seçimi, eksen, renk körlüğü, KPI kartı | Grafik içeren her ekran |
| `micro-interactions` | Hover/focus/loading/başarı geri bildirimleri | Cilalama fazı |
| `accessibility-wcag` | Kontrast, klavye, ARIA, focus tuzağı | Her PR öncesi denetim |

### 3.2 Duruma göre eklenenler (proje tipine göre 1–3 tane)

| Proje tipi | Ekle |
|------------|------|
| Landing / pazarlama sayfası | `design-taste-frontend`, `high-end-visual-design` |
| SaaS abonelik/plan/limit ekranları | `saas-design` |
| Yoğun animasyon | `framer-motion` + `design-motion-principles` |
| Mobil / iOS hissi | `apple-design` |
| Mevcut çirkin projeyi düzeltme | `redesign-existing-projects`, `refactoring-ui` |
| Marka kimliği (logo, banner) | `brand`, `brandkit` |
| Türkçe metin kalitesi | `ux-writing` |

### 3.3 KURMA (veya sonra kur)

Aynı işi yapan skill'ler birbirini boğar. Şunlar **çekirdek set ile
çakışıyor**, aynı anda kurma:

- `impeccable`, `ui-ux-pro-max`, `design-inspiration`, `emil-design-eng`,
  `gpt-taste`, `stitch-design-taste`, `design-taste-frontend-v1`,
  `ui-styling`, `color-system`, `typography`, `minimalist-ui`,
  `industrial-brutalist-ui`, `animation-vocabulary`, `magicui-patterns`,
  `aceternity-ui-patterns`, `reactbits-patterns`, `ux-laws`
- Bunların çoğu `frontend-design` + `design-system` + bu dosyanın
  Bölüm 5–13'ü ile zaten karşılanıyor.
- `magicui-patterns` / `aceternity-ui-patterns` / `reactbits-patterns`:
  **shadcn MCP + 21st MCP** bunların işini canlı kaynaktan yapıyor.

> **Kural: aynı anda 10'dan fazla design skill aktif olmasın.**
> Daha fazlası ölçülebilir şekilde kaliteyi düşürür (context dilüsyonu).

### 3.4 Kurulum

```bash
mkdir -p .claude/skills
# her skill kendi klasöründe SKILL.md olacak şekilde:
# .claude/skills/frontend-design/SKILL.md
```

Aktif skill'leri doğrula:

```
Claude Code içinde:  hangi skill'ler yüklü, listele
```

### 3.5 Skill'lerin tetiklenmesi

Skill'ler `description` alanındaki anahtar kelimelerle otomatik tetiklenir.
Tetiklenmediğini düşünüyorsan prompt'ta **açıkça çağır**:

```
frontend-design ve dataviz skill'lerini kullanarak ...
```

---

## 4. PROJE BRIEF — DOLDURULACAK

> **Bu bölüm boşken hiçbir UI kodu yazılmaz.**
> Boş bırakılırsa ajan varsayım üretir ve varsayımlar jenerik olur.

> **DOLDURULDU** · 2026-07-25 · kaynak: kod tabanı (`apps/web`, `packages/api-client`),
> `README.md`, `GELISTIRME_PLANI.md`. Varsayım işaretli alanlar `⌂` ile gösterilir.

```yaml
proje_adi:        TenderIQ

tek_cumle:        "Türkçe kamu ihalesi / RFP şartnamelerini kaynağına kadar izlenebilir
                   (citation-first) biçimde analiz eden, çok kiracılı KVKK-uyumlu SaaS."

kullanici:        "Birincil: teklif hazırlama sorumlusu / iş geliştirme müdürü — 300+
                   sayfalık şartnameyi okuyup teklif kararını veren kişi.
                   İkincil: teknik müdür (yalnız uygunluk sekmesine bakar),
                   organizasyon yöneticisi (üye, davet, kota, plan).
                   ⌂ Segment: kamu ihalesine giren KOBİ ölçekli entegratör/müteahhit."

kullanim_ortami:  "Ofis masaüstü, 1440–1920px, Chrome sekmesi. Teklif hazırlık haftasında
                   günde 2–4 saat kesintisiz açık; diğer günlerde birkaç dakikalık
                   kontrol ziyaretleri. Yan ekranda EKAP ve orijinal PDF açık olur —
                   ürün, o PDF'in yerini almaz, ona köprü kurar."

birincil_is:      "Bu şartnamede beni eleyecek ya da riske atacak madde hangisi, ve
                   kanıtı dokümanın tam olarak neresinde? — 5 saniyede."

duygu:            "kanıtlı · ölçülü · hukuki-ciddi"

karsit_duygu:     "sihirli-yapay-zekâ · pazarlamacı · gradient'li · oyuncaklı ·
                   'kara kutu' (gerekçesiz sonuç üreten)"

tema:             "ikisi — varsayılan light. Gerekçe: ana çalışma yüzeyi beyaz bir PDF
                   tuvali; kabuk koyu, tuval beyaz olduğunda kontrast sıçraması göz
                   yorar. Koyu tema tam desteklenir ama varsayılan değildir."

yogunluk:         "dengeli (kart padding 20px · satır 48px · taban metin 14px).
                   Tüm sayfalarda sabit — inceleme çalışma alanı dahil istisna yok."

dil:              "tr · i18n yok (JSX içinde doğrudan Türkçe metin). Ek B kuralları
                   bağlayıcı."

stack:            "Next.js 15 (App Router) + React 19 + TypeScript strict +
                   Tailwind v4 (@theme inline) + shadcn/ui (tekil `radix-ui` paketi) +
                   TanStack Query v5 + sonner (toast) + react-pdf/pdfjs-dist +
                   next-themes"

grafik_kutuphanesi: "YOK — kurulu değil ve eklenmeyecek. Bu üründe zaman serisi yok;
                     sayısal anlatım KPI kartı (§8.1) + sıralı dağılım listesi (§8.12)
                     + ilerleme çubuğu ile çözülür. Yeni bağımlılık = yeni karar."

ikon_seti:        "lucide-react 0.469 — tek set, 16/18px, strokeWidth 1.5 (nav/dekoratif)
                   ve 1.75 (eylem)."

kirmizi_cizgiler:
  - "Bulgu, kaynağından koparılarak gösterilemez. Doküman + sayfa + madde referansı
     bulgu satırının ayrılmaz parçasıdır; 'kaynağı gör' ayrı bir tıklama arkasına
     saklanamaz. Ürün vaadi budur."
  - "İnceleme ekranı iki bölmelidir (sol bulgu listesi ↔ sağ doküman tuvali) ve bulgu
     seçimi sağdaki sayfayı + vurguyu sürer. Tek bölmeye indirgenemez."
  - "Türkçe biçimlendirme Ek B'ye tabidir: ₺1.234,56 · %12,4 · 25.07.2026 · 24 saat.
     Intl.NumberFormat('tr-TR') / Intl.DateTimeFormat('tr-TR') dışında elle
     biçimlendirme yasak."
  - "shadcn CSS değişken sözleşmesi (--background/--card/--primary/--ring/…) korunur;
     DESIGN token'ları bunların ÜZERİNE eşlenir. Bileşende ham palet sınıfı
     (bg-blue-500, text-slate-600) ve çıplak hex yok."
  - "İnceleme kararları geri alınabilir olmalı: onay/red/düzeltme her zaman
     'İncelemeyi geri al' ile dönülebilir; kim/ne zaman geçmişi ekranda erişilebilir."
  - "KVKK: hiçbir ekrana gerçek şartname içeriği mock veri olarak gömülmez. Örnek veri
     gerçekçi ama uydurma kurum/firma adları kullanır."
  - "Erişim rolleri UI'da görünür olmalı: yönetici olmayan kullanıcıya devre dışı buton
     değil, nedenini söyleyen metin gösterilir (mevcut davranış korunur)."
```

### Ekran envanteri (redesign kapsamı)

| # | Rota | Rol | Birincil iş |
|---|------|-----|-------------|
| 1 | `/` | Pazarlama | "Bu ürün bulguyu kanıtlıyor mu?" |
| 2 | `/login` · `/forgot-password` · `/reset-password` | Auth | Sürtünmesiz giriş |
| 3 | `/verify-email` · `/accept-invitation` | Auth (tek amaçlı) | Tek eylemi tamamlat |
| 4 | `/tenders` | Liste | "Hangi ihalede sıra bende?" |
| 5 | `/tenders/[id]` | Detay + yükleme | "Analiz nerede kaldı?" |
| 6 | `/tenders/[id]/review` | **Çekirdek çalışma alanı** | `birincil_is` |
| 7 | `/capability` | Form | "Beyanım analizi besliyor mu?" |
| 8 | `/usage` | Hesap | "Kotam bitiyor mu?" |
| 9 | `/settings` | Hesap (3 bölüm) | Üye/davet/hesap yönetimi |
| — | `global-error` · 404 · 403 | Durum | §10.4 / §10.5 |

### Referans görselleri (ZORUNLU)

`design/refs/` klasörüne beğendiğin **5–10 ekran görüntüsü** koy ve her
biri için tek satır not yaz:

```
design/refs/README.md

- 01-linear-dash.png     → sidebar grup başlıkları + boşluk ritmi. RENGİNİ ALMA.
- 02-stripe-payments.png → KPI kartı anatomisi, delta yerleşimi.
- 03-mes-panel.png       → tablo yoğunluğu ve durum rozetleri.
- 04-findexa-dark.png    → koyu tema yüzey katmanları (bg/card/border).
```

> **En kritik nokta:** her referans için *neyi* aldığını yaz. "Bu güzel"
> yeterli değil. Ajan "renk paletini kopyala" mı, "boşluk ritmini al" mı
> anlamak zorunda. Aksi halde 3 referanstan Frankenstein çıkar.

---

## 5. TASARIM TOKEN SİSTEMİ

### 5.1 Kural

- **Hiçbir bileşende ham hex, ham px yok.** Sadece token.
- Token sayısı azdır. Yeni token eklemek bir **karardır**, refleks değil.
- Tailwind v4 kullanıyorsan `@theme` içinde; v3 ise `tailwind.config`;
  CSS-in-JS ise tek bir `tokens.css`.

### 5.2 Renk mimarisi (semantik, ham değil)

Ham renk isimlendirme (`blue-500`) bileşende **kullanılmaz**. Semantik
katman zorunlu:

```css
@theme {
  /* ── Yüzeyler (katman derinliği: 3 seviye, fazlası değil) ── */
  --color-bg:            #FAFAFA;  /* sayfa zemini */
  --color-surface:       #FFFFFF;  /* kart, panel */
  --color-surface-sunken:#F4F4F5;  /* tablo başlığı, input arkası */
  --color-overlay:       #FFFFFF;  /* modal, popover */

  /* ── Kenarlıklar (2 seviye) ── */
  --color-border:        #E7E7E9;  /* varsayılan */
  --color-border-strong: #D4D4D8;  /* vurgulu ayırıcı */

  /* ── Metin (4 seviye — 5. seviyeye ihtiyacın yok) ── */
  --color-fg:            #18181B;  /* başlık, ana metin */
  --color-fg-muted:      #52525B;  /* açıklama */
  --color-fg-subtle:     #A1A1AA;  /* etiket, placeholder */
  --color-fg-on-accent:  #FFFFFF;

  /* ── Marka / aksiyon (TEK aksan rengi) ── */
  --color-accent:        #____;    /* BRIEF'ten gelir */
  --color-accent-hover:  #____;
  --color-accent-subtle: #____;    /* %8-12 alpha zemin */

  /* ── Durum (4 renk, sabit anlam) ── */
  --color-success:       #16A34A;
  --color-warning:       #D97706;
  --color-danger:        #DC2626;
  --color-info:          #2563EB;
  /* her biri için -subtle (rozet zemini) varyantı */

  /* ── Veri görselleştirme (sıralı, renk körü güvenli) ── */
  --color-chart-1: #____;  --color-chart-2: #____;
  --color-chart-3: #____;  --color-chart-4: #____;
  --color-chart-5: #____;  --color-chart-6: #____;
}
```

**Koyu tema** aynı isimlerle, ayrı blokta tanımlanır:

```css
@media (prefers-color-scheme: dark), [data-theme="dark"] {
  --color-bg:             #0A0A0B;
  --color-surface:        #141416;
  --color-surface-sunken: #1B1B1E;
  --color-border:         #26262A;
  --color-border-strong:  #34343A;
  --color-fg:             #FAFAFA;
  --color-fg-muted:       #A1A1AA;
  --color-fg-subtle:      #71717A;
}
```

> **Koyu tema kuralları:**
> - Saf siyah (`#000`) **yasak** — göz yorar, gölge görünmez. `#0A0A0B` ile başla.
> - Koyu temada gölge değil, **yüzey açıklığı** derinlik verir.
> - Koyu temada aksan rengi light temadakinden **~%10 daha açık ve daha az doygun** olmalı.

### 5.3 Spacing (4px tabanlı, 7 değer)

```
--space-1:  4px    ikon-metin arası
--space-2:  8px    kart içi sıkı gruplar
--space-3: 12px    form alanı içi
--space-4: 16px    kart padding (yoğun panel)
--space-6: 24px    kart padding (standart), kartlar arası
--space-8: 32px    bölüm arası
--space-12:48px    sayfa üst boşluğu, büyük bölüm ayrımı
```

**Yasak:** 5px, 10px, 13px, 18px, 22px gibi ara değerler. Bir şey
"biraz kaymış" görünüyorsa çözüm ara değer değil, **yapıyı düzeltmek**.

### 5.4 Radius

```
--radius-sm:  6px   rozet, tag, küçük buton
--radius-md:  8px   input, buton, dropdown
--radius-lg: 12px   kart, panel        ← ana karakter buradan gelir
--radius-xl: 16px   modal, büyük konteyner
--radius-full: 9999px  avatar, pill
```

> Radius kimlik taşır. 4px = teknik/keskin. 12px = modern SaaS.
> 20px+ = tüketici/oyuncaklı. **Projede tek bir karakter seç, karıştırma.**

### 5.5 Gölge (2 seviye — daha fazlası amatörlük işareti)

```css
--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.04),
             0 1px 3px 0 rgb(0 0 0 / 0.06);
--shadow-md: 0 4px 12px -2px rgb(0 0 0 / 0.08),
             0 2px 6px -2px rgb(0 0 0 / 0.04);
--shadow-lg: 0 12px 32px -8px rgb(0 0 0 / 0.14);  /* SADECE modal/popover */
```

**Kural:** Dashboard kartları gölge yerine **1px border** kullanır.
Gölge yalnızca "yüzeyin üstünde yüzen" şeyler içindir (dropdown, modal,
toast, sürüklenen kart). Her karta gölge = ucuz görünüm.

---

## 6. TİPOGRAFİ

### 6.1 Türkçe kritik uyarısı

> **Font seçmeden önce `İ ı Ğ ğ Ş ş Ç ç Ö ö Ü ü` karakterlerini test et.**
> Popüler display font'ların çoğunda (özellikle variable/deneysel olanlar)
> Türkçe glif eksik veya bozuk. Eksikse tarayıcı fallback yapar ve
> arayüzde **iki farklı font karışır** — bu, tasarımı anında ucuzlatır.
> Google Fonts'ta "Latin Extended" alt kümesini işaretle.

### 6.2 Font eşleştirme

Üç rol, en fazla **iki aile**:

| Rol | Kullanım | Öneri |
|-----|----------|-------|
| **Display** | H1, hero, büyük KPI sayısı | Karakterli. Ölçülü kullanılır. |
| **Body/UI** | Her şey | Nötr, yüksek okunabilirlik |
| **Mono** | ID, kod, tablo sayıları, timestamp | Tabular figürlü |

**Güvenli ve jenerik olmayan kombinasyonlar** (hepsi Türkçe destekli):

| Yön | Display | Body | Mono |
|-----|---------|------|------|
| Modern SaaS / teknik | Geist | Geist | Geist Mono |
| Kurumsal, ciddi | Instrument Sans | Inter Tight | IBM Plex Mono |
| Sıcak, editoryal | Fraunces (yalnız H1) | Public Sans | JetBrains Mono |
| Endüstriyel / MES | Archivo | Archivo | Roboto Mono |
| Finans / veri yoğun | Söhne alternatifi: Manrope | Manrope | IBM Plex Mono |

> **Yasak kombinasyon:** düz `Inter` + `Poppins` + `Montserrat` üçlüsü.
> Bu, "AI üretti" işaretidir. Tek başına `Inter` kullanacaksan bile
> `Inter Tight` veya `Geist` tercih et ve `font-feature-settings` ile
> karakterini değiştir.

### 6.3 Ölçek (7 adım, majör üçlü ~1.25)

```
--text-xs:   12px / 16px  · +0.01em   etiket, tablo başlığı, yardımcı metin
--text-sm:   13px / 20px  ·  0        tablo hücresi, ikincil metin
--text-base: 14px / 22px  ·  0        UI varsayılanı (dashboard'da 14, pazarlamada 16)
--text-lg:   16px / 24px  · -0.005em  kart başlığı
--text-xl:   20px / 28px  · -0.01em   bölüm başlığı
--text-2xl:  24px / 32px  · -0.015em  sayfa başlığı
--text-3xl:  30px / 36px  · -0.02em   KPI değeri
--text-4xl:  40px / 44px  · -0.025em  hero (yalnız landing)
```

> **Kural:** Yazı büyüdükçe `letter-spacing` **azalır** (negatife gider).
> Bunu yapmayan tipografi amatör görünür. Küçük uppercase etiketlerde ise
> `letter-spacing` **artar** (+0.04em ila +0.08em).

### 6.4 Ağırlık

Sadece **3 ağırlık** kullan: `400` (body), `500` (UI/vurgu), `600`
(başlık). `700`+ yalnızca hero'da. `300` hiç kullanma — ekranda zayıf ve
okunmaz görünür.

### 6.5 Sayılar — atlanmaması gereken detay

Tablolarda, KPI'larda ve tüm sayısal hizalamalarda:

```css
font-variant-numeric: tabular-nums;
```

Bu tek satır dashboard'un profesyonellik hissini gözle görülür şekilde
artırır. Sayılar sütun halinde hizalanır, güncellenirken zıplamaz.

Ek olarak: para/ölçü birimi sayıdan **daha küçük ve muted** olur.

```
₺ 184.392  →  ₺ küçük+muted, 184.392 büyük+fg
```

---

## 7. LAYOUT & GRID

### 7.1 Uygulama iskeleti (dashboard/panel)

```
┌────────────┬──────────────────────────────────────────────┐
│            │  Topbar  56px                                │  ← breadcrumb + arama + kullanıcı
│  Sidebar   ├──────────────────────────────────────────────┤
│  264px     │                                              │
│            │  İçerik alanı                                │
│  (daralt:  │  padding: 24px 32px                          │
│   64px)    │  max-width: 1440px (ortalanmaz, sola yaslı)  │
│            │                                              │
├────────────┤                                              │
│ Kullanıcı  │                                              │
│ kartı 64px │                                              │
└────────────┴──────────────────────────────────────────────┘
```

**Ölçüler (referans ekranlardan çıkarılmış, tartışmasız):**

| Öğe | Değer |
|-----|-------|
| Sidebar genişliği | 240–280px (varsayılan **264px**) |
| Sidebar daraltılmış | 64px (yalnız ikon) |
| Topbar yüksekliği | 56px (yoğun) / 64px (ferah) |
| İçerik yatay padding | 24px (yoğun) / 32px (standart) |
| Kart aralığı (gap) | 16px (yoğun) / 24px (standart) |
| İçerik max genişlik | 1440px; 1920px ekranda **ortalama** |
| Okunabilir metin bloğu | max 68 karakter (`max-w-[68ch]`) |

### 7.2 Sidebar anatomisi

```
[Logo 28px]  [Ürün adı 14px/600]        [⌘ daralt ikonu]
────────────────────────────────────────────────────────
[🔍 Ara...]                                        ⌘K      ← 36px, surface-sunken
────────────────────────────────────────────────────────
ANA MENÜ                                                    ← 11px, 600, +0.06em, fg-subtle
  ▸ Genel bakış            ← 36px yükseklik, 8px radius
  ▸ Üretim            (3)  ← sayaç rozeti sağda
  ▸ Stok
ANALİZ & RAPOR                                              ← grup başlıkları arası 20px
  ▸ Performans
  ▸ Raporlar
────────────────────────────────────────────────────────
[Avatar 32px] Berkay
              Yönetici                            [⌄]
```

**Kurallar:**
- Grup başlıkları (`ANA MENÜ`) tıklanamaz, seçilemez, `user-select: none`.
- Aktif öğe: `surface-sunken` zemin + `fg` metin + `500` ağırlık.
  **Sol tarafta 2px aksan çubuğu opsiyonel** — ikisini birden yapma.
- Hover: yalnızca zemin değişir, metin renk değiştirmez. 120ms.
- İkonlar 16px, `stroke-width: 1.75`, metinle 10px boşluk.
- Nav öğesi yüksekliği 36px, iç padding `0 10px`, radius 8px.
- 7'den fazla öğe varsa **gruplamak zorunludur**.

### 7.3 Grid sistemi

```css
/* KPI satırı */
grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
gap: var(--space-4);

/* Ana içerik: 2/3 + 1/3 */
grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
```

> `minmax(0, ...)` kullan — aksi halde içerideki grafik/tablo grid'i
> patlatır. Dashboard'da en sık görülen layout hatası budur.

### 7.4 Kırılma noktaları

| Ad | px | Davranış |
|----|-----|----------|
| mobile | < 768 | Sidebar → drawer, KPI 1 sütun, tablo → kart listesi |
| tablet | 768–1279 | Sidebar daraltılmış, KPI 2 sütun |
| desktop | 1280–1919 | Tam sidebar, KPI 4 sütun |
| wide | ≥ 1920 | İçerik 1440px'de sabitlenir ve ortalanır |

**Tablolar mobilde asla yatay kaydırmaya bırakılmaz** — kart listesine
dönüşür veya sütun öncelik sırasına göre gizlenir.

---

## 8. BİLEŞEN SPESİFİKASYONLARI

### 8.1 KPI / Metrik kartı

Referans ekranların hepsinde aynı anatomi var. Bunu birebir uygula:

```
┌──────────────────────────────────────┐
│ [ikon 16px]  TOPLAM CİRO        [⋯] │  ← 12px/500/fg-muted, +0.02em
│                                      │
│  ₺184.392                            │  ← 30px/600/fg, tabular-nums
│                                      │     (₺ 18px/muted)
│  ↑ 12,4%  geçen haftaya göre         │  ← 12px; ok+yüzde renkli, metin subtle
└──────────────────────────────────────┘
   padding: 20px · radius: 12px · 1px border · gölge YOK
```

**Kesin kurallar:**
- Sıralama **her zaman**: etiket → değer → delta. Değeri üste koyma.
- Delta rengi: pozitif `success`, negatif `danger` — **ama** "gider arttı"
  gibi durumlarda ters çevir. Renk *iyi/kötü*yü anlatır, *artış/azalış*ı değil.
- Delta metninde karşılaştırma dönemi **zorunlu** ("geçen haftaya göre").
  Bağlamsız yüzde değersizdir.
- Kart içine sparkline eklenecekse: sağ üstte, 64×24px, dolgusuz, tek renk,
  eksen yok, tooltip yok.
- 4'ten fazla KPI kartı = kullanıcı hiçbirini okumaz. Maks 4.

#### 8.1.1 KPI kartı varyantları

Referans ekranlarda 5 farklı anatomi görülüyor. **Projede tek varyant
seç.** Aynı satırda iki farklı KPI anatomisi = amatör işareti.

| Varyant | Anatomi | Ne zaman kullanılır |
|---------|---------|---------------------|
| **A — Sade** | etiket → değer → delta | **Varsayılan.** 4 kart yan yana, en yüksek okunabilirlik |
| **B — İkonlu** | 16px ikon + etiket → değer → delta | Metrikler görsel olarak birbirinden ayrışsın isteniyorsa |
| **C — Rozetli** | 36px tinted ikon kutusu sol üst + delta pill **sağ üst** → etiket → değer | 2-4 kart, pazarlamaya yakın ürünler. Yoğun panelde kullanma |
| **D — İlerlemeli** | etiket + ikon kutusu sağ üst → değer → delta → **kartın altında 4px ilerleme çubuğu** | Metriğin bir hedefe göre konumu varsa (kota, OEE, hedef ciro) |
| **E — Sparkline'lı** | etiket + ikon sağ üst → değer → delta, sağda veya altta 64×24 sparkline | Trend yönü, değerin kendisi kadar önemliyse |

**Varyant D ilerleme çubuğu detayı:** kartın alt kenarına yapışık, 4px
yükseklik, `surface-sunken` ray + metriğin kendi rengi. Yüzde metni
yazma — çubuk zaten anlatıyor.

**Varyant C delta rozeti:** `success-subtle` zemin, `success` metin,
20px yükseklik, radius 6px, içinde küçük trend ikonu + yüzde.

#### 8.1.2 KPI ikon kutusu

Varyant C ve D'de kullanılan ikon konteyneri:

```
36×36px · radius 8px · zemin: ilgili rengin %10 alpha'sı
ikon 18px, tam merkezde, rengin tam tonu
```

**Kural:** ikon kutusu rengi metriğin anlamıyla ilişkili olmalı
(ciro→accent, hata→danger, süre→warning). Rastgele renklendirme
"dekoratif" görünür ve ucuzlatır.

### 8.2 Grafik kartı

```
┌─────────────────────────────────────────────────┐
│ Ciro Trendi                    [Aylık ⌄]  [⋯]  │  ← 16px/600 + kontroller sağda
│ ₺184.392  ↑12,4%                                │  ← özet değer başlıkta, grafikte değil
├─────────────────────────────────────────────────┤
│                                                 │
│           [grafik alanı, min-height 240px]      │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Grafik kuralları:**
- Y ekseni **grid çizgileri**: yatay, `border` rengi, dashed **değil** düz,
  opaklık %60. Dikey grid çizgisi yok.
- Y ekseni etiketleri: 11px, `fg-subtle`, kısaltılmış (`50k` değil `50B`
  Türkçe için — veya birim başlıkta belirtilip sayı çıplak bırakılır).
- Eksen çizgisi (`axisLine`) ve tick işaretleri **kapatılır**.
- Tooltip: `surface` zemin, 1px border, `shadow-md`, radius 8px, 12px metin.
  Tarih başlıkta bold, değerler altında renk noktası + isim + tabular sayı.
- Alan grafiği dolgusu: aksan renginin `%12 → %0` dikey gradient'i. Düz
  dolgu yapma.
- Çizgi kalınlığı 2px, `strokeLinecap: round`, nokta yok (yalnız hover'da).
- **Sıra ve renk:** kategori sırası ile renk sırası sabit kalır. Sayfa
  yenilendiğinde renkler değişiyorsa hata var.

### 8.3 Veri tablosu

```
┌─────────────────────────────────────────────────────────────┐
│ Tüm kullanıcılar  145      [Son 30 gün ⌄] [Filtre] [🔍 Ara] │  ← 52px araç çubuğu
├────┬───────────────────┬──────────┬─────────┬───────────────┤
│ ☐  │ KULLANICI         │ ROL      │ DURUM   │ SON AKTİVİTE  │  ← 11px/500/+0.04em/subtle
├────┼───────────────────┼──────────┼─────────┼───────────────┤   surface-sunken zemin
│ ☐  │ (A) Ayşe Kaya     │ [Yönetici]│ ● Aktif │ 2 dakika önce │  ← 48px satır
│    │     ayse@x.com    │          │         │               │
└────┴───────────────────┴──────────┴─────────┴───────────────┘
```

| Özellik | Kural |
|---------|-------|
| Satır yüksekliği | 44px (yoğun) / 52px (iki satırlı hücre) |
| Zebra şerit | **Yok.** Ayırıcı olarak 1px alt border kullan. |
| Hover | Satır zemini `surface-sunken`, 100ms |
| Başlık | Sticky, `surface-sunken`, alt border 1px |
| Sayısal sütun | **Sağa hizalı**, `tabular-nums` |
| Tarih sütunu | Göreli ("3 saat önce") + `title` içinde tam tarih |
| Aksiyon sütunu | En sağda, sabit genişlik, satır hover'ında görünür |
| Sıralama | Başlık tıklanabilir, aktif sütunda ok ikonu |
| Sayfalama | Alt sağda; toplam kayıt sayısı **her zaman** yazılır |
| Boş durum | Bölüm 10 |
| Yükleniyor | Skeleton satırlar (5 adet), spinner değil |

### 8.4 Durum rozeti (badge)

```
● Aktif        → success-subtle zemin, success metin, 6px nokta
● Beklemede    → warning-subtle
● Askıda       → danger-subtle
● Pasif        → surface-sunken zemin, fg-muted metin
```

- Yükseklik 22px, padding `2px 8px`, radius 6px (pill **değil**, tablo
  içinde pill amatör durur), 12px/500 metin.
- Nokta göstergesi 6px, metinle 6px boşluk.
- **Renk tek başına anlam taşımaz** — metin her zaman yazılır (erişilebilirlik).
- Rozet sayısı 5'i geçmesin; geçiyorsa gruplama yanlış.

### 8.5 Buton

| Varyant | Zemin | Metin | Kenarlık | Kullanım |
|---------|-------|-------|----------|----------|
| Primary | `accent` | `fg-on-accent` | yok | Sayfada **1 tane** |
| Secondary | `surface` | `fg` | 1px `border` | Yan eylemler |
| Ghost | şeffaf | `fg-muted` | yok | Tablo içi, ikon butonlar |
| Danger | `danger` | beyaz | yok | Yalnız yıkıcı eylem |

- Yükseklik: `sm` 32px · `md` 36px · `lg` 40px. Dashboard varsayılanı **36px**.
- Padding: `0 14px` (ikonlu: sol 12px), ikon-metin boşluğu 6px.
- Metin 14px/500. **Uppercase yapma.**
- `disabled`: opaklık 0.5 + `cursor: not-allowed`. Renk değiştirme.
- Yükleniyor: metin yerinde kalır, sol tarafa 14px spinner girer,
  buton **genişliği değişmez** (layout zıplaması yasak).
- Focus: `outline: 2px solid accent; outline-offset: 2px`. Kaldırma.

### 8.6 Form alanı

```
Şirket unvanı *                          ← 13px/500/fg, alt 6px
┌────────────────────────────────────┐
│ Örn. Yılmaz Metal San. Tic. A.Ş.   │   ← 36px, 1px border, radius 8px
└────────────────────────────────────┘
Ticaret sicil kaydındaki tam ad.         ← 12px/fg-subtle, üst 6px
```

- Focus: kenarlık `accent` + `box-shadow: 0 0 0 3px accent/12%`.
- Hata: kenarlık `danger` + altta 12px `danger` metin + `aria-invalid`.
  **Hata mesajı ne yapılacağını söyler:** "E-posta geçersiz" değil,
  "E-posta adresi ad@site.com biçiminde olmalı".
- Zorunlu alan: etiket yanında `*`, ayrıca form başında "* zorunlu alan".
- Placeholder etiketin yerine geçmez. Placeholder **örnek** verir.
- Doğrulama zamanı: `blur`'da ilk kez, sonra `change`'de canlı.
- Form genişliği: tek sütun, max **480px**. Geniş ekranda form alanlarını
  esnetme.

### 8.7 Modal / Drawer

- Modal genişliği: `sm` 420px · `md` 560px · `lg` 720px. Yüksekliği içerik
  belirler, maks `85vh` sonra iç kaydırma.
- Overlay: `rgb(0 0 0 / 0.4)` + `backdrop-filter: blur(2px)`.
- Başlık 18px/600, sağ üstte kapatma ikonu 32×32 ghost buton.
- Alt eylem çubuğu: sağa hizalı, `[İptal] [Onayla]` sırası (Türkçe/LTR).
- `Esc` kapatır, açılınca ilk odaklanabilir öğeye focus, focus trap zorunlu,
  kapanınca focus tetikleyen öğeye döner.
- **Yıkıcı işlemlerde**: onay butonu `danger`, ve metin eylemi tekrarlar
  ("Sil" değil, "Kalıcı olarak sil").

### 8.8 Toast / Bildirim

- Konum: sağ üst (masaüstü), alt (mobil). 4px offset.
- Süre: bilgi 4sn, başarı 3sn, hata **otomatik kapanmaz**.
- Yapı: durum ikonu + tek satır başlık + (opsiyonel) eylem bağlantısı.
- Aynı anda maks 3 toast, fazlası kuyruğa alınır.
- Eylem sonucu geçmiş zamanla yazılır: buton "Yayınla" → toast "Yayınlandı".

### 8.9 Çalışma alanı / kiracı seçici

Çok kiracılı (multi-tenant) ürünlerde sidebar'ın **en üstünde**, logonun
altında değil, logonun **yerinde**:

```
┌──────────────────────────────────────┐
│ [◧ 32px]  Yılmaz Metal          [⌃⌄] │  ← ad 14px/600
│           Kurumsal                    │  ← plan 12px/subtle
└──────────────────────────────────────┘
```

- Yükseklik 48px, hover'da `surface-sunken`, radius 8px.
- Sağdaki ikon çift ok (`chevrons-up-down`), tek chevron değil — bu
  "değiştirilebilir" sinyali verir.
- Açılan menü: mevcut alanlar listesi + ✓ işareti + altta ayırıcı +
  "Yeni çalışma alanı" ve "Çalışma alanı ayarları".
- **Plan adı burada gösterilir** ("Kurumsal", "Deneme — 4 gün"). Deneme
  süresi bitiyorsa `warning` rengiyle.

> FabrikaOS gibi tenant bazlı ürünlerde bu bileşen zorunludur. Kullanıcı
> hangi fabrikada/şirkette olduğunu her an görebilmeli.

### 8.10 Filtre çipi satırı

İçeriğin hemen üstünde, yatay dizilim:

```
[📅 Son 7 gün ⌄]  [🏷 Tüm etiketler ⌄]  [⚙ Tüm hatlar ⌄]      [Sıfırla]
```

- Çip yüksekliği 32px, radius 8px, 1px `border`, zemin `surface`.
- İçerik: 14px ikon + 13px metin + 14px chevron, boşluklar 6px.
- **Aktif filtre** (varsayılandan farklı): kenarlık `accent`, zemin
  `accent-subtle`, metin `accent`. Bu ayrım olmazsa kullanıcı neyi
  filtrelediğini unutur.
- En az 1 filtre aktifse sağda "Sıfırla" ghost butonu belirir.
- Çipler arası 8px. 5'ten fazla çip varsa "Daha fazla filtre" ile
  popover'a taşı.

### 8.11 Segment kontrolü (segmented control)

İki-dört seçenek arasında geçiş için. Sekme **değildir** — sekme sayfa
bölümü değiştirir, segment aynı veriyi farklı gösterir.

```
┌──────┬────────┐
│ 24s  │ 7g │ 30g │ 90g │ YTD │
└──────┴────────┘
```

- Konteyner: `surface-sunken` zemin, radius 8px, 3px iç padding.
- Seçili öğe: `surface` zemin, `shadow-sm`, radius 6px, metin `fg`/500.
- Seçili olmayan: şeffaf, metin `fg-muted`.
- Yükseklik 32px, öğe padding `0 12px`, metin 13px.
- Geçiş animasyonu: seçili arka planın kayması, 180ms
  `cubic-bezier(.16,1,.3,1)`. (Framer Motion `layoutId` ile.)
- Grafik kartlarında **sağ üstte**, kart başlığıyla aynı hizada.

### 8.12 Sıralı dağılım listesi

Bir metriğin kategorilere göre dağılımını gösterir (il, hat, ürün,
tedarikçi). Donut'a göre **her zaman daha okunaklıdır** — 5'ten fazla
kategori varsa donut yerine bunu kullan.

```
Ofis WiFi 1   ──────────────────────────────  8,21 GB  ●
Ofis WiFi 2   ────────────────                4,54 GB  ●
Ofis WiFi 3   ──────────                      3,11 GB  ●
```

veya yığılmış (iki seri karşılaştırması):

```
Manisa    [████████ 210.345 |████ 175.289]
Bursa     [███████ 190.412  |████ 160.578]
```

- Satır yüksekliği 28px, etiket sol sabit genişlik (max %35), çubuk
  esner, değer sağda `tabular-nums`.
- Yığılmış varyantta değer **çubuğun içinde**, beyaz metin 11px/500 —
  çubuk 40px'den darsa dışarı taşır.
- Ray (`track`) rengi `surface-sunken`, çubuk 6px yükseklik, radius 3px.
- **Sıralama her zaman büyükten küçüğe.** Alfabetik sıralama bu
  bileşenin amacını yok eder.
- 10 satırdan fazlası scroll'a alınır, konteynere `max-height` verilir.

### 8.13 Donut + açıklama listesi

```
      ╭─────╮        ● Başarılı    21.142  (%86,1)
    ╭─┤24.532├─╮      ● Çalışıyor    2.345  (%9,6)
    │ │Toplam│ │      ● Bekliyor       732  (%3,0)
    ╰─┴─────┴─╯      ● İptal           313  (%1,3)
```

- Donut kalınlığı: dış yarıçapın **%22'si** (daha ince = zayıf, daha
  kalın = pasta grafiğe döner).
- Merkezde toplam: değer 24px/600 + altında etiket 12px/subtle.
- **Segment sayısı maks 5.** Fazlası "Diğer" altında toplanır.
- Açıklama listesi sağda, dikey; her satır: 8px renk noktası + isim
  (14px) + sağda değer (`tabular-nums`) + yüzde (12px/subtle).
- Açıklama listesi **her zaman** yazılır. Sadece donut = okunamaz grafik.
- Bir segmente hover → hem dilim hem liste satırı vurgulanır.

### 8.14 Grafik tooltip'i

Referans ekranların hepsinde tooltip'ler zengin. Basit "değer" tooltip'i
amatör durur.

```
┌────────────────────────────┐
│ Perşembe, 15 Tem 2026      │  ← 12px/600/fg
├────────────────────────────┤
│ ● Kâr              ₺55.000 │  ← 12px; nokta 8px, isim muted, değer fg
│ ● Hedef            ₺74.000 │
│ ● Kapanan işlem          2 │
├────────────────────────────┤
│ Marj                  %60  │  ← türetilmiş metrik (varsa)
│ Önceki güne göre    +%43,4 │  ← karşılaştırma, renkli
└────────────────────────────┘
```

- Zemin `surface`, 1px `border`, `shadow-md`, radius 8px, padding 10px 12px.
- Ayırıcı çizgiler: `border` rengi, sadece mantıksal gruplar arasında.
- Değerler sağa hizalı, `tabular-nums`.
- **Türetilmiş metrik ve karşılaştırma satırı ekle** — tooltip'i
  değerli yapan şey budur. Ham sayıyı zaten eksenden okuyabiliyor.
- Tooltip imleci takip etmez; en yakın veri noktasına **kilitlenir**
  (`cursor` olarak dikey çizgi gösterilir).

### 8.15 Aktivite akışı

```
(A)  Ahmet  Enterprise Pipeline'da bir            1 sa önce
     anlaşma kapattı
(M)  Mehmet Müşteri Onboarding'de engel           2 sa önce
     bildirdi
```

- Avatar 28px, metinle 10px boşluk.
- Metin 13px: **aktör adı 500 ağırlık + `fg`**, eylem `fg-muted`,
  nesne adı `fg` ve tıklanabilir.
- Zaman sağda, 12px `fg-subtle`, sabit genişlik, `title` içinde tam tarih.
- Satırlar arası 16px, ayırıcı çizgi **yok** (avatar ritmi zaten ayırıyor).
- Maks 5-6 öğe + altta "Tümünü gör →".
- Eylem metni **geçmiş zaman** ve **üçüncü şahıs**: "kapattı", "ekledi".

### 8.16 Canlı akış tablosu

Gerçek zamanlı güncellenen listelerde (izleme, log, sipariş akışı):

```
Canlı akış                                    ● Canlı
Akış halinde · son 10                    ↑ nokta 6px, success, 2s nabız
─────────────────────────────────────────────────────
02:27   Satış Botu     inceleme hatası      2,10 sn
02:26   Onboarding     ~~işlem başarısız~~  [Hata]
```

- "● Canlı" göstergesi: 6px nokta + 12px metin, nokta 2s aralıkla
  `opacity 1 → 0.4` nabız. `prefers-reduced-motion`'da nabız durur.
- Yeni satır **üstten** girer: `opacity 0→1` + `translateY(-4px→0)`,
  200ms. Liste kaymaz, alttaki eleman düşer.
- Hata satırı: metin `line-through` + `fg-subtle` + sağda `[Hata]` rozeti.
- Varlık adları (ajan, kullanıcı, servis) kendi sabit renginde —
  **renk her zaman aynı varlığa denk gelir**, rastgele atanmaz.
- Otomatik kaydırma varsa kullanıcı yukarı kaydırdığında **durdurulur**
  ve "N yeni kayıt ↑" butonu gösterilir.

### 8.17 Kanban / aşama sütunları

```
┌ Ön görüşme  2 ┐┌ Nitelikli  4 ┐┌ Demo  6 ┐┌ Teklif  2 ┐
│ ┌───────────┐ ││              ││          ││           │
│ │ Nebula A.Ş.│ ││              ││          ││           │
│ │ ₺120.000   │ ││              ││          ││           │
│ │ (A) Adem   │ ││              ││          ││           │
│ │  4g   ◎89  │ ││              ││          ││           │
│ └───────────┘ ││              ││          ││           │
└───────────────┘└──────────────┘└──────────┘└───────────┘
```

- Sütun başlığı: 14px ikon + isim 13px/500 + sağda sayı rozeti
  (`surface-sunken` zemin, 20px, radius 6px).
- Sütun zemini `surface-sunken`, radius 12px, padding 8px.
- Kart: `surface` zemin, 1px `border`, radius 8px, padding 12px, **gölge yok**.
- Kart içi: başlık 13px/`fg-muted` → değer 16px/600/`fg` → alt satırda
  avatar 20px + süre + skor.
- Kartlar arası 8px.
- Sürükleme: kalkan kart `shadow-lg` + `rotate(1.5deg)` + `scale(1.02)`,
  hedef sütunda 2px dashed `accent` yer tutucu.
- Sütun yüksekliği eşit, içerik taşarsa sütun içinde scroll.

### 8.18 Liderlik tablosu / skorlu liste

```
(A) Jason Wu                                      [92]
    jason.wu@example.com
(D) David Lee                                     [91]
    david.lee@example.com
```

- Avatar 32px + iki satırlı metin (isim 13px/500, alt 12px/subtle).
- Skor çipi sağda: 28×22px, radius 6px, `tabular-nums` 13px/500.
- **Skor rengi eşiğe göre:** ≥90 `success-subtle`, 70-89 nötr
  (`surface-sunken`), <70 `warning-subtle`. Eşikler BRIEF'te tanımlanır,
  koda gömülmez.
- Sıra numarası göstermek gerekiyorsa avatarın solunda 20px sabit
  genişlikte, `fg-subtle`, `tabular-nums`.
- Satır yüksekliği 52px, ayırıcı çizgi yok.

### 8.19 Görev / kontrol listesi

```
☐ Kurumsal onboarding akışını gözden geçir        (A)
☑ Q3 otomasyon raporunu tamamla                   (M)   ← üstü çizili + muted
☐ Pasif iş akışlarını denetle (3 bulundu)         (S)
```

- Checkbox 16px, radius 4px, işaretliyken `accent` dolgu + beyaz tik.
- **Tamamlanan öğe:** metin `line-through` + `fg-subtle`. Listeden
  kaldırma — tamamlanma hissi değerlidir.
- Sorumlu avatarı sağda 24px.
- Satır yüksekliği 40px, hover'da `surface-sunken`.
- İşaretleme animasyonu: tik 150ms `ease-out` çizilir, metin 200ms
  içinde soluklaşır. Satır **yerinden oynamaz**.

### 8.20 Zaman bloğu / randevu öğesi

```
┌────┐  Cum, 16 Ağu 2026 · 14:40
│ 16 │  Ahmet Yılmaz                          ₺560.000
│Ağu │  Değerleme · 2s 30dk · Berkay ile
└────┘
```

- Tarih bloğu: 44×44px, `surface-sunken` zemin, radius 8px;
  gün 16px/600 üstte, ay 11px/subtle altta, ikisi merkezde.
- Sağ blok üç satır: üst meta (12px/subtle) → ana isim (13px/500) →
  alt detay (12px/subtle).
- Tutar/değer varsa en sağda, `tabular-nums`, 13px/500.
- Öğeler arası 8px, hover'da tüm satır `surface-sunken`.

### 8.21 Trend rozeti

Tablo içinde yön göstermek için (yıldızlı yüzde yerine):

```
[⌃ Artıyor]   danger-subtle    ← kötü metrik artıyorsa
[– Sabit]     surface-sunken
[⌄ Azalıyor]  success-subtle
```

- 22px yükseklik, radius 6px, 11px/500 metin, 12px ikon.
- **Renk anlama bağlıdır, yöne değil.** "Hata sayısı artıyor" kırmızı,
  "ciro artıyor" yeşil. Bunu bileşene prop olarak geçir (`sentiment`),
  yönden türetme.

### 8.22 Ekleme kartı (dashed)

Kart ızgaralarının sonunda:

```
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
│        (+)         │
│  Yeni anket başlat │
│  Dakikalar içinde  │
│  veri toplamaya    │
│  başlayın          │
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

- 1px dashed `border`, zemin `accent-subtle` veya şeffaf, radius 12px.
- Diğer kartlarla **aynı yükseklik** (`items-stretch`).
- İçerik dikey merkezde: 32px daire içinde + ikonu → başlık 14px/500 →
  açıklama 12px/muted.
- Hover: kenarlık `accent`, zemin hafif koyulaşır, 120ms.
- Bu bileşen liste boşken **kullanılmaz** — o durumda Bölüm 10.1 boş
  durumu gösterilir.

### 8.23 Upsell / duyuru kartı

- Zemin: `accent-subtle` **düz renk** — gradient yasak (Bölüm 13.1).
- İkon kutusu 36px + başlık 15px/600 + açıklama 13px/muted + tam
  genişlik primary buton.
- Panel içinde **en fazla 1 tane**, ve asla birincil içeriğin üstünde değil.
- Kapatılabilir olmalı (× ikonu), kapatma tercihi kalıcı saklanır.

### 8.24 Navigasyon rozetleri ve etiketler

| Tür | Görünüm | Kullanım |
|-----|---------|----------|
| Sayaç | `12` — `surface-sunken` zemin, `fg-muted`, 18px, radius 6px | Bekleyen öğe sayısı |
| Dikkat sayacı | `3` — `danger-subtle` zemin, `danger` metin | Aksiyon gerektiren |
| Yeni etiketi | `YENİ` — `success-subtle`, 10px/600, +0.06em | Yeni özellik, 30 gün sonra kaldırılır |
| Durum noktası | 6px renkli daire | Proje/ortam durumu (prod/staging/dev) |

- Rozetler nav öğesinin **sağ kenarına** hizalanır, metne değil.
- Sayı 99'u geçerse `99+`.
- Sidebar'da aynı anda **3'ten fazla rozet olmasın** — hepsi acilse
  hiçbiri acil değildir.

### 8.25 İç içe (nested) navigasyon

```
▾ Panel                                    ← ana öğe, chevron solda değil sağda
  │ Genel bakış                            ← aktif: surface-sunken
  │ Analitik
  │ Raporlar
  ▸ Görevler                          12
```

- Alt öğeler 12px sola girintili, solda 1px `border` dikey ray.
- Alt öğe yüksekliği 32px (ana öğe 36px), metin 13px.
- Açılma/kapanma: `grid-template-rows: 0fr → 1fr` + 200ms. `height: auto`
  animasyonu **yapma**.
- Aktif alt öğe varken ana öğe kapalı olamaz — sayfa yüklenirken
  otomatik açılır.
- **Maks 2 seviye.** 3. seviye gerekiyorsa bilgi mimarisi yanlış.

### 8.26 Gelişmiş grafik desenleri

Referans ekranlardan çıkarılan, tek başına kaliteyi yükselten üç kalıp:

**1. Bindirmeli çubuk (gerçekleşen / kapasite)**
Gri arka çubuk = hedef/kapasite, önündeki renkli çubuk = gerçekleşen.
İki ayrı çubuk yan yana koymaktan **çok daha okunaklı**. Üretim,
kota, kapasite metriklerinde varsayılan seçim olmalı.
Gri çubuk `surface-sunken`, renkli çubuk tam opak, aynı x konumunda,
renkli olan %55 genişlikte ve ortalanmış.

**2. Taralı (hatch) dolgu**
Renk yerine desen kullanmak, hem renk körü erişilebilirliği sağlar hem
görsel olarak pahalı durur. SVG `<pattern>` ile 45° 1px çizgiler, 4px
aralık, `border` renginde. "Tahmin", "geçen dönem", "hedef" gibi
**ikincil serilerde** kullan — birincil seri her zaman düz dolgu.

**3. Eksen etiketi sıfır dolgulu hizalama**
Y ekseninde `00, 03, 06, 09, 12` gibi sabit karakter uzunluğu, veya
`tabular-nums`. Etiket genişliği değiştikçe grafik alanı kayarsa
(canlı güncellemede) ekran titrer — en sık gözden kaçan hata.

**Ayrıca:**
- Çok serili çizgi grafiklerde seri sayısı **maks 4**. Fazlası okunmaz.
- Sütun grafikte çubuk genişliği ≈ boşluğun 2 katı (`barCategoryGap: 30%`).
- Negatif değer varsa sıfır çizgisi `border-strong` ile vurgulanır.

---

## 9. SAYFA ŞABLONLARI

### 9.1 Her sayfada zorunlu iskelet

```
1. Breadcrumb (2+ seviye derinlikte)         12px/subtle
2. Sayfa başlığı H1                          24px/600
3. Alt açıklama (opsiyonel, tek satır)       14px/muted
4. Sağ üstte birincil eylem                  1 adet primary buton
5. ───── 24px boşluk ─────
6. Filtre / segment çubuğu (varsa)
7. İçerik
```

### 9.2 Dashboard / Genel bakış

```
Selamlama + tarih aralığı seçici + [Dışa aktar]
─────────────────────────────────────────────────
[KPI] [KPI] [KPI] [KPI]                      ← 4 kart, aynı yükseklik
─────────────────────────────────────────────────
┌──────────────────────────┬──────────────────┐
│  Ana trend grafiği        │  İkincil dağılım │  ← 2fr / 1fr
│  (zaman serisi)           │  (donut/liste)   │
└──────────────────────────┴──────────────────┘
┌──────────────────────────┬──────────────────┐
│  Son işlemler tablosu     │  Uyarılar /      │
│  (maks 5-8 satır + "Tümü")│  Aktivite akışı  │
└──────────────────────────┴──────────────────┘
```

Yoğun (izleme/operasyon) panellerde selamlama satırı yerine **filtre
çipi satırı** (Bölüm 8.10) konur:

```
[📅 Son 24 saat ⌄] [🏭 Tüm hatlar ⌄] [🏷 Tüm etiketler ⌄]   [↻ Yenile] [+ Yeni]
```

**Bilgi hiyerarşisi kuralı:** Kullanıcı 5 saniyede **tek bir soruya**
cevap bulmalı (BRIEF'teki `birincil_is`). O soruya cevap veren öğe
ekranın sol-üst çeyreğinde ve en büyük tipografiye sahip olmalı.

**Yoğunluk modu seçimi:**

| Mod | Kart padding | Satır yük. | Metin | Ne zaman |
|-----|--------------|------------|-------|----------|
| Ferah | 24px | 52px | 14px | Günde birkaç kez bakılan yönetici paneli |
| Dengeli | 20px | 48px | 14px | **Varsayılan** |
| Yoğun | 16px | 44px | 13px | 8+ saat açık kalan operasyon/izleme ekranı |

BRIEF'teki `yogunluk` alanı bunu belirler ve **tüm sayfalarda aynı
kalır**. Sayfa başına yoğunluk değiştirmek tutarsızlık üretir.

### 9.3 Liste / Tablo sayfası

```
Başlık + kayıt sayısı           [Filtreler] [+ Yeni kayıt]
─────────────────────────────────────────────────────────
[Segment sekmeler: Tümü (145) | Aktif (31) | Bekleyen (24)]
─────────────────────────────────────────────────────────
[Arama] [Sütun seçici] [Dışa aktar]        [Seçili: 3 ⋯]
─────────────────────────────────────────────────────────
[ Tablo ]
─────────────────────────────────────────────────────────
145 kayıttan 1-25 arası          [‹] 1 2 3 … 6 [›]
```

- Filtreler URL'de tutulur (`?status=active&page=2`) — sayfa yenilenince
  kaybolmaz, link paylaşılabilir.
- Toplu seçim yapıldığında araç çubuğu **yerinde değişir**, yeni bar açılmaz.

### 9.4 Detay sayfası

```
‹ Listeye dön
[Başlık büyük] [durum rozeti]              [Düzenle] [⋯]
Alt bilgi satırı: ID · oluşturulma · sorumlu
─────────────────────────────────────────────────────────
[Sekmeler: Genel | Geçmiş | Belgeler | Ayarlar]
─────────────────────────────────────────────────────────
┌─────────────────────────┬──────────────────────────┐
│  Ana içerik              │  Yan panel:              │
│                          │  - özet alanlar          │
│                          │  - ilişkili kayıtlar     │
│                          │  - zaman çizelgesi       │
└─────────────────────────┴──────────────────────────┘
```

### 9.5 Form / Sihirbaz sayfası

- 6'dan fazla alan → **bölümlere ayır** (fieldset + başlık).
- 3 bölümden fazla → **çok adımlı sihirbaz**, üstte ilerleme göstergesi.
- Kaydet butonu: kısa formda altta, uzun formda **sticky alt çubuk**.
- Kaydedilmemiş değişiklikle sayfadan çıkışta uyarı.
- Otomatik kaydetme varsa durum göstergesi: "Kaydediliyor… / Kaydedildi 14:32".

### 9.6 Auth (giriş / kayıt)

- İki sütun: sol form (max 400px, dikey ortalı), sağ marka alanı.
- Sağ alan **stok fotoğraf olmaz** — ürünün gerçek bir ekran görüntüsü,
  soyut bir desen veya tek bir güçlü tipografik ifade.
- Sosyal giriş butonları formun **üstünde**, ayırıcı ("veya") ile.
- Hata: form üstünde tek bir uyarı bloğu, alan altında değil.

### 9.7 Ayarlar

- Sol dikey sekme navigasyonu (200px) + sağ içerik.
- Her ayar grubu bir kart, kart başlığı + açıklama + kontrol.
- **Anında kaydet** (toggle'lar) veya **kartın altında kaydet butonu** —
  ikisini karıştırma, sayfa genelinde tek model seç.
- Tehlikeli bölge en altta, `danger` kenarlıklı ayrı kartta.

---

## 10. DURUM TASARIMI

> Ekranların %70'i "mutlu yol" için tasarlanır, %30'u unutulur.
> Unutulan %30 kullanıcının kaliteyi yargıladığı yerdir.
> **Her sayfa için 5 durum da kodlanır.**

### 10.1 Boş durum (hiç veri yok)

```
        [ikon 40px, fg-subtle]

     Henüz tedarikçi eklenmedi          ← 16px/600
  Tedarikçi ekleyerek sipariş           ← 14px/muted, max 2 satır
  takibine başlayabilirsiniz.
  
       [+ Tedarikçi ekle]               ← primary buton
```

- "Veri bulunamadı" **yasak**. Ne olacağını ve nasıl başlanacağını söyle.
- Boş durum bir **davettir**, bir hata değil. Aksiyon butonu zorunlu.

### 10.2 Filtre sonucu boş (veri var ama filtre eşleşmedi)

Farklı metin: "'metal' aramasıyla eşleşen kayıt yok" + **[Filtreleri temizle]**.
Bu durumu 10.1 ile aynı yapma — kullanıcı hangi durumda olduğunu bilmeli.

### 10.3 Yükleniyor

- **Skeleton kullan, spinner değil.** Skeleton gerçek içeriğin şeklini
  taklit eder (aynı yükseklik, aynı sütun genişlikleri).
- Skeleton animasyonu: `shimmer` değil, `opacity 0.6 ↔ 1` 1.5s ease-in-out.
  Shimmer 2019 estetiği.
- 300ms'den kısa sürecek yüklemelerde **hiçbir şey gösterme** (flash önleme).
- Buton içi yükleme: Bölüm 8.5.

### 10.4 Hata

```
     Veriler yüklenemedi                ← ne oldu
  Sunucuya ulaşılamıyor. Bağlantınızı   ← neden (biliniyorsa)
  kontrol edip tekrar deneyin.
       [Tekrar dene]                    ← nasıl çözülür
```

- Teknik hata kodu gösterilecekse **küçük ve altta** (`HTTP 503 · req_a8f2`).
- Kısmi hata: yalnızca o widget hata gösterir, sayfa çökmez.
  (Her grafik kartı kendi error boundary'sinde olmalı.)

### 10.5 Yetkisiz / bulunamadı

- 403: ne yapılacağını söyle ("Bu sayfa için yönetici yetkisi gerekli.
  Erişim talep et →").
- 404: geri dönüş yolu ver, ana sayfaya at.

---

## 11. HAREKET & ANİMASYON

### 11.1 Süre ve easing tablosu

| Etkileşim | Süre | Easing |
|-----------|------|--------|
| Hover / renk geçişi | 120ms | `ease-out` |
| Buton basma | 80ms | `ease-out` |
| Dropdown / popover açılış | 160ms | `cubic-bezier(.16,1,.3,1)` |
| Modal açılış | 220ms | `cubic-bezier(.16,1,.3,1)` |
| Drawer / sheet | 280ms | `cubic-bezier(.32,.72,0,1)` |
| Sayfa geçişi | 200ms | `ease-out` |
| Toast girişi | 200ms | `cubic-bezier(.16,1,.3,1)` |
| Kapanış (her şey) | giriş × 0.75 | `ease-in` |

> **Kural:** 300ms'yi geçen hiçbir UI animasyonu olmaz. Geçiyorsa
> yavaş hissettirir. Kapanış her zaman açılıştan hızlıdır.

### 11.2 Ne animasyon edilir

**Edilir:** `opacity`, `transform` (translate/scale).
**Edilmez:** `width`, `height`, `top/left`, `margin`, `box-shadow`
(GPU dışı, jank yapar). Yükseklik animasyonu gerekiyorsa `grid-template-rows: 0fr → 1fr`.

### 11.3 Yasaklar

- Sayfa yüklenişinde her elemanın sırayla belirmesi (staggered fade-in)
  → **dashboard'da yasak.** Kullanıcı her gün 40 kez açıyor; 3. seferde
  sinir bozucu olur. Yalnızca landing sayfalarında, yalnızca bir kez.
- Sonsuz dönen/parlayan arka plan efektleri.
- Scroll-jacking.
- Hover'da kartın büyümesi (`scale > 1.02`).
- Otomatik oynayan carousel.

### 11.4 Zorunlu

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## 12. ERİŞİLEBİLİRLİK

Bunlar "sonra bakarız" maddeleri değil, ilk yazımda uygulanır.

- [ ] Metin kontrastı ≥ **4.5:1**, büyük metin (≥18.66px/600) ≥ 3:1.
- [ ] UI bileşeni kenarlığı / ikon kontrastı ≥ **3:1**.
- [ ] Her etkileşimli öğe klavye ile erişilebilir, `Tab` sırası mantıklı.
- [ ] **Görünür focus halkası** — `outline: none` yazıldığı her yerde
      alternatif focus stili zorunlu.
- [ ] Modal/drawer'da focus trap, `Esc` ile kapanış, kapanışta focus dönüşü.
- [ ] İkon-only butonlarda `aria-label`.
- [ ] Form alanları `<label for>` ile bağlı; `aria-describedby` ile
      yardım/hata metni.
- [ ] Bilgi **yalnızca renkle** verilmez (rozet metni, grafik etiketi).
- [ ] Grafiklerde renk körü güvenli palet + desen/etiket yedeği.
- [ ] Dinamik içerik değişiminde `aria-live="polite"` (toast, arama sonucu).
- [ ] Sayfa `<h1>` ile başlar, başlık seviyeleri atlanmaz.
- [ ] Dil: `<html lang="tr">`.

Denetim: `chrome-devtools` MCP ile Lighthouse Accessibility çalıştır,
**skor ≥ 95** olmadan görev kapanmaz.

---

## 13. ANTI-SLOP YASAK LİSTESİ

> Bu bölüm, üretilen UI'ın "AI yapmış" gibi görünmesinin **somut
> nedenlerini** listeler. Her çıktıdan önce buradan geçilir.

### 13.1 Renk

- ❌ Mor→pembe gradient (`#6366F1 → #A855F7 → #EC4899`) — en belirgin tell.
- ❌ Kart başlıklarında, butonlarda, ikonlarda gradient.
- ❌ Krem zemin (`#F4F1EA`) + terracotta aksan (`#D97757`) — yaygın AI default.
- ❌ Saf siyah zemin + neon yeşil/asit aksan.
- ❌ 3'ten fazla aksan rengi.
- ❌ Glassmorphism / `backdrop-blur` her yerde.
- ✅ Tek aksan rengi, nötr gri skalası, durum renkleri.

### 13.2 Tipografi

- ❌ `Poppins`, `Montserrat`, düz `Inter` üçlüsü.
- ❌ Gradient metin (`bg-clip-text`).
- ❌ Uppercase buton metni.
- ❌ Aynı ekranda 5'ten fazla font boyutu.
- ❌ Büyük başlıkta `letter-spacing: normal`.
- ❌ `font-weight: 300` UI metninde.

### 13.3 Layout

- ❌ Her şeyin ortalanması (özellikle sola yaslı olması gereken veri).
- ❌ Eşit olmayan kart yükseklikleri (`items-stretch` kullan).
- ❌ Optik hizasızlık: ikon ile metin baseline'ının kaymış olması.
- ❌ `space-y-4` ile her şeye aynı boşluk — hiyerarşi boşlukla anlatılır.
- ❌ Nefes almayan yoğunluk **veya** amaçsız devasa boşluk.
- ❌ 3 sütunlu "özellik kartları" (🚀 Hızlı / 🔒 Güvenli / ⚡ Kolay).

### 13.4 İçerik & metin

- ❌ Lorem ipsum. **Her zaman gerçekçi Türkçe veri kullan** (gerçek şirket
  adları, gerçek birimler, gerçekçi tarihler).
- ❌ Emoji ikon olarak (🚀📊✨). `lucide` kullan.
- ❌ "Kolayca", "sorunsuz", "güçlü", "devrim niteliğinde" gibi pazarlama dolgusu.
- ❌ "Submit", "Data", "Error occurred" gibi sistem dili.
- ❌ `$1,234.56` biçimi Türkçe arayüzde — `₺1.234,56` olmalı.

### 13.5 Bileşen

- ❌ Her karta gölge.
- ❌ Aynı ekranda 3 farklı radius değeri.
- ❌ Aynı ekranda 2 farklı ikon seti.
- ❌ Aynı ekranda 2 primary buton.
- ❌ Zebra şeritli tablo.
- ❌ Her yerde spinner.
- ❌ Değiştirilmemiş shadcn default'ları (`slate` palet + `rounded-md` + hepsi).

### 13.6 Sinyal cümlesi

Bir tasarım kararı verdiğinde kendine sor:

> **"Bu kararı bu proje için mi verdim, yoksa herhangi bir dashboard için
> de aynı kararı verir miydim?"**

İkincisiyse — karar değil, default. Değiştir.

---

## 14. GÖRSEL DOĞRULAMA DÖNGÜSÜ

> **Bu bölüm atlanamaz. Ajan kendi çıktısını görmeden görev bitmez.**

### 14.1 Zorunlu döngü

```
1. Kodu yaz
2. Dev sunucusunun ayakta olduğunu doğrula (localhost:3000)
3. chrome-devtools MCP → navigate_page → take_screenshot
   → design/shots/<sayfa>-desktop-1440.png
4. Ekran görüntüsünü GERÇEKTEN İNCELE ve şunları yaz:
   - "Neyi iyi yapmışım?" (2 madde)
   - "Neyi kötü yapmışım?" (en az 3 madde)
5. design/refs/ içindeki referansla YAN YANA karşılaştır:
   - Boşluk ritmi tutuyor mu?
   - Tipografik kontrast referanstaki kadar güçlü mü?
   - Renk sayısı referanstakinden fazla mı?
6. Bölüm 13 yasak listesini madde madde geç
7. Düzelt → 3'e dön
8. En az 2 tur döngü tamamlanmadan "bitti" deme
```

### 14.2 Zorunlu viewport'lar

| Viewport | Boyut | Kontrol edilen |
|----------|-------|----------------|
| Mobil | 375 × 812 | Sidebar drawer'a döndü mü, tablo kart oldu mu, taşma var mı |
| Tablet | 768 × 1024 | Grid 2 sütuna düştü mü |
| Masaüstü | 1440 × 900 | Ana tasarım |
| Geniş | 1920 × 1080 | İçerik 1440'ta sabitlendi mi, sağda boşluk çirkin mi |

Her viewport için ayrı screenshot ve ayrı kritik.

### 14.3 Ek kontroller (chrome-devtools MCP)

```
- list_console_messages   → 0 hata, 0 React key uyarısı olmalı
- Koyu tema toggle → screenshot → aynı kritik
- Tab tuşuyla gezinme → focus halkası her adımda görünür mü
- Lighthouse: Performance / Accessibility / Best Practices
```

### 14.4 Kritik yazma formatı

Ajan her turda `design/decisions.md` dosyasına ekler:

```md
## 2026-07-25 · /uretim/panel · tur 2

**İyi:** KPI kartlarının delta hizalaması tutarlı; tablo başlığı sticky çalışıyor.

**Kötü:**
1. Grafik kartı ile tablo kartı arasında 20px boşluk var — token değil, 24 olmalı.
2. Sidebar aktif öğede hem zemin hem sol çubuk var — Bölüm 7.2'ye aykırı, çubuğu kaldır.
3. Durum rozetleri pill (999px) — Bölüm 8.4 gereği 6px olmalı.
4. 1920px'te içerik sağa doğru esniyor, max-w yok.

**Uygulanan:** 1,2,3,4 düzeltildi. Tur 3'te tekrar bakılacak.
```

Bu dosya bir sonraki oturumda okunur — ajan aynı hatayı iki kez yapmaz.

---

## 15. DEFINITION OF DONE

Bir UI görevi ancak **tüm maddeler** işaretliyse kapanır.

**Token & tutarlılık**
- [ ] Kodda hiç ham hex yok (`grep -rE "#[0-9a-fA-F]{6}" src/` → sadece token dosyası)
- [ ] Kodda spacing için ham px yok
- [ ] Tek ikon seti, tek radius karakteri, tek aksan rengi

**Yapı**
- [ ] Bölüm 9'daki sayfa iskeleti uygulandı
- [ ] Sayfada tek primary buton var
- [ ] `birincil_is` (BRIEF) ekranın en belirgin öğesi

**Durumlar**
- [ ] Boş durum kodlandı (eylem butonlu)
- [ ] Filtre-boş durumu ayrı kodlandı
- [ ] Yükleniyor durumu skeleton ile kodlandı
- [ ] Hata durumu "tekrar dene" ile kodlandı
- [ ] Uzun metin / çok uzun isim taşma testi yapıldı (40+ karakter)

**Responsive**
- [ ] 375 / 768 / 1440 / 1920 screenshot alındı ve incelendi
- [ ] Yatay kaydırma yok (mobil dahil)

**Erişilebilirlik**
- [ ] Lighthouse Accessibility ≥ 95
- [ ] Tab ile tüm sayfa gezilebildi, focus her yerde görünür
- [ ] Kontrast oranları geçti

**Kalite**
- [ ] Console 0 hata / 0 uyarı
- [ ] Bölüm 13 yasak listesi madde madde geçildi
- [ ] En az 2 tur görsel kritik döngüsü yapıldı
- [ ] `design/decisions.md` güncellendi
- [ ] Türkçe metinler Ek B kurallarına uygun

---

## 16. PROMPT KÜTÜPHANESİ

### 16.1 Yeni sayfa üretimi (ana prompt)

```
DESIGN.md dosyasını baştan sona oku, sonra design/refs/ klasöründeki
tüm görselleri ve README.md notlarını incele.

GÖREV: <sayfa adı> sayfasını tasarla ve kodla.
Sayfanın tek işi: <birincil_is>
Kullanıcı: <kim, hangi ortamda>

ÇALIŞMA SIRASI — bu sırayı bozma:

1. PLAN (kod yazma):
   - Bu sayfa hangi soruyu 5 saniyede cevaplamalı?
   - Bilgi hiyerarşisi: 1. seviye / 2. seviye / 3. seviye ne?
   - ASCII wireframe çiz.
   - Kullanılacak token'ları listele (renk, spacing, tipografi).
   - "Signature": bu sayfayı akılda kalıcı yapacak TEK öğe ne?
   - Bu planı bana göster ve ONAY BEKLE.

2. ÖZ-ELEŞTİRİ (onaydan önce, kendin yap):
   Planındaki her kararı sor: "Bu kararı herhangi bir dashboard için
   de verir miydim?" Evet ise o kararı değiştir ve neyi neden
   değiştirdiğini yaz.

3. KOD:
   - shadcn MCP ile bileşen YAPISINI al, STİLİNİ DESIGN.md'den ver.
   - Gerçekçi Türkçe mock veri kullan (lorem ipsum yasak).
   - 5 durumu da kodla: dolu / boş / filtre-boş / yükleniyor / hata.

4. GÖRSEL DOĞRULAMA (Bölüm 14):
   - chrome-devtools MCP ile 375/768/1440/1920 screenshot al.
   - Her birini incele, en az 3 kusur bul, yaz.
   - Bölüm 13 yasak listesini madde madde geç.
   - Düzelt, tekrar screenshot al. EN AZ 2 TUR.

5. Bölüm 15 DoD kontrol listesini doldur ve bana göster.

Kırmızı çizgiler: <BRIEF'ten>
```

### 16.2 Mevcut ekranı düzeltme

```
DESIGN.md oku. <dosya yolu> içindeki ekranı chrome-devtools MCP ile
1440x900'de aç ve screenshot al.

Bu ekranı DESIGN.md'ye göre DENETLE, henüz düzeltme:
- Bölüm 5-8 (token, tipografi, bileşen spec) ihlalleri
- Bölüm 13 anti-slop ihlalleri
- Bölüm 10 eksik durumlar
- Bölüm 12 erişilebilirlik ihlalleri

Her bulgu için: [önem: kritik/orta/düşük] · [dosya:satır] · [ihlal] ·
[önerilen düzeltme]

Bulguları önem sırasına göre listele ve ONAY BEKLE.
Sonra sadece onayladıklarımı, en kritikten başlayarak düzelt.
Her 3 düzeltmede bir screenshot al ve ilerlemeyi göster.
```

### 16.3 Token sistemi kurulumu (proje başında bir kez)

```
DESIGN.md Bölüm 4'teki BRIEF'i ve design/refs/ görsellerini oku.

frontend-design ve design-system skill'lerini kullanarak bu proje için
Bölüm 5 ve 6'daki tüm boş token'ları doldur.

Kurallar:
- Palet 4-6 isimlendirilmiş hex ile TARİF EDİLİR, önce prose olarak anlat.
- Bölüm 13.1'deki yasaklı palet ailelerine girme.
- Font seçiminde Türkçe glif kontrolü yap (İ ı Ğ ğ Ş ş).
- Her renk için WCAG kontrast oranını hesapla ve tabloda göster.
- Koyu tema varyantını da üret.

Önce 3 farklı yön öner (her biri 2 cümle + palet + font eşleşmesi).
Ben birini seçeyim, sonra kodla:
- app/globals.css içinde @theme bloğu
- design/decisions.md'ye "neden bu palet" gerekçesi
```

### 16.4 Bileşen üretimi

```
DESIGN.md Bölüm 5-8 oku.

<bileşen adı> bileşenini üret.
Referans: DESIGN.md Bölüm <8.x> spesifikasyonu — birebir uy.

- shadcn MCP ile varsa mevcut bileşeni bul, YAPISINI temel al.
- Tüm varyantları (Bölüm 8.x tablosundaki) ve tüm durumları
  (default/hover/focus/active/disabled/loading) implement et.
- TypeScript prop tipleri eksiksiz, JSDoc ile açıkla.
- Aynı dosyada bir demo/showcase bölümü yaz.
- chrome-devtools ile screenshot al, tüm varyantları tek ekranda göster.
```

### 16.5 Slash komutu: `/ui-audit`

`.claude/commands/ui-audit.md` dosyasına kaydet:

```md
DESIGN.md dosyasını oku ve $ARGUMENTS ile belirtilen sayfayı/bileşeni
Bölüm 15 Definition of Done listesine göre denetle.

chrome-devtools MCP ile 375, 768, 1440, 1920 genişliklerinde screenshot al.
Console mesajlarını listele. Lighthouse Accessibility çalıştır.

Çıktı formatı: DoD listesinin her maddesi için ✅ / ❌ + ❌ olanlar için
tek satır gerekçe ve dosya:satır referansı.

Sonunda: "Bu ekranın en zayıf 3 yanı" başlığı altında somut düzeltmeler öner.
Düzeltme YAPMA, sadece raporla.
```

### 16.6 Slash komutu: `/ui-build`

`.claude/commands/ui-build.md` dosyasına, 16.1'deki ana prompt'u
`$ARGUMENTS` ile parametreleştirerek kaydet.

---

## 17. REFERANS KAYNAKLARI

> **Kullanım kuralı:** Bu siteler *ilham* içindir, *kopyalamak* için
> değil. Bir tasarımı beğendiğinde ekran görüntüsünü `design/refs/`
> içine at ve **neyi** aldığını yaz (Bölüm 4).

### 17.1 Bileşen & kod (doğrudan projeye girer)

| Kaynak | Ne için | Not |
|--------|---------|-----|
| [ui.shadcn.com](https://ui.shadcn.com/) | Temel bileşen yapısı | **Default stilini asla olduğu gibi kullanma** |
| [21st.dev](https://21st.dev/) | Hazır React bileşenleri, MCP'si var | En verimli kaynak; token'a uyarla |
| [magicui.design](https://magicui.design/) | Animasyonlu efekt bileşenleri | Dashboard'da değil, landing'de |
| [ui.aceternity.com](https://ui.aceternity.com/) | Gösterişli efektler | Ölçülü kullan, kolay ucuzlaşır |
| [reactbits.dev](https://reactbits.dev/) | Küçük etkileşim parçaları | |
| [motion-primitives.com](https://motion-primitives.com/) | Framer Motion desenleri | Bölüm 11 sürelerine uyarla |
| [ui-layouts.com](https://www.ui-layouts.com/) | Layout blokları | |
| [fancycomponents.dev](https://www.fancycomponents.dev/) | Deneysel bileşenler | Nadiren; "signature" öğe için |
| [originui-ng.com](https://www.originui-ng.com/) | Form/input varyantları | Form ağırlıklı ekranlarda faydalı |
| [uiverse.io](https://uiverse.io/) | CSS mikro-bileşenler | Kalite değişken, seçici ol |

### 17.2 Ürün arayüzü referansı (dashboard/SaaS — **en değerli grup**)

| Kaynak | Ne için |
|--------|---------|
| [refero.design](https://refero.design/) | **Gerçek ürün ekranları, akış bazlı.** Dashboard işi için en iyi kaynak |
| [boardui.com](https://www.boardui.com/) | Dashboard/panel odaklı derleme |
| [mobbin.com](https://mobbin.com/) | Akış bazlı (onboarding, ödeme, boş durum) — mobil ağırlıklı |
| [layers.to](https://layers.to/explore) | Tasarımcı işleri, UI detayı |
| [recent.design](https://recent.design/) | Güncel ürün tasarımı |
| [jiro.build](https://jiro.build/) | Ürün arayüzü örnekleri |

### 17.3 Landing / pazarlama sayfası

| Kaynak | Ne için |
|--------|---------|
| [saaspo.com](https://saaspo.com/) | SaaS landing, bölüm bazlı filtreleme |
| [saaslandingpage.com](https://saaslandingpage.com/) | SaaS landing arşivi |
| [land-book.com](https://land-book.com/) | Geniş landing galerisi |
| [lapa.ninja](https://www.lapa.ninja/) | Landing + renk paleti bilgisi |
| [onepagelove.com](https://onepagelove.com/) | Tek sayfa siteler |
| [relume.ai](https://www.relume.ai/) | Sitemap + wireframe üretimi (yapı için) |
| [subframe.com](https://www.subframe.com/) | Görsel editör + kod çıktısı |
| [billow.so](https://www.billow.so/) | SaaS örneği |

### 17.4 Üst düzey estetik & ödüllü işler

| Kaynak | Ne için | Uyarı |
|--------|---------|-------|
| [siteinspire.com](https://www.siteinspire.com/) | **Küratörlü, yüksek kalite** | Dashboard için değil, estetik kalibrasyon için |
| [awwwards.com](https://www.awwwards.com/) | Ödüllü siteler | Çoğu ürün arayüzü için fazla gösterişli |
| [thefwa.com](https://thefwa.com/) | Deneysel web | Aynı uyarı |
| [cssdesignawards.com](https://www.cssdesignawards.com/) | Ödüllü işler | |
| [httpster.net](https://httpster.net/) | Trend takibi | |
| [dribbble.com](https://dribbble.com/) | Görsel ilham | ⚠️ **Çoğu çalışmayan konsept.** Dribbble'dan *layout* alma, sadece *renk/tipografi* fikri al. Dribbble taklidi = kullanılamaz arayüz. |
| [monet.design](https://www.monet.design/) | Renk/palet | |

### 17.5 Kullanım disiplini

1. Bir projede **en fazla 3 referans** kullan. Fazlası tutarsızlık üretir.
2. Referansı ekran görüntüsü olarak `design/refs/`'e **indir** — link verme,
   ajan siteyi göremez.
3. Her referans için "neyi alıyorum" notu zorunlu.
4. Dribbble/Awwwards işlerini **dashboard'a taşıma**. O işler 1 ekran
   için tasarlanmıştır, 40 ekranlık bir üründe çöker.

---

## EK A: TAILWIND'SİZ / ANT DESIGN PROJELERİ

FabrikaOS gibi antd tabanlı projelerde bu dosyanın tamamı geçerlidir,
yalnızca uygulama katmanı değişir.

### A.1 Token'ları antd'ye bağla

```ts
// theme/tokens.ts
export const theme = {
  token: {
    colorPrimary:      'var(--color-accent)',
    colorBgLayout:     'var(--color-bg)',
    colorBgContainer:  'var(--color-surface)',
    colorBorder:       'var(--color-border)',
    colorBorderSecondary: 'var(--color-border)',
    colorText:         'var(--color-fg)',
    colorTextSecondary:'var(--color-fg-muted)',
    colorTextTertiary: 'var(--color-fg-subtle)',
    colorSuccess:      'var(--color-success)',
    colorWarning:      'var(--color-warning)',
    colorError:        'var(--color-danger)',
    borderRadius:      8,
    borderRadiusLG:    12,
    fontFamily:        'var(--font-body)',
    fontSize:          14,
    controlHeight:     36,
    boxShadow:         'var(--shadow-sm)',
    boxShadowSecondary:'var(--shadow-md)',
  },
  components: {
    Card:   { paddingLG: 20, borderRadiusLG: 12, boxShadow: 'none' },
    Table:  { headerBg: 'var(--color-surface-sunken)',
              rowHoverBg: 'var(--color-surface-sunken)',
              cellPaddingBlock: 12, headerSplitColor: 'transparent' },
    Button: { primaryShadow: 'none', defaultShadow: 'none' },
    Layout: { siderBg: 'var(--color-surface)', headerBg: 'var(--color-surface)' },
    Menu:   { itemHeight: 36, itemBorderRadius: 8,
              itemSelectedBg: 'var(--color-surface-sunken)',
              itemSelectedColor: 'var(--color-fg)' },
  },
};
```

### A.2 antd'de mutlaka kapatılacaklar

- `Card` gölgesi → `boxShadow: 'none'` + 1px border
- `Table` başlık ayırıcı çizgisi (`headerSplitColor: 'transparent'`)
- `Button` gölgeleri (antd 5 default'unda var, ucuz durur)
- Varsayılan mavi (`#1677FF`) — projenin aksan rengiyle değiştir
- `Table` `bordered` prop'u — kullanma, tam ızgaralı tablo ağır durur

### A.3 antd'de dikkat

- `Table`'da `size="middle"` kullan, `large` çok gevşek.
- `Statistic` bileşeni Bölüm 8.1 anatomisine uymaz — kendi KPI kartını yaz.
- antd ikon seti ile lucide'ı **karıştırma**; birini seç.
- Türkçe locale: `<ConfigProvider locale={trTR}>` + `dayjs.locale('tr')`.

---

## EK B: TÜRKÇE ARAYÜZ KURALLARI

### B.1 Biçimlendirme

| Tür | Doğru | Yanlış |
|-----|-------|--------|
| Para | `₺1.234,56` · `1.234,56 ₺` | `$1,234.56` |
| Sayı | `184.392` | `184,392` |
| Yüzde | `%12,4` (işaret **önde**) | `12.4%` |
| Tarih | `25.07.2026` / `25 Tem 2026` | `07/25/2026` |
| Saat | `14:32` (24 saat) | `2:32 PM` |
| Büyük sayı | `1,2 mn` · `184 b` | `1.2M` · `184K` |

`Intl.NumberFormat('tr-TR')` ve `Intl.DateTimeFormat('tr-TR')` kullan,
elle biçimlendirme yapma.

### B.2 Metin tonu

- **Cümle düzeni:** Başlıklarda ilk harf büyük, gerisi küçük.
  ✅ "Yeni tedarikçi ekle" · ❌ "Yeni Tedarikçi Ekle"
- **Fiil kipi:** Butonlar emir kipinde: "Kaydet", "Sil", "Dışa aktar".
- **Tutarlılık:** Bir eylem baştan sona aynı adı taşır.
  Buton "Yayımla" → onay "Yayımlansın mı?" → toast "Yayımlandı".
- **Sistem dili yasak:** "webhook yapılandırması" değil "bildirimler";
  "null değer" değil "boş"; "senkronizasyon hatası" değil
  "değişiklikler kaydedilemedi".
- **Hata mesajları özür dilemez, çözüm söyler.**
  ❌ "Üzgünüz, bir hata oluştu."
  ✅ "Dosya yüklenemedi. En fazla 10 MB olmalı."

### B.3 Teknik tuzaklar

- **`text-transform: uppercase` Türkçe'de bozuktur.** `i` → `I` yapar,
  `İ` olması gerekir. Küçük etiketlerde uppercase istiyorsan CSS ile
  değil, metni **elle büyük yaz** veya `text-transform` yerine
  `font-variant: small-caps` düşün. (CSS `text-transform` `lang="tr"`
  ile bazı tarayıcılarda doğru çalışır ama güvenme, test et.)
- **Sıralama:** `localeCompare('tr')` kullan — `ç ğ ı i ö ş ü` sırası
  varsayılan sıralamada yanlış çıkar.
- **Metin uzunluğu:** Türkçe metin İngilizce'den **~%20 uzundur.**
  Buton ve etiket genişliklerini sabitleme, `min-width` ver.
  ("Save" 4 karakter, "Kaydet" 6; "Export" 6, "Dışa aktar" 10.)
- **Ekler:** Değişken içeren metinlerde ek uyumu kırılır.
  ❌ `` `${count} kayıt bulundu` `` → sayı 1 ise sorun yok ama
  ❌ `` `${name}'in siparişi` `` → sesli/sessiz uyumu bozulur.
  ✅ Ek gerektirmeyen kalıp kur: `"Sipariş sahibi: {name}"`.
- i18n kullanıyorsan (i18next) tüm metinler anahtar üzerinden geçer,
  JSX içinde çıplak Türkçe string kalmaz.

---

## SON SÖZ — AJANA NOT

Bu dosyayı okuyup "anladım" deyip default'a dönmek en yaygın hatadır.
Somut kontrol: kod yazmadan önce **Bölüm 5'teki token değerlerini
gerçekten okudun mu, yoksa `slate-200` mu yazdın?** İkincisiyse
dosyayı okumamışsın demektir.

Ve en önemlisi: **çıktını gözünle görmeden bitirme.** (Bölüm 14)
