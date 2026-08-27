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

---

## 2026-07-29 · /usage — abonelik iptali ve plan değişimi · tur 1-2

**Bağlam.** `/sartlar` §3 üç şey taahhüt ediyor (yükseltme anında, düşürme dönem
sonunda, iptal dönem sonunda) ve 14 gün koşulsuz cayma hakkı veriyor. Kullanıcının
kendi iptal edebildiği bir yol olmadan bu taahhüt tutulamıyordu — yayın engeli.

**Karar: iptal ayrı bir "tehlikeli bölge" kartına konmadı.** `/settings`teki hesap
kapatma `danger` kenarlıklı ayrı bir kartta duruyor (§9.7) ve ilk refleks iptali de
oraya koymaktı. Yapmadım: hesap kapatma geri alınamaz ve veri siler; abonelik iptali
dönem sonuna kadar tek tıkla geri alınır ve hiçbir şey silmez. İkisini aynı görsel
dille anlatmak, iptali olduğundan korkutucu gösterir — yani kullanıcıyı caydırır.
Bu, `/sartlar`ın verdiği hakkı arayüzle geri almak olurdu. Buton `secondary`,
kart nötr, onay kutusunda kırmızı yok.

**Karanlık desen sayımı (bilinçli olarak sıfır):** tutma teklifi yok, "gerçekten
emin misiniz" suçlaması yok, yazı yazdırma yok (hesap kapatmada var — orada
gerekli), gizli buton yok. Onay kutusundaki görsel birincil eylem iptalin kendisi.
Geri alma butonu, iptalin duyurulduğu uyarının hemen altında.

**Signature: "erişiminiz şu tarihe kadar sürüyor".** Bu ekranın akılda kalan tek
öğesi olması gereken şey, iptalden sonra kullanıcının aklındaki tek soru: *ne
zaman kesilecek?* Bu yüzden tarih iki kez, iki farklı yerde ve iki farklı anlamda
yazılıyor — uyarı bloğunda ("erişim bitişi") ve iptal edilmemişken veri satırında
("sıradaki tahsilat"). Aynı alandan gelirler ama biri diğerinin yerine geçemez:
iptal etmiş kullanıcıya "sıradaki tahsilat" göstermek yanlış bilgi olurdu, o yüzden
API `next_charge_at`i o durumda `null` döndürüyor.

**Tur 1 kritiği (1440 + 375, aktif ve iptal durumları):**

**İyi:** Abonelik kartı kota kartının ritmini birebir tutuyor (padding, radius,
kenarlık) — sayfaya yeni bir görsel dil sokmuyor. Uyarı bloğu `account-section` ve
`legal-shell`deki mevcut uyarı anatomisiyle aynı; ikinci bir uyarı görünümü
üretmedim.

**Kötü:**
1. **Sayfa başlığındaki durum rozeti iptal edilmiş abonelikte hâlâ "● Etkin"
   (yeşil).** Hemen altında "dönem sonunda sona erecek" yazıyor — ekranın en
   görünür öğesi, hemen altındaki cümleyle çelişiyor. Teknik olarak doğru
   (durum ACTIVE kalıyor, erişim sürüyor) ama kullanıcı için yanlış.
2. Kart açıklaması ile altındaki veri satırı (`Sıradaki tahsilat`) sıfır boşlukla
   yapışık (`CardContent pt-0`); üçü tek bir paragraf gibi okunuyor (§13.3).
3. Kota kartı ↔ abonelik kartı arası ile abonelik kartı ↔ "Planlar" bölümü arası
   eşit (32px). Bölüm ayrımı kart ayrımından büyük olmalı (§5.3), yoksa üç blok
   da eşit uzaklıkta durur ve hangisinin bir bütün olduğu okunmaz.

**Uygulanan (tur 2):** 1 → rozet `cancel_at_period_end`i okuyup "Dönem sonunda
bitiyor" (warning) diyor; durum alanını eziyor. 2 → `pt-4`. 3 → kartlar `mb-6`,
bölüm öncesi `mb-8`.

**Tur 2 çekimi.** 375 · 768 · 1440 · 1920 + koyu tema; dört durum (aktif, iptal
edilmiş, bekleyen düşürme, onay kutusu). Yatay taşma yok, konsolda yalnız
projede zaten var olan Next.js `scroll-behavior` uyarısı.

**`scripts/shoot.mjs` genişletildi.** Kimlik gerektiren ekranlar girişsiz
çekilirse yalnız `/login`in görüntüsü alınıyor ve §14 döngüsü sessizce hiçbir şey
doğrulamamış oluyordu. `SHOOT_EMAIL`/`SHOOT_PASSWORD` verildiğinde her viewport
kendi bağlamında giriş yapıyor (çerezler bağlamlar arasında paylaşılmaz).

**Bilinen borç.** `design/refs/` hâlâ boş; karşılaştırma yine mevcut ekranlara
karşı yapıldı. "Ücretsiz" plan kartında başlık ve fiyat alanı aynı kelimeyi iki
kez yazıyor (`formatPrice` 0 TL için "Ücretsiz" döndürüyor) — bu turun kapsamı
dışında, plan kartı kopyası ayrı bir karar. Lighthouse erişilebilirlik skoru
hâlâ ölçülmedi (§15 açık madde).

---

## 2026-07-30 · zorlayıcı CSP + erişilebilirlik denetimi · tur 10

**Kapsam.** Görsel yeniden tasarım değil: politika (CSP) ve semantik (ARIA,
başlık kademesi) düzeltmeleri. Bu yüzden döngünün amacı "daha iyi görünsün"
değil, **görünümün hiç değişmediğini kanıtlamak** oldu.

**Tur 1 — ölçüm (kusurları bulan tur).** Lighthouse erişilebilirlik 16 rotada
ölçüldü (`scripts/lighthouse-a11y.mjs`). Skorlar 95–100 arasıydı, yani görev
eşiğinin (90) üstünde; buna rağmen **üç gerçek kusur** çıktı. Ders: skora bakmak
yetmiyor, düşen denetimlerin listesine bakmak gerekiyor.

**İyi:** Hukuki sayfalar, auth ekranları ve `/panel` ilk ölçümde 100'dü — token
sistemi ve kontrast kararları tutmuş. Konsol dört viewport'ta temiz.

**Kötü (ölçümle bulundu):**
1. Hesap menüsü butonunun erişilebilir adı görünen metni kapsamıyordu
   (`aria-label="Hesap menüsü"` vs görünen "E2E Test Kullanıcısı · Yönetici") —
   WCAG 2.5.3. Sesli komut kullanıcısı butonu adıyla çağıramaz.
2. `CardTitle` sayfa düzeyindeki kartlarda `h1 → h3` atlaması üretiyordu
   (`/usage`, `/settings`, `/capability`).
3. Segment kontrolü Radix `Tabs` ile kuruluyordu ama panel yoktu; `aria-controls`
   var olmayan bir kimliğe işaret ediyordu. DESIGN.md §8.11 bu ayrımı zaten
   yazmış ("sekme sayfa bölümü değiştirir, segment aynı veriyi farklı gösterir")
   — kod o ayrımı takip etmiyordu.

**Uygulanan:** 1 → `aria-label` kaldırıldı, amaç `sr-only` metne taşındı.
2 → `CardTitle` `as` prop'u aldı (varsayılan `h3`), sayfa düzeyindeki kartlar
`as="h2"`. 3 → `components/ui/segmented-control.tsx` (`role="group"` +
`aria-pressed`); sınıflar `tabs.tsx`ten **tek kaynak** olarak alınıyor
(`tabsTriggerClassName` dışa açıldı) — kopyalasaydım görünüm zamanla ayrışırdı.

**Tur 2 — doğrulama.** Yeniden ölçüm: **16 rota × 100/100, düşen denetim yok.**
Ekran görüntüleri `/tenders` (375·768·1440·1920 + koyu tema), `/settings`
(375·1440), `/usage` (1440): yatay taşma yok, konsol temiz, segment kontrolü
375'te kendi içinde kayıyor (§7.4) ve koyu temada yüzey açıklığıyla derinlik
veriyor (§5.2). Kart başlıkları aynı boyutta — seviye değişikliği görünümü
etkilemedi (sınıflar seviyeden bağımsız).

**CSP notu (tasarımı etkileyen taraf).** Politika zorlayıcı ve nonce tabanlı
oldu; nonce istek başına değiştiği için kök layout `headers()` okuyor ve **tüm
rotalar dinamik render'a geçti** (derleme çıktısında artık `○` yok, hepsi `ƒ`).
Statik hukuki sayfalar da dâhil. Bu bilinçli bir ödün: alternatif, korumayı en
çok gereken yerlerde (`/login`, `/register`) `'unsafe-inline'` bırakmaktı.
`next-themes`in satır içi tema betiğine nonce geçirildi — geçirilmezse koyu tema
kullanıcısı her yüklemede bir kare beyaz görürdü.

**Bilinen borç.** `design/refs/` hâlâ boş. `/tenders/[id]` ve
`/tenders/[id]/review` Lighthouse ile ölçülmedi (dinamik rota; betiğin listesi
sabit) — inceleme ekranı çekirdek çalışma alanı olduğu için bu bir açık madde.
Performans kategorisi ölçülmedi; dinamik render'a geçişin maliyeti bilinmiyor.

---

## 2026-07-30 · dinamik rotalar ölçüme girdi · tur 11

**Kapsam.** Görsel değişiklik yok; ölçüm KAPSAMININ genişletilmesi. Tur 10'da
`/tenders/[id]` ve `/tenders/[id]/review` "dinamik rota" oldukları için Lighthouse
listesinin dışında kalmıştı — yani ürünün çekirdek çalışma alanı hiç ölçülmemişti.

**Ölçüm kapsamı genişletilir gibi bir şey yoktu: kimlik listeden okunuyor.**
`scripts/lighthouse-a11y.mjs` artık giriş yaptıktan sonra `/tenders` listesinden
ilk ihalenin `href`ini okuyup `:tenderId` yer tutucusunu dolduruyor. Elle env
değişkeni vermek yanlış olurdu: tohum yeniden koşulduğunda kimlik değişir,
Lighthouse 404 sayfasını ölçer ve skor "iyi" görünür.

**Kötü (ölçümle bulundu):** `/tenders/[id]` = 98 · `heading-order`. "Şartname
yükle" kartının başlığı `h3`, sayfa başlığı `h1` → bir kademe atlanıyor.
Tur 10'da altı kart başlığı düzeltilmişti ama bu sayfa ölçülmediği için gözden
kaçmıştı — düzeltmenin kapsamı ölçümün kapsamı kadardı.

**Uygulanan:** `CardTitle as="h2"` (`components/tenders/tender-detail-view.tsx`).
Sonuç: **18 rota × 100/100, düşen denetim yok.**

**CSP'nin doküman tuvalini öldürdüğü bulundu (görsel sonucu olan asıl kusur).**
`e2e/csp.spec.ts`e eklenen kimlikli test, inceleme ekranında `connect-src`
ihlali gösterdi: imzalı PDF URL'i politikada yok, yani **tuval boş kalıyor**.
BRIEF `kirmizi_cizgiler` #1 ("bulgu kaynağından koparılamaz") tam olarak o tuvale
dayanıyor; zorlayıcı CSP onu sessizce kesmişti. Sebep `NEXT_PUBLIC_STORAGE_ORIGIN`
değişkeninin hiçbir yerde kurulmaması + derleme anında gömülmesi. Düzeltildi
(compose build arg, CI job env, `.env.example`'da "ZORUNLU" işaretiyle).

**Performans.** Nonce CSP'nin tüm rotaları dinamik render'a geçirmesinin bedeli
ölçüldü: ortanca TTFB +6 ms, LCP +25 ms, skor değişmedi (98–100). Tasarım
açısından anlamı: yoğunluk/yerleşim kararlarını değiştirmeyi gerektiren bir
maliyet yok. Ölçümün görmediği şey CDN önbelleği kaybı (localhost).

**Bilinen borç.** `design/refs/` hâlâ boş. `sonner` çalışma anında nonce'suz
`<style>` enjekte ettiği için `style-src 'unsafe-inline'` kalıcı borç oldu
(ölçülerek doğrulandı; DURUM.md §1.2).

---

## 2026-07-31 · /usage — bütçe, depolama ve yönetici teşhisi · tur 1-3

**Bağlam.** J.6'nın backend'i Tur 13-16'da bitti (ölçüm → tavan → depolama kotası
→ yönetici teşhis ucu) ama ekran yalnız doküman ve sayfa metresini gösteriyordu.
Yani ürün, kullanıcıyı **göremediği bir sınırla** reddediyordu — GA engeli.

### Bilgi hiyerarşisi kararı: dört ölçer eşit değildir

Jenerik çözüm dört ölçeri (doküman · sayfa · bütçe · depolama) yan yana dizmekti.
Bu üründe **yanlış** olurdu: doküman ve sayfa kotaları `plans.py`de bütçeden
TÜRETİLİYOR ve bütçe pratikte hep önce doluyor. Dördünü eşit göstermek,
"3 dokümandan 1'ini kullandım" diyen bir kullanıcının neden reddedildiğini
açıklanamaz hâle getirirdi. Bu yüzden bütçe hero konumunda tek başına; kotalar
onun altında ikincil satırlar ve aralarında şu cümle var: *"Doküman ve sayfa
kotası bir üst sınırdır; bir analizi fiilen durduran şey yukarıdaki bütçedir."*

**Depolama ayrı karttadır** çünkü dönemsel değil kümülatiftir. "Bu dönem"
başlığının altına koymak, ay başında sıfırlanacağını ima ederdi.

### İMZA ÖĞESİ — taralı rezervasyon segmenti

Rezerve tutar ne "harcanmış" ne "kalan"dır: iş bitince serbest kalır (harcanmadı)
ama o parayla yeni iş başlatılamaz (kabul sınırı `tavan − rezervasyon`). İki uçtan
birine yuvarlamak yanlış bilgi olurdu — harcamaya katmak "param bitti" dedirtir,
kalana katmak olmayan bir hakkı vadeder.

Çözüm: aynı çubukta **ayrı segment + ayrı doku**. Birincil seri (harcanan) düz
dolgu, ikincil seri (ayrılan) 45° taralı dolgu — §8.26.2'nin "ikincil serilerde
tarama" kuralı. Doku aynı zamanda renk körü yedeğidir (§12) ve §8.13 gereği
açıklama listesi her zaman yazılır. §13.6 testi: bu kararı herhangi bir dashboard
için verir miydim? Hayır — çoğu üründe "rezerve" kavramı yok, olsa da harcamaya
katılır.

**Bunun için backend'e tek satırlık bir düzeltme gerekti:** `GET /usage`
`reserved_try`i sabit `0.0` döndürüyordu (yalnız yönetici ucu Redis'e bakıyordu).
Yani alan "ayrı duruyor" ama hep boştu ve `remaining_try`, kabul kontrolünün
uyguladığı sınırdan büyük çıkıyordu — ekran "₺14 kaldı" derken sunucu reddederdi.

### Tur 1 kritiği (1440 · 375 · koyu)

**İyi:** Bütçe çubuğu tek bakışta okunuyor; taralı segment düz segmentten net
ayrışıyor. Yönetici uyarıları ciddiyet sırasına göre iniyor (kırmızı → sarı →
mavi) ve `unpriced_calls` hem sayı hem renk olarak görünür.

**Kötü:**
1. Hero'da 30px rakam ile "harcandı" arası 4px — 375'te "8,40harcandı" gibi
   okunuyor (§13.3 optik hizasızlık).
2. `₺25,00 tavan` 1440'ta kartın sağ ucunda, hero'dan ~1000px uzakta. İki sayı
   arasındaki ilişki mesafeyle anlatılmaz.
3. Kur eksikken hem "kur tanımlı değil" hem "3 çağrının tutarı hesaplanamadı"
   uyarısı çıkıyor. İkincisi birincinin SONUCU — iki bağımsız arıza varmış gibi
   duruyor ve yöneticiyi olmayan ikinci bir işin peşine düşürüyor.
4. `Sayfa` ölçerinde eşik uyarısı kapalıydı: sayfa kotası dolduğunda kullanıcı
   hiçbir cümle görmüyordu. Tur 2'nin `showThresholdNote` gerekçesi ("aynı cümle
   iki kez") burada geçersiz — iki kota AYRI sebeplerle dolar.
5. `formatBytes` 500 MB'ı "500,0 MB", 2 KB'ı "2,0 KB" yazıyor.
6. Sayfa açıklaması hâlâ yalnız "kota"dan söz ediyordu.
7. Teşhis ızgarasındaki "Dönem" hücresi ₺8,40 ile aynı mono ağırlıkta — tarih
   aralığı bir metrik değil, üstelik sayfanın üstünde zaten yazılı.

**Uygulanan (tur 2):** 1 → hero iki gruba ayrıldı, `gap-x-2`. 2 → tavan hero'nun
yanına alındı (`₺8,40 harcandı · ₺25,00 tavan`), sağ uçtaki değer kaldırıldı.
3 → kur eksikken `unpriced` uyarısı yazılmıyor, sayı fx uyarısının içine
gömülüyor. 4 → iki ölçere de kendi `noteNear`/`noteFull` cümlesi. 5 →
`formatBytes` en fazla bir ondalık, zorunlu değil. 6 → açıklama güncellendi.
7 → dönem, kartın açıklama cümlesine taşındı.

### Tur 2 kritiği — ölçümle bulunan gerçek kusur

**Açıklama listesindeki üç örnek (swatch) hiç çizilmiyordu.** `<span>` satır içi
kaldığı için `h-2 w-3` yok sayılıyor, kutular sıfır genişlikte bir kenarlığa
düşüyor ve "Kalan" örneği ince bir dikey çizgi — yani AYIRICI — gibi okunuyordu.
375'te satır başında yalnız bir "|" kalıyordu. Yani §8.13'ün zorunlu kıldığı
açıklama listesi fiilen YOKTU ve çubuk tek başına renk/dokuya kalıyordu (§12
ihlali). Ekran görüntüsüne gerçekten bakılmasaydı bu kusur görülmezdi: kod
doğru, sınıflar doğru, çıktı yanlıştı.

**Uygulanan (tur 3):** sarmalayıcı `flex`, örnekler `block`; "Kalan" örneği
`border-strong` (WCAG 1.4.11 için 3:1). Ayrıca "Dönem 01.07.2026 – 01.08.2026 ·
01.08.2026 tarihinde sıfırlanır" aynı tarihi iki kez yazıyordu → "bitiminde
sıfırlanır" (eksiz kalıp, Ek B.3).

### Durumlar

Beşi de kodlandı ve **canlı backend'e karşı** çekildi (önizleme mock'u değil):
- **İlk kullanım** (dört boyut da sıfır): §10.1 daveti — "Bu dönemde henüz analiz
  yapılmadı" + hakkın tamamı (kota · bütçe · yenilenme tarihi · depolama kotası)
  + "İhalelere git". Dört boş çubuk çizmek hiçbir soruyu yanıtlamazdı.
- **Normal**, **tavana yakın** (yumuşak eşik uyarısı), **dolu** (sert ret:
  ne olduğu · ne zaman sıfırlanacağı · plan yükseltme yolu; sayfanın TEK primary
  butonu bu durumda beliriyor).
- **Yükleniyor** iskeleti hero + çubuk + açıklama + iki ölçer şeklini taklit
  ediyor; **hata** `InlineError` ile kart içinde kalıyor (sayfa çökmüyor).

### Yönetici tarafı

`Yalnız yönetici` rozeti taşıyor ve yalnız `role === "admin"` iken çiziliyor —
ama asıl kapı sunucuda (403). `e2e/usage.spec.ts` ikisini de sınıyor: üye
sayfayı açıyor, kendi kullanımını görüyor, teşhis kartının hiçbir izini
görmüyor (başlık · rozet · sayı · hata kartı yok) ve sayfanın kendi origin'inden
`fetch` ettiğinde 403 alıyor.

> `page.request` KULLANILMADI: o bağlam oturum çerezini taşımıyor ve isteği
> kimliksiz gönderiyor (401). "Üye reddedildi" yerine "kimse reddedildi" ölçmüş
> olurduk — hiçbir şey kanıtlamayan yeşil bir test.

### Yeni paylaşılan bileşen: `components/notice.tsx`

`subscription-card.tsx` içindeki yerel `Notice` çıkarıldı ve üç tonlu
(info/warning/danger) tek bir bileşene dönüştü. Bütçe ve teşhis ekranları üç ayrı
ciddiyet seviyesi taşıyor; bunları ayırt eden şey **ton** olmalı, anatomi değil.
`InlineError` ile karışmasın diye ayrımı dosyaya yazdım: `InlineError` bir
İSTEĞİN başarısız olduğunu söyler ("yeniden dene"), `Notice` başarıyla dönmüş
verinin ANLAMINI söyler — tekrar denemek bir şey değiştirmez.

### Spec'ten sapma

§6.5 "para birimi sayıdan küçük ve muted" **uygulandı** ama yalnız bütçe
hero'sunda: `splitCurrency` Intl'in kendi parçalarından okuyor (sembolün yeri ve
boşluğu locale kararıdır). Plan kartlarındaki fiyatlar bölünmedi — orada değer
"Ücretsiz" / "Özel fiyat" gibi metin de olabiliyor ve bölünmüş sembol üç kartta
iki farklı para anatomisi üretirdi.

### Ortam notu (bir sonraki tur için)

**~~`next dev` bu projede §14 döngüsü için KULLANILAMAZ.~~ ÇÖZÜLDÜ — 2026-08-01,
aşağıdaki turda.** Zorlayıcı CSP'de `'unsafe-eval'` yoktu; webpack dev bundle'ı
`eval` kullandığı için hidrasyon hiç çalışmıyor, form gönderimi düz GET'e düşüyor
ve ekran görüntüsü "çalışıyor gibi" görünüyordu. Artık dev politikası
`'unsafe-eval'` içeriyor (üretim içermiyor) ve `next dev` üzerinde ekran görüntüsü
alınabiliyor. **Dev sunucusu ayaktayken `next build` yine çalıştırılmaz.**

**Bilinen borç.** `design/refs/` hâlâ boş (bu turda da karşılaştırma mevcut
ekranlara karşı yapıldı). Kart başlıkları (`CardTitle` h2) ile bölüm başlığı
(`SectionHeader` h2) tipografik olarak aynı — sayfa dört kart + bir bölümle
uzadıkça bu düzlük daha görünür oldu; ayrı bir tipografi turu gerektiriyor,
bu turun kapsamı dışında bırakıldı.

---

## 2026-08-01 · /login + landing "Giriş yap" · giriş kilidi

**Belirti (kullanıcı raporu):** Landing'de "Giriş yap"a tıklayınca giriş sayfası
yerine `/tenders`'a düşülüyor, `/tenders` da boş çıkıyor — yani hesaba hiç
girilemiyor.

**Kök neden ÜÇ ayrı kusurdu, ikisi birbirini gizliyordu.**

1. `middleware.ts` oturum cookie'sinin yalnız VARLIĞINA bakıp `/login`i koşulsuz
   `/tenders`'a yolluyordu. Middleware geçerliliği göremez; bayat/bozuk token'da
   giriş sayfası erişilemez oluyor, `/tenders` ise 401 alıp boş kalıyordu. Tek
   kurtuluş yolu istemci JS'inin 401'i görüp cookie'leri temizlemesiydi — yani
   (2) yüzünden hiç işlemeyen bir yol.
2. Dev CSP'sinde `'unsafe-eval'` yoktu; `next dev` paketi modülleri `eval()` ile
   sardığı için **hiçbir istemci betiği çalışmıyordu.** Sayfa SSR HTML'iyle
   donuyor, veri çekilmiyor, form gönderimi düz GET'e düşüyordu.
3. Landing `FinalCta`'daki "Ücretsiz başla" `/login`e gidiyordu; aynı etiket
   sayfanın diğer iki yerinde `/register`e gidiyor.

**Karar — doğrulanmış yönlendirme, middleware'de değil sayfada.** "Zaten girişli
misin" kontrolü `app/login/page.tsx`e (sunucu bileşeni) taşındı ve backend'e
`GET /api/v1/auth/me` ile SORULUYOR. Neden middleware değil: edge çalışma
zamanında `process.env` derleme anında sabitleniyor (§CSP'deki `STORAGE_ORIGIN`
tuzağının aynısı), yani `API_URL` üretim imajında görünmezdi. Doğrulanamayan her
durumda **form gösteriliyor** — yanlış tarafa düşmek serbest bırakmaktır,
kilitlemek değil. Girişli kullanıcı için `/login → /tenders` kolaylığı korundu.

**Görsel doğrulama:** dev sunucusunda gerçek Chromium; 1440×900.
- `/login` — §9.6 iki sütun (sol form ≤400px, sağda ürünün kendi bulgu satırı),
  focus halkası görünür, form/istemci-bileşeni ayrımı görünümü bozmadı.
- `/tenders` — kenar çubuğu + kullanıcı kartı + §10.1 boş durumu ("Henüz ihale
  projesi yok" + eylem butonu) doğru çiziliyor. Konsol 0 hata.

**Bulunan, DÜZELTİLMEYEN kusur (kapsam dışı):** `/tenders` boş durumunda ekranda
İKİ primary buton var — başlıktaki "Yeni ihale" ve boş durumdaki "Yeni ihale".
§13.5 ve §15 "sayfada tek primary buton" der. Boş durum butonu kalmalı (§10.1
eylem butonu zorunlu), başlıktakinin `secondary`ye inmesi gerekir. Ayrı tur.

---

## 2026-08-01 · yükleme + doküman tuvali · depolama zinciri

**Belirti:** Dosya seçip yükleyince "Failed to fetch"; mevcut ihalenin PDF'i
görünmüyor. İki belirti, **iki ayrı kusur** — ama tek bir zincirin ardışık iki
halkası olduğu için biri düzeltilmeden diğeri görünmüyordu.

**Kusur 1 — depolama origin'i yerel çalıştırmada CSP'ye hiç girmiyordu.**
Tarayıcı nesne depolamaya DOĞRUDAN çıkıyor: yükleme `PUT`, önizleme `GET`.
`NEXT_PUBLIC_STORAGE_ORIGIN` yalnız `required: "production"` olduğu için dev'de
sessizce boş kalıyor, `connect-src 'self'` oluyor ve tarayıcı ikisini de kesiyor.
Tur 11'de üretim için compose build ARG'ıyla çözülmüştü; **yerel `next dev` /
`next build` yolunun karşılığı yoktu** — Next yalnız `apps/web` altındaki `.env`
dosyalarını okur, değerin tek gerçek kaynağı olan kök `.env` oraya ulaşmaz.
Çözüm: `next.config.ts` origin'i kök `.env`den compose ile AYNI zinciri kullanarak
türetiyor (`NEXT_PUBLIC_STORAGE_ORIGIN` → `STORAGE_ORIGIN` →
`OBJECT_STORAGE_ENDPOINT_URL`in origin'i). İkinci bir dosyaya elle kopyalamak
origin'i iki yere yazardı ve R2 hesabı değişince biri sessizce eskirdi.

**Türetme `process.env`e yazmakla OLMUYOR.** Denendi: `connect-src 'self'` olarak
kaldı. Next `NEXT_PUBLIC_*` değerlerini paketlere gömerken kendi anlık görüntüsünü
kullanıyor ve `config()` çağrıldığında o görüntü çoktan alınmış oluyor. Değer
`nextConfig.env` üzerinden veriliyor — gömmeyi yapan belgelenmiş mekanizma bu ve
edge (middleware) paketini de kapsıyor. Üretim kapısı gevşemedi: kök `.env`
Docker bağlamına hiç girmiyor (`.dockerignore`), CI değişkeni açıkça veriyor,
eksik build ARG'ı `assertBuildTimeEnv()` yakalamaya devam ediyor.

**Kusur 2 — `connect-src` `blob:` taşımıyordu. Bu bir ÜRETİM kusuruydu.**
Origin düzeltilince R2 `GET → 200` geldi, dosya indi — tuval yine boş kaldı.
`pdf-viewer.tsx` baytları bir kez indirip `URL.createObjectURL` ile sarıyor ve
PDF.js'e `blob:` adresini veriyor; PDF.js onu `fetch`liyor ve CSP kesiyor
("Unexpected server response (0)"). `img-src` ve `worker-src` zaten `blob:`
taşıyordu, `connect-src` atlanmıştı.

**E2E bunu neden görmedi — yapısal kör nokta.** `csp.spec.ts` depolama origin'i
olarak bilinçli biçimde ölü bir port kullanıyor (hermetiklik için doğru karar).
Baytlar hiç gelmediği için `createObjectURL` hiç çağrılmıyor, PDF.js hiç `blob:`
istemiyor ve ihlal **doğamıyor**. Yani test zincirin ilk halkasını doğrularken
ikincisini yapısal olarak maskeliyor. Kapatan şey `csp-policy.spec.ts`e eklenen
ağa çıkmayan birim kapısı: politika `blob:` taşıyor mu.

**Doğrulama (gerçek Chromium, dev, 1440×900):** giriş → ihale detayı → gerçek
şartname (`idari-sartname-6428pdf.pdf`, 337,6 KB) yüklendi: `[R2] PUT → 200`,
belge listeye düştü, işleme hattı başladı, "Failed to fetch" yok, 0 CSP ihlali.
İnceleme ekranı: `[R2] GET → 200`, 1 canvas 732×1035, PDF'in ilk sayfası
("T.C. SAĞLIK BAKANLIĞI … İDARİ ŞARTNAME", 1/15) okunur biçimde çiziliyor.
