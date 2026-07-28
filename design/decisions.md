# Tasarım kararları günlüğü

> DESIGN.md §14.4 biçimi. Her UI turunun sonunda buraya yazılır; bir sonraki
> oturum bunu okur ve aynı hatayı iki kez yapmaz.

---

## 2026-07-25 · kurulum · tur 0

**Bağlam.** Yeni `DESIGN.md` v1.1 sözleşmesi devreye alındı. Önceki arayüz farklı
numaralandırmalı bir protokolle (accent `#0B6E99`, Public Sans + JetBrains Mono,
"Archetype A") üretilmişti; token'lar tutarlıydı ama §13.6 sinyal testinden geçmiyordu
— mavi aksan + nötr gri kararı herhangi bir B2B SaaS için de verilebilirdi.

**Kurulan altyapı.**
- `DESIGN.md` §4 BRIEF kod tabanından dolduruldu (ekran envanteri dahil).
- `CLAUDE.md` frontend kuralları eklendi (dosya yoktu).
- `.claude/commands/`: `ui-audit`, `ui-fix`, `ui-build`.
- `scripts/shoot.mjs`: §14 döngüsünün motoru. `chrome-devtools` MCP kurulu olmadığı
  için apps/web'de zaten bulunan Playwright + Chromium kullanılır; 375/768/1440/1920
  viewport, konsol hatası toplama, yatay taşma ölçümü.

---

## 2026-07-25 · token sistemi · Yön A "MÜREKKEP"

**Seçilen yön ve gerekçesi.** Üç yön sunuldu (Mürekkep / Kadastro / Mühür); Mürekkep
seçildi.

Tez şu: **bu ürün kanıt üretir, öyleyse ekrandaki her doygun renk bir anlam
taşımalı.** Marka rengi diye ayrılmış dekoratif bir mavi yok — birincil eylem rengi
mürekkebin kendisi (`#16171A`). Kroma yalnız dört semantik durumda ve kanıt
vurgusunda bulunur. §13.6 testi: jenerik B2B paleti *her zaman* kromatik bir aksan
seçer; bu karar bu ürüne özgüdür.

Koyu tema aynı tezin inversiyonu: mürekkep kâğıda döner (`--accent: #F4F4F2`).

**Renk kısıtı — neden aksan kromatik olamazdı.** Dört semantik renk sabit
(success/warning/danger/info). Geriye kalan hue alanı ya mor (AI-slop tell, §13.1),
ya teal (info'ya bitişik), ya turuncu/terracotta (§13.1 açıkça yasak). Kromatik bir
aksan seçmek, ya bir yasağa ya bir çakışmaya götürüyordu. Monokrom bu kısıtın
zorlaması değil, ondan çıkan doğru cevap.

**Kontrast — hesaplanmış, tahmin değil (WCAG 2.1):**

| Token | Değer | Zemin | Oran | Hedef |
|---|---|---|---|---|
| `ink-1` | `#16171A` | beyaz | 17,5:1 | 4,5:1 ✓ |
| `ink-2` | `#43454C` | beyaz | 9,6:1 | 4,5:1 ✓ |
| `ink-3` | `#6C6E75` | beyaz | 5,1:1 | 4,5:1 ✓ |
| `ink-3` | `#6C6E75` | canvas | 4,9:1 | 4,5:1 ✓ |
| `border-strong` | `#929397` | beyaz | 3,1:1 | 3:1 ✓ (1.4.11) |
| `success` | `#15803D` | beyaz | 5,0:1 | 4,5:1 ✓ |
| `warning` | `#9A6207` | beyaz | 5,1:1 | 4,5:1 ✓ |
| `danger` | `#B42318` | beyaz | 6,6:1 | 4,5:1 ✓ |
| `info` | `#175CD3` | beyaz | 6,1:1 | 4,5:1 ✓ |
| koyu `ink-2` | `#A7A9AF` | surface | 7,7:1 | 4,5:1 ✓ |
| koyu `ink-3` | `#83858C` | surface-2 | 4,5:1 | 4,5:1 ✓ |
| koyu `border-strong` | `#6D6F75` | surface | 3,6:1 | 3:1 ✓ |

`ink-3` başlangıçta `#8C8E96` idi (3,3:1) — **başarısız**. `#6C6E75`'e koyulaştırıldı.
Koyu temada `#7B7D84` surface-2 üstünde 4,44:1'de kalıyordu → `#83858C`.

**Tipografi.** Instrument Sans (başlık) + Inter Tight (arayüz) + IBM Plex Mono
(koordinat, sayı) — DESIGN.md §6.2'nin "Kurumsal, ciddi" satırı. Üçü de Google
Fonts'ta `latin-ext` + `U+0131` taşıyor; **doğrulandı** (İ ı Ğ ğ Ş ş Ç ç Ö ö Ü ü).
Düz `Inter` bilerek kullanılmadı (§13.2).

**İMZA ÖĞESİ — kaynak şeridi.** Bulguyu kanıtına bağlayan 2px dikey mürekkep çizgisi
+ mono koordinat (`s.42 · 4.3.1`) + kanıt yıkaması. Üç yüzeyde de aynı: bulgu satırı,
panel listesi, PDF vurgusu. **Navigasyonda kullanılmaz** — §7.2 zaten aktif nav
öğesine ray + zemini birlikte vermeyi yasaklıyor, ayrıca motifin anlamı
seyrekliğinden geliyor.

**Spec'ten bilinçli sapmalar.**
1. **§8.1 delta → niteleyici.** Metrik kartının üçüncü satırı karşılaştırma dönemli
   delta ister ("↑%12,4 geçen haftaya göre"). Bu üründe dönemsel karşılaştırma yok —
   ihale kesikli bir olay, zaman serisi değil. Delta uydurmak §13.4'ün yasakladığı
   sahte içerik olurdu. Yerine sayıyı karara bağlayan niteleyici kondu ("2 ihalede",
   "Dönem sonu 01.08.2026"). Kural aynı (bağlamsız sayı değersizdir), bağlamın
   kaynağı değişti.
2. **§9.2 selamlama + tarih aralığı seçici kaldırıldı.** Tarih aralığı kavramı yok;
   selamlama her açılışta okunan boş bir satır. Yerine doğrudan `birincil_is`.
3. **Yeni token `--nav-active`.** §5.1 "yeni token bir karardır" diyor. Koyu temada
   `surface-2` (#1D1E21) sidebar zemini (#141517) üstünde yalnız 9 birim açık; aktif
   nav ayırt edilemiyordu. `surface-2`'yi açmak ise `ink-3`'ün tablo başlıklarındaki
   kontrastını 4,5:1'in altına düşürüyordu. Ayrı bir seçim tonu tek çözümdü.
4. **Ham hex muafiyeti — iki yer.** `global-error.tsx` kök layout çöktüğünde de
   çalışmak zorunda, `globals.css`'in yüklendiği varsayılamaz. `layout.tsx`
   `viewport.themeColor` Next metadata API'si gereği literal ister. İkisi de dosya
   içinde gerekçelendirildi; değerler token'larla birebir aynı.

---

## 2026-07-25 · /design/preview + /design/shell · tur 1

**İyi:** Panel'in bilgi hiyerarşisi çalışıyor — "ELEME RİSKİ" en solda, en büyük
tipografide, altındaki liste o maddeleri kaynak koordinatıyla açıyor. Kaynak şeridi
motifi üç yüzeyde de tutarlı.

**Kötü:**
1. Kabuk önizlemesi katalog kartının içine gömülmüştü; `ShellFrame` kenar çubuğu
   `position: fixed` kullandığı için kabından taştı ve içerikle üst üste bindi.
2. `shadow-md` / `shadow-lg` örnekleri beyaz üstünde beyaz — gölge görünmüyordu.
3. Sıralı dağılım listesi başlıksızdı; ne gösterdiği anlaşılmıyordu.
4. Next dev göstergesi ("N") ekran görüntülerini kirletiyordu.
5. İşleme hattı 5 adımı 1400px'e yayılınca ilerleme çizgisi "boşluk" gibi duruyordu.
6. Reddedilen bulgu satırı `opacity-60` + `line-through` + soluk dekorasyon üst üste
   binince neredeyse okunmuyordu.
7. İhale listesinde UUID'nin ilk 8 hanesi gösteriliyordu — kullanıcıya hiçbir şey
   söylemiyor, kayıt numarası zaten başlıkta.
8. "ANALİZ SÜRÜYOR" ikon kutusu nötrdü; §8.1.2 kutu renginin metriğin anlamıyla
   ilişkili olmasını şart koşuyor.

**Uygulanan:** 1 → `/design/shell` ayrı tam sayfa rotasına alındı ve katalog layout'u
`(catalog)` route group'una taşındı. 2 → gölge örnekleri `surface-2` zemine oturdu.
3 → overline başlık eklendi. 4 → `shoot.mjs` çekim sırasında gizliyor. 5 →
`max-w-xl`. 6 → opaklık yerine `surface-2` zemin + `ink-2` metin. 7 → UUID kaldırıldı,
yerine durum ipucu. 8 → `info` tonu.

---

## 2026-07-25 · tüm ekranlar, açık + koyu · tur 2

**İyi:** Kabuk ölçüleri spec'e uyuyor (sidebar 264px, topbar 56px, aktif öğede ray
YOK). Koyu tema yüzey katmanları gölge değil açıklıkla derinlik veriyor (§5.2).

**Kötü:**
1. `--dark` bayrağı çalışmıyordu: uygulama `defaultTheme="light"` ile sistem
   tercihini bilerek eziyor, Playwright'ın `colorScheme` ayarı yetmiyor.
2. Koyu temada aktif nav öğesi ayırt edilemiyordu (yukarıda `--nav-active`).
3. Koyu `ink-3` surface-2 üstünde 4,44:1 — **WCAG başarısız**.
4. **375px'de yatay taşma: scrollWidth 489 > 375.** Segment sekme listesi sarmıyordu;
   `overflow-x-auto` eklemek yetmedi çünkü `Tabs` kökü esnek bir kapta
   `min-width: auto` ile içerikten küçülmüyordu.
5. **§7.4 ihlali:** ihale tablosu ve üye tablosu 375px'de yatay kaydırmaya
   bırakılmıştı; başlıklar "20…" diye kırpılıyordu.
6. Kota eşiği uyarısı her ölçerde tekrarlıyordu (aynı cümle iki kez).
7. Metrik kartında 11px etiket, 36px ikon kutusunun üst kenarında yüzüyordu (§13.3
   optik hizasızlık).
8. Auth ekranında marka sola yaslı, form geniş sütunda sola yaslıydı — kompozisyon
   dağınıktı.
9. Hero'daki kanıt vurgusu metnin altına kaymıştı; fosforlu kalem değil alt çizgi
   gibi duruyordu.

**Uygulanan:** 1 → `shoot.mjs` `--dark` ile `localStorage.theme` tohumluyor. 2,3 →
token düzeltmeleri. 4 → `Tabs` köküne `min-w-0 max-w-full`, `TabsList`'e
`overflow-x-auto`; kaydırma kontrolün kendi içinde kalıyor, sayfa gövdesi kaymıyor.
5 → her iki tablo `md:` altında kart listesine dönüyor. 6 → `showThresholdNote`
prop'u. 7 → `min-h-9 items-center`. 8 → marka, form ve alt not aynı 400px sütunda
hizalanıp blok olarak ortalandı. 9 → em cinsinden ölçü, metnin üstüne biniyor.

**Kapanış ölçümü:** 5 rota × 4 viewport + 3 rota × 2 viewport koyu tema = **26 çekim,
0 konsol hatası, 0 yatay taşma.** `tsc --noEmit` ve `eslint` temiz.

**Bilinen borç.**
1. `design/refs/` **hâlâ boş** — kalitenin ~%40'ı. §8 ölçüleri yapı ve ritim için
   vekil görevi gördü; görsel karakter kalibrasyonu için gerçek referans gerekli.
2. Ekranların canlı backend ile doğrulaması yapılmadı (Docker ayakta değildi).
   Önizleme kataloğu beş durumu kapsıyor ama gerçek veri hacmi (200+ bulgu, 40
   karakterlik ihale adları) sınanmadı.
3. Lighthouse erişilebilirlik skoru ölçülmedi — `chrome-devtools` MCP kurulunca
   `/ui-audit` ile koşulmalı. Kontrast, focus halkası, `aria-label`, klavye erişimi
   ve renk-tek-başına-bilgi-taşımaz kuralları elle denetlendi ve geçti.
4. `/panel` verisi beş uçtan birleşiyor (incelemeye hazır ilk 5 ihale için N+1).
   Kapalı beta ölçeğinde yeterli; `GET /api/v1/panel` toplu ucu açılmalı.

---

## 2026-07-25 · panel tek uca bağlandı

**Karar.** `/panel` beş uçtan (ihaleler + kullanım + her ihale için takvim/risk/
uygunluk) birleşmeyi bıraktı; `GET /api/v1/panel` tek çağrısına geçti.

**Neden sadece performans değil.** Eski hâl istek sayısını sınırlamak için yalnız
ilk 5 incelemeye-hazır ihalenin bulgularını çekiyordu. Yani ekran "en yakın son
teklif tarihi"ni değil "ilk beş ihalenin en yakın tarihi"ni gösteriyordu —
BRIEF'teki birincil işi (5 saniyede eleme riskini görmek) sessizce yanlışlıyordu.

**Tarih ayrıştırma sunucuya taşındı** (`tenderiq_core.dates.parse_tr_date`,
`lib/format.ts → parseTrDate` ile aynı sözleşme). Sıralama istemcide kalsaydı
sunucu anlamlı bir LIMIT uygulayamaz, tüm satırları göndermek zorunda kalırdı.
Ham metin (`value_text`) yanıtta korunur — kaynağa sadık gösterim şart.

**Bileşen değişikliği.** `PanelData.detailLoading` kaldırıldı: tek uçla "üst veri
geldi, ayrıntılar geliyor" ara durumu yok. Üst seviye `state="loading"` iskeleti
duruyor.

**Gerçek veriyle doğrulama.** Faz 2 kiracısının 6 takvim bulgusundan 2'si
ayrıştırıldı ve başa alındı (28/02/2025 → 28/08/2025); "28/08/2025 tarihinden
önce olmamak üzere" gibi cümle içine gömülü tarih yakalandı, "14:00" ve "150
(yüzelli) takvim günüdür" ayrıştırılamayıp ham metniyle sonda kaldı.

**Çekim.** `design/preview` 375+1440: 0 konsol hatası, 0 yatay taşma.

---

## 2026-07-28 · /register + hukuki sayfa seti · tur 1-2

**Karar.** Kayıt ekranı `AuthLayout`'u birebir yeniden kullanır. Yeni bir auth
kompozisyonu denemedim: giriş ve kayıt yan yana görülen iki ekrandır, farklı
ritim "iki ayrı ürün" hissi verir. Tasarım sisteminin kendisi burada tutarlılıktır.

**Signature: canlı çalışma alanı kısa adı (slug).** Kayıt sırasında geri
alınamayan tek karar bu — hesap kapatma onayında kullanıcıdan birebir yazması
istenir ve backend Türkçe harf kabul etmez (`^[a-z0-9-]+$`). Gizli bir alan
olarak arkada türetmek, kullanıcıyı aylar sonra tanımadığı bir kimlikle
karşılaştırırdı. Bu yüzden unvan yazılırken altında canlı görünür ve "Değiştir"
ile açılır. Türkçe dönüşüm `lib/slug.ts`te: `İ/I/ı → i`, `ş → s`, `ğ → g`…
küçültmeden **önce** eşlenir, çünkü `"İ".toLowerCase()` birleşen nokta üretir ve
`toLocaleLowerCase("tr")` `I`yı `ı`ya çevirir — ikisi de sonradan eşlemeyi bozar.

**Tur 1 kritiği (1440 + 375):**

**İyi:** Sol sütun ritmi giriş ekranıyla birebir tutuyor; sağdaki kanıt motifi
kayıt anında da ürünün vaadini gösteriyor.

**Kötü:**
1. Birincil buton boş formda `disabled` — sayfanın ilk gördüğü şey ölü bir
   buton ve neyin eksik olduğunu söylemiyor. BRIEF'in "devre dışı buton değil,
   nedenini söyleyen metin" ilkesiyle de çelişiyor.
2. Zorunlu alan işareti yok (§8.6). 4 alandan 3'ü zorunlu, hiçbiri işaretli değil.
3. "Firma unvanı" altında iki ayrı yardım satırı (hint + "kısa adı kendim
   belirlemek istiyorum") yığılmış; form dikey ritmi yalnız bu grupta bozuluyor.
4. Ad soyad alanı isteğe bağlı ama öyle görünmüyor.
5. Placeholder "Berkay Yılmaz" — ürünün sahibinin adı; jenerik örnek olmalı.

**Uygulanan (tur 2):** 1 → `disabled` kaldırıldı; submit'te kısa ad geçersizse
alan açılıp odaklanıyor (ölü buton yerine düzeltilecek yeri gösteriyor).
2 → `*` + "* işaretli alanlar zorunludur". 3 → hint ile "Değiştir" aynı satırda
(login'deki "Parolamı unuttum" kalıbı). 4 → "(isteğe bağlı)". 5 → "Ayşe Demir".
Tur 2'de 4 viewport + koyu tema temiz: 0 konsol hatası, 0 yatay taşma.

**Hukuki sayfa seti** (`/kvkk`, `/sartlar`, `/trust`, `/dpa`) ortak
`LegalPage` kabuğunu kullanır; metin bloğu 68 karakterle sınırlı (§7.1).

**Bölümler JSX çocuk değil, VERİ olarak veriliyor.** İlk sürüm
`<LegalSection>` çocuklarıyla yazılmıştı ve içindekiler listesi yoktu; 9-12
bölümlük hukuki metinler birbirine `#saklama` gibi çapalarla atıf yapıyor,
yönlenme olmadan okunmuyor. İçindekiler'i elle yazmak ise başlıkla listenin
ayrışması riskini doğururdu — hukuki bir metinde bu kabul edilemez. Bölümler
`sections` dizisi olarak verilince liste otomatik üretiliyor, drift imkânsız.

**`<Fill>` bileşeni bilinçli olarak göze batıyor** (amber zemin, mono). Bir
hukuki metinde eksik alanın sessizce boş kalması, yanlış bilgi vermekten
tehlikelidir: kimse fark etmez. Ayrıca sayfa başında "taslak, hukuk onayından
geçmemiştir" uyarısı duruyor ve doldurulacaklar `grep -r "<Fill" apps/web/src`
ile listelenebiliyor.

**Bilinen borç (devam ediyor).** `design/refs/` hâlâ boş — bu ekranlarda referans
karşılaştırması yapılamadı; mevcut auth ekranları fiilî referans olarak kullanıldı.
Lighthouse erişilebilirlik skoru hâlâ ölçülmedi (§15 açık madde).
