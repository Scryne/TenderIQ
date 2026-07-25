# BAŞLANGIÇ — DESIGN.md'yi bir projede kullanma

> **Bu dosya senin için. `DESIGN.md` ajan için.**
> Bu dosyayı projeye koymana bile gerek yok — istersen sadece bir kez oku,
> istersen `docs/` altına at.
>
> Toplam kurulum süresi: ilk projede ~30 dk, sonrakilerde ~5 dk.

---

## ⚡ ÇOK KISA ÖZET

```
1. DESIGN.md'yi proje köküne at
2. CLAUDE.md'ye 4 satır ekle
3. .mcp.json oluştur (3 MCP)
4. design/refs/ klasörüne 5-8 referans ekran görüntüsü at + not yaz
5. Claude Code'da PROMPT 1'i çalıştır (BRIEF)
6. PROMPT 2'yi çalıştır (token sistemi)
7. Her sayfa için PROMPT 3'ü çalıştır
```

**Adım 4'ü atlarsan geri kalanı işe yaramaz.** Kalitenin en büyük tek
kaynağı orası.

---

## ADIM 1 — Dosya yapısını kur (2 dk)

Proje kökünde:

```bash
mkdir -p design/refs design/shots .claude/skills .claude/commands
touch design/decisions.md
```

`DESIGN.md`'yi proje köküne kopyala. Sonuç:

```
proje/
├── CLAUDE.md
├── DESIGN.md          ← attığın dosya
├── .mcp.json          ← Adım 2'de oluşacak
├── .claude/
│   ├── skills/
│   └── commands/
└── design/
    ├── refs/          ← Adım 4 (EN ÖNEMLİ)
    ├── shots/         ← ajan buraya screenshot atacak
    └── decisions.md   ← ajan buraya kritik yazacak
```

### CLAUDE.md'ye ekle

Yoksa oluştur, varsa **en üste** ekle:

```md
## Frontend kuralları — ATLANAMAZ

UI/frontend içeren HER görevde, kod yazmadan önce `DESIGN.md` dosyasını
baştan sona oku ve `design/refs/README.md` içindeki referans notlarını incele.

- DESIGN.md Bölüm 13 (Anti-slop) ve Bölüm 14 (Görsel doğrulama döngüsü)
  atlanamaz.
- Görev, Bölüm 15'teki Definition of Done listesi doldurulmadan
  "bitti" sayılmaz.
- Her UI görevinin sonunda `design/decisions.md` güncellenir.
```

`.gitignore`'a ekle:

```
design/shots/
.env.claude
```

---

## ADIM 2 — MCP'leri kur (5 dk)

Proje kökünde `.mcp.json` oluştur:

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

**API anahtarı:**

```bash
echo 'export MAGIC_21ST_API_KEY=senin_keyin' >> .env.claude
source .env.claude
```

Key'i https://21st.dev/magic/console adresinden al. `.env.claude` zaten
`.gitignore`'da.

### Doğrula

Claude Code'u yeniden başlat, sonra:

```
/mcp
```

Üçü de **Connected** görünmeli. `chrome-devtools` bağlanmıyorsa Node 22+
gerekiyor:

```bash
node -v   # v22 veya üstü olmalı
```

> **En kritik MCP `chrome-devtools`.** Diğer ikisi olmasa da olur.
> Bu olmadan ajan kendi çıktısını göremez ve hizasız/taşan layout üretip
> "tamamdır" der.

---

## ADIM 3 — Skill'leri kur (5 dk)

Her skill `.claude/skills/<isim>/SKILL.md` olarak konur.

**Kur (7 tane):**

```
frontend-design
design-system
enterprise-dashboard-design
dashboard-ux
dataviz
micro-interactions
accessibility-wcag
```

**Proje tipine göre 1-3 ek:**

| Proje | Ekle |
|-------|------|
| Landing sayfası var | `design-taste-frontend`, `high-end-visual-design` |
| Abonelik/plan/limit ekranları | `saas-design` |
| Ağır animasyon | `framer-motion` |
| Mevcut çirkin projeyi düzeltme | `redesign-existing-projects` |
| Türkçe metin kalitesi önemli | `ux-writing` |

**KURMA:** `impeccable`, `ui-ux-pro-max`, `design-inspiration`,
`gpt-taste`, `emil-design-eng`, `ui-styling`, `color-system`,
`typography`, `ux-laws`, `magicui-patterns`, `aceternity-ui-patterns`,
`reactbits-patterns`, `minimalist-ui`, `industrial-brutalist-ui`.

Bunlar çekirdek setle veya DESIGN.md'nin kendisiyle çakışıyor. **Aynı
anda 10'dan fazla design skill aktifse kalite düşer.**

### Slash komutlarını kur

`.claude/commands/ui-audit.md`:

```md
DESIGN.md dosyasını oku ve $ARGUMENTS ile belirtilen sayfayı/bileşeni
Bölüm 15 Definition of Done listesine göre denetle.

chrome-devtools MCP ile 375, 768, 1440, 1920 genişliklerinde screenshot al.
Console mesajlarını listele. Lighthouse Accessibility çalıştır.

Çıktı: DoD listesinin her maddesi için ✅ / ❌ + ❌ olanlar için tek satır
gerekçe ve dosya:satır referansı.

Sonunda "Bu ekranın en zayıf 3 yanı" başlığı altında somut düzeltmeler öner.
DÜZELTME YAPMA, sadece raporla.
```

`.claude/commands/ui-fix.md`:

```md
DESIGN.md oku. $ARGUMENTS ekranını chrome-devtools ile 1440x900'de aç,
screenshot al.

DESIGN.md Bölüm 5-8, 10, 12, 13'e göre denetle. Bulguları önem sırasına
diz ve ONAY BEKLE. Sonra sadece onayladıklarımı, en kritikten başlayarak
düzelt. Her 3 düzeltmede bir screenshot al ve göster.
```

---

## ADIM 4 — Referansları hazırla (10 dk) ← **EN ÖNEMLİ ADIM**

> Bu adımı atlarsan geri kalan her şey boşa gider.
> Ajan "güzel"i tarif edemez, **taklit** edebilir.

### 4.1 Görselleri indir

`design/refs/` klasörüne **5-8 ekran görüntüsü** koy. Kaynaklar
DESIGN.md Bölüm 17'de. Dashboard işi için en verimli üçü:

- **refero.design** — gerçek ürün ekranları, akış bazlı
- **boardui.com** — dashboard odaklı
- **mobbin.com** — akış bazlı (onboarding, boş durum, ödeme)

**Link verme, dosya indir.** Ajan siteyi göremez.

### 4.2 `design/refs/README.md` yaz — zorunlu

Her referans için **neyi aldığını** yaz. "Bu güzel" yetmez:

```md
# Referans notları

- `01-linear-sidebar.png`
  ALIYORUM: sidebar grup başlığı ritmi, nav öğesi yüksekliği, aktif durum.
  ALMIYORUM: renk paleti, tipografi.

- `02-stripe-kpi.png`
  ALIYORUM: KPI kartı anatomisi (etiket→değer→delta), sparkline yerleşimi,
  para biriminin sayıdan küçük olması.
  ALMIYORUM: layout, mor tonlar.

- `03-helix-dark.png`
  ALIYORUM: koyu tema yüzey katmanları, veri yoğunluğu, taralı grafik dolgusu.
  ALMIYORUM: 6 sütunlu grid.

- `04-saleignite-table.png`
  ALIYORUM: tablo satır anatomisi, iki satırlı kullanıcı hücresi,
  rol/durum rozeti biçimi, seçili satır vurgusu.
  ALMIYORUM: KPI kartlarının sadeliği (bizde delta gerekli).

## Genel yön
Sakin, hassas, veri yoğun. Gösterişli efekt yok. Referanslardan sadece
YAPI ve RİTİM alınacak; renk ve tipografi bu projeye özel belirlenecek.
```

**Kritik:** 3'ten fazla referanstan *layout* alma. Yoksa Frankenstein çıkar.
Layout için 1-2 referans, geri kalanı detay (kart, tablo, rozet) için.

---

## ADIM 5 — BRIEF'i doldur

### PROMPT 1 — kopyala yapıştır

```
DESIGN.md dosyasını oku. Bölüm 4'teki PROJE BRIEF şablonunu bu proje için
doldurmam gerekiyor.

Önce projeyi anla: package.json, README, mevcut sayfa/route yapısı,
varsa mevcut UI kodunu incele.

Sonra bana Bölüm 4'teki her alan için tek tek soru sor — hepsini birden
sorma, sırayla git ve cevabımı aldıktan sonra bir sonrakine geç.
Tahmin edebildiğin alanları (stack, dil, ikon seti) doldurup bana
"bunu şöyle varsaydım, doğru mu?" diye onaylat.

Özellikle şu üçünü zorla, çünkü en kritik olanlar:
- birincil_is: bu ürünün ana ekranı 5 saniyede HANGİ tek soruyu cevaplamalı?
- duygu / karsit_duygu: 3'er sıfat
- kirmizi_cizgiler

Bittiğinde doldurulmuş BRIEF'i DESIGN.md Bölüm 4'ün içine yaz
(dosyayı güncelle, ayrı dosya açma).
```

Bu prompt biter bitmez DESIGN.md Bölüm 4 dolu olacak. **Bir daha
doldurmana gerek yok.**

---

## ADIM 6 — Token sistemini kur (proje başına bir kez)

### PROMPT 2 — kopyala yapıştır

```
DESIGN.md Bölüm 4'teki doldurulmuş BRIEF'i ve design/refs/ klasöründeki
tüm görselleri + README.md notlarını oku.

frontend-design ve design-system skill'lerini kullanarak bu proje için
DESIGN.md Bölüm 5 (renk, spacing, radius, gölge) ve Bölüm 6 (tipografi)
içindeki BOŞ token'ları doldur.

ÖNCE: 3 farklı görsel yön öner. Her yön için:
- 2 cümlelik karakter tarifi
- 4-6 isimlendirilmiş hex (palet)
- display + body + mono font eşleşmesi
- neden bu projeye uygun olduğu (BRIEF'teki duygu/kullanıcı/ortama bağla)

KISITLAR:
- DESIGN.md Bölüm 13.1 ve 13.2'deki yasaklı palet ve font ailelerine girme.
- Font seçiminde Türkçe glif kontrolü yap: İ ı Ğ ğ Ş ş Ç ç Ö ö Ü ü.
  Eksik olan fontu önerme.
- Her yön için "bu kararı herhangi bir SaaS için de verir miydim?"
  sorusunu sor; cevap evet ise o yönü değiştir ve neyi değiştirdiğini yaz.

Ben bir yön seçeyim. ONAY BEKLE.

Seçimden sonra:
1. Tüm token'ları hesapla; her metin/zemin çifti için WCAG kontrast
   oranını tabloda göster (hedef: metin 4.5:1, UI 3:1).
2. Koyu tema varyantını da üret (Bölüm 5.2 kurallarına göre).
3. app/globals.css içine @theme bloğunu yaz.
4. design/decisions.md'ye "neden bu palet ve bu fontlar" gerekçesini yaz.
5. Tüm token'ları tek ekranda gösteren bir /design-tokens sayfası üret,
   chrome-devtools ile screenshot al, bana göster.
```

Son madde önemli: token sayfasının screenshot'ına bakınca paleti
beğenmezsen **şimdi** değiştirirsin, 20 sayfa kodlandıktan sonra değil.

---

## ADIM 7 — Sayfa üret

### PROMPT 3 — ana prompt, her sayfa için kullan

```
DESIGN.md dosyasını baştan sona oku, design/refs/ görsellerini ve
README.md notlarını incele, design/decisions.md'deki geçmiş kararları oku.

GÖREV: <SAYFA ADI> sayfasını tasarla ve kodla.
Bu sayfanın tek işi: <5 saniyede cevaplanacak soru>
Kullanıcı: <kim, hangi ortamda, ne sıklıkla>

ÇALIŞMA SIRASI — bu sırayı bozma:

═══ 1. PLAN (henüz kod yazma) ═══
- Bu sayfa hangi tek soruyu 5 saniyede cevaplamalı?
- Bilgi hiyerarşisi: 1., 2., 3. seviye ne? Neyi büyük, neyi küçük yapıyorum?
- ASCII wireframe çiz.
- DESIGN.md Bölüm 8'den hangi bileşen spec'lerini kullanacağım? (numara ver)
- Hangi KPI kartı varyantı (Bölüm 8.1.1)? Neden?
- Kullanacağım token'ları listele.
- SIGNATURE: bu sayfayı akılda kalıcı yapacak TEK öğe ne?

═══ 2. ÖZ-ELEŞTİRİ (planı bana göstermeden önce, kendin) ═══
Plandaki her kararı sor: "Bu kararı herhangi bir dashboard için de
verir miydim?" Evet ise o karar bir DEFAULT'tur, bir seçim değil.
Değiştir ve neyi neden değiştirdiğini yaz.

Sonra planı bana göster ve ONAY BEKLE. Onay almadan kod yazma.

═══ 3. KOD ═══
- shadcn MCP ile bileşen YAPISINI al; STİLİNİ DESIGN.md'den ver.
  shadcn default stilini olduğu gibi bırakma.
- Gerçekçi Türkçe mock veri kullan. Lorem ipsum ve "Company A" yasak.
  Gerçek şirket adları, gerçekçi tutarlar (₺ biçimi), gerçek tarihler.
- 5 durumu da kodla: dolu / boş / filtre-boş / yükleniyor / hata.
- Her grafik kartı kendi error boundary'sinde olsun.

═══ 4. GÖRSEL DOĞRULAMA — ATLANAMAZ (DESIGN.md Bölüm 14) ═══
- Dev sunucusunun ayakta olduğunu doğrula.
- chrome-devtools MCP ile 375, 768, 1440, 1920'de screenshot al,
  design/shots/ altına kaydet.
- HER screenshot'ı gerçekten incele. Her biri için:
    "İyi olan 2 şey:" / "Kötü olan EN AZ 3 şey:"
- design/refs/ ile karşılaştır: boşluk ritmi tutuyor mu? tipografik
  kontrast referanstaki kadar güçlü mü? renk sayısı fazla mı?
- DESIGN.md Bölüm 13 yasak listesini madde madde geç.
- Düzelt, tekrar screenshot al. EN AZ 2 TUR yap.
- list_console_messages: 0 hata olmalı.
- Koyu tema varsa onun da screenshot'ını al ve ayrı kritik yaz.

═══ 5. KAPANIŞ ═══
- DESIGN.md Bölüm 15 DoD listesini doldur, bana göster.
- design/decisions.md'ye bu turun kritiklerini yaz.

Kırmızı çizgiler: <BRIEF'ten kopyala>
```

**`<SAYFA ADI>` ve iki satırı doldurmayı unutma.** Gerisi sabit.

### PROMPT 3-kısa — küçük işler için

```
DESIGN.md oku. <bileşen/küçük iş>.
Bölüm 8.<x> spesifikasyonuna birebir uy.
Bitirince chrome-devtools ile screenshot al, Bölüm 13 yasak listesini
geç, en az 1 tur düzeltme yap.
```

---

## ADIM 8 — Denetim

Sayfa bitince veya eski bir ekranı düzeltmek istediğinde:

```
/ui-audit uretim-paneli
```

Sadece rapor verir, düzeltmez. Raporu okuyup neyi düzelteceğine sen karar
ver, sonra:

```
/ui-fix uretim-paneli
```

---

## GÜNLÜK KULLANIM (kurulum bittikten sonra)

| Ne yapıyorsun | Ne yaz |
|---------------|--------|
| Yeni sayfa | PROMPT 3 |
| Yeni bileşen | PROMPT 3-kısa |
| Mevcut ekranı denetle | `/ui-audit <sayfa>` |
| Mevcut ekranı düzelt | `/ui-fix <sayfa>` |
| Renk/font değiştirmek | PROMPT 2 (yeniden) |
| Yeni referans ekledin | `design/refs/README.md`'yi güncelle, ajana "refs güncellendi, oku" de |

---

## SIK YAPILAN 6 HATA

**1. `design/refs/` boş bırakmak**
En büyük hata. Ajanın elinde referans yoksa istatistiksel ortalamayı
üretir — yani jenerik AI tasarımı. Kalitenin ~%40'ı burada.

**2. "Neyi alıyorum" notu yazmamak**
5 referans, not yok → ajan hepsinden bir şey karıştırır → Frankenstein.
Her referans için 2 satır not, 1 dakikan gider, kaliteyi ikiye katlar.

**3. Plan aşamasını atlatmak**
"Hemen kodla" dersen ajan default'a kayar. Plan → onay → kod sırası
bu playbook'un en değerli kısmı. Planı okumak 30 saniye, kötü kodu
düzeltmek 30 dakika.

**4. Screenshot döngüsünü atlatmak**
"Tamamdır, bitti" diyen ama ekranı hiç görmemiş ajan, hizasız ve taşan
layout teslim eder ve bunu bilmez. Bölüm 14 pazarlık konusu değil.

**5. 20 skill birden kurmak**
Aynı işi yapan skill'ler context'i böler ve ajanın dikkatini dağıtır.
7 çekirdek + 1-3 ek. Bu bir kısıtlama değil, optimizasyon.

**6. BRIEF'i boş bırakmak**
`birincil_is` yazılmamışsa ajan "bu bir dashboard" der ve genel geçer
bir dashboard üretir. Tek cümle yazmak tüm sayfanın hiyerarşisini
belirler.

---

## SORUN GİDERME

**"Ajan DESIGN.md'yi okumuyor gibi"**
CLAUDE.md'deki 4 satırı ekledin mi? Ekledin ve hâlâ okumuyorsa prompt'un
başına açıkça yaz: `Önce DESIGN.md dosyasını oku.`
Kontrol yöntemi: kodda `slate-200` veya çıplak hex varsa okumamış demektir.

**"Screenshot alamıyor"**
- Node 22+ mı? (`node -v`)
- Dev sunucu ayakta mı? Ajana port'u açıkça söyle: `localhost:3000`
- `--autoConnect` yerine Chrome'u kapatıp tekrar dene.

**"shadcn MCP bağlanmıyor"**
`components.json` var mı? Yoksa `npx shadcn@latest init` çalıştır —
shadcn MCP registry'yi bu dosyadan okuyor.

**"Çıktı hâlâ jenerik"**
Sırayla kontrol et:
1. `design/refs/` dolu mu? Notlar yazılı mı?
2. BRIEF'te `duygu` ve `karsit_duygu` dolu mu?
3. Ajan plan aşamasında öz-eleştiri yaptı mı, yoksa direkt mi kodladı?
4. Screenshot döngüsü kaç tur döndü? 2'den azsa döndür.

Hâlâ jenerikse şunu yaz:
```
Ürettiğin ekranın screenshot'ını al ve DESIGN.md Bölüm 13'ü madde madde
geç. Her ihlal için "ihlal + neden yaptım + düzeltme" yaz.
Sonra en az 5 somut değişiklik yap ve tekrar screenshot al.
```

**"Sayfalar birbirine benzemiyor"**
Token'lar kullanılmıyor demektir. Şunu çalıştır:
```
grep -rE "#[0-9a-fA-F]{6}" src/ --include="*.tsx" --include="*.css"
```
Token dosyası dışında sonuç çıkarsa ajana temizlet.

**"Context doluyor / ajan yavaşlıyor"**
Aktif skill sayısını düşür. `design/refs/` içindeki görselleri her
prompt'ta okutma — sadece PROMPT 2 ve PROMPT 3'ün plan aşamasında yeter.

---

## KONTROL LİSTESİ — kurulum tamam mı?

- [ ] `DESIGN.md` proje kökünde
- [ ] `CLAUDE.md`'de 4 satırlık frontend kuralı var
- [ ] `.mcp.json` var, `/mcp` üçünü de Connected gösteriyor
- [ ] `.claude/skills/` altında 7-10 skill var (fazla değil)
- [ ] `.claude/commands/ui-audit.md` ve `ui-fix.md` var
- [ ] `design/refs/` içinde 5-8 görsel **ve** notlu README.md var
- [ ] DESIGN.md Bölüm 4 BRIEF dolu
- [ ] DESIGN.md Bölüm 5-6 token'ları dolu (boş `#____` kalmadı)
- [ ] `/design-tokens` sayfasını gözünle gördün ve beğendin
- [ ] `.gitignore`'da `design/shots/` ve `.env.claude` var

Hepsi ✅ ise PROMPT 3 ile sayfa üretmeye başla.
