// Yerel geliştirme/E2E için kurgusal, 5 sayfalık örnek şartname PDF'i üretir.
//
// Kaynak cümle `scripts/seed_e2e.py`deki QUOTE ile birebir aynıdır ve 4. sayfada,
// tohumdaki bbox'a (sol-üst köken, nokta: x 72–480, y 120–150) yerleştirilir; böylece
// inceleme ekranının "kaynağı vurgula" katmanı gerçek bir belgenin üstüne düşer.
// Kullanım: node scripts/ornek_sartname.mjs [çıktı.pdf]
// (Playwright'ın Chromium'u gerekir: `pnpm exec playwright install chromium`.)
import { chromium } from "@playwright/test";

const cikti = process.argv[2] ?? "scripts/fixtures/ornek-sartname.pdf";
const QUOTE = "Yüklenici tüm idari maddeleri eksiksiz karşılamak zorundadır.";

const madde = (no, baslik, metin) => `<h3>Madde ${no} — ${baslik}</h3><p>${metin}</p>`;
const sayfalar = [
  `<div class="kapak">
     <p class="ust">T.C. ÖRNEK BELEDİYESİ · DESTEK HİZMETLERİ MÜDÜRLÜĞÜ</p>
     <h1>İDARİ ŞARTNAME</h1>
     <p class="alt">Hizmet Binası Temizlik ve Genel Destek Hizmeti Alımı</p>
     <p class="alt">İhale Kayıt No: 2026/000000 (kurgusal)</p>
     <p class="not">Bu belge TenderIQ yerel geliştirme ortamı için üretilmiş kurgusal bir örnektir;
     gerçek bir idareye ya da ihaleye ait değildir.</p>
   </div>`,
  madde("1", "İdareye ilişkin bilgiler", "İdarenin adı, adresi, telefon numarası ve elektronik posta adresi bu maddede yer alır. İsteklilerin ihaleye ilişkin yazışmaları bu adrese yapılır.") +
    madde("2", "İhale konusu hizmete ilişkin bilgiler", "Hizmetin adı, niteliği, türü ve miktarı ekteki teknik şartnamede ayrıntılı olarak tanımlanmıştır. Hizmetin süresi işe başlama tarihinden itibaren 12 aydır.") +
    madde("3", "İhaleye ilişkin bilgiler", "İhale, Kamu İhale Kanununun 19 uncu maddesine göre açık ihale usulü ile yapılacaktır. Teklifler elektronik ortamda sunulur."),
  madde("4", "İhale dokümanının görülmesi", "İhale dokümanı EKAP üzerinden bedelsiz görülebilir. Teklif verecek isteklilerin e-imza kullanarak dokümanı indirmeleri zorunludur.") +
    madde("5", "Teklif ve sözleşme türü", "İstekliler tekliflerini birim fiyat üzerinden verecektir. İhale sonucunda birim fiyat sözleşme imzalanacaktır.") +
    madde("6", "Kısmi teklif", "Bu ihalede kısmi teklif verilemez. Teklifler işin tamamı için verilecektir."),
  `<div class="kesin" style="left:72pt;top:120pt;width:408pt;height:30pt">${QUOTE}</div>
   <div style="position:absolute;left:72pt;top:72pt;width:451pt"><h3>Madde 7 — İhaleye katılabilmek için gereken belgeler</h3>
   <p>7.1. İstekliler, aşağıdaki belgeleri teklifleri kapsamında sunmak zorundadır.</p></div>
   <div style="position:absolute;left:72pt;top:150pt;width:451pt">
   <p>7.2 bendindeki yükümlülük; iş deneyim belgesi, mesleki faaliyet belgesi ve teklif mektubu dahil
   olmak üzere idari şartnamenin her maddesini kapsar. Eksik belge, belgelerin tamamlatılmasına ilişkin
   hükümler saklı kalmak kaydıyla teklifin değerlendirme dışı bırakılmasına yol açar.</p>
   ${madde("8", "Geçici teminat", "İstekliler teklif ettikleri bedelin %3'ünden az olmamak üzere geçici teminat vereceklerdir. Teminat mektuplarının geçerlilik tarihi en az 120 gündür.")}
   ${madde("9", "Kesin teminat", "İhale üzerinde kalan istekliden sözleşme bedelinin %6'sı oranında kesin teminat alınır.")}
   </div>`,
  madde("10", "Fiyat farkı", "Bu ihalede fiyat farkı ödenmeyecektir.") +
    madde("11", "Ödeme yeri ve şartları", "Hak ediş ödemeleri aylık olarak, faturanın idareye tesliminden itibaren 30 gün içinde yapılır.") +
    madde("12", "Uyuşmazlıkların çözümü", "Sözleşmenin uygulanmasından doğan uyuşmazlıklarda Örnek İli mahkemeleri ve icra daireleri yetkilidir."),
];

const html = `<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>
@page { size: 595pt 842pt; margin: 0 }
* { box-sizing: border-box }
body { margin: 0; font-family: "Times New Roman", serif; color: #111 }
.sayfa { position: relative; width: 595pt; height: 842pt; padding: 72pt; page-break-after: always; overflow: hidden }
.sayfa:last-child { page-break-after: auto }
h1 { font-size: 26pt; letter-spacing: 2pt; margin: 180pt 0 16pt; text-align: center }
h3 { font-size: 12pt; margin: 0 0 6pt }
p { font-size: 11pt; line-height: 1.45; margin: 0 0 14pt; text-align: justify }
.ust { text-align: center; font-size: 10pt; letter-spacing: 1pt }
.alt { text-align: center; font-size: 13pt }
.not { margin-top: 260pt; font-size: 9pt; color: #555; text-align: center }
.kesin { position: absolute; font-size: 11pt; line-height: 30pt; white-space: nowrap }
.no { position: absolute; bottom: 36pt; left: 0; right: 0; text-align: center; font-size: 9pt; color: #555 }
</style></head><body>${sayfalar
  .map((icerik, i) => `<section class="sayfa">${icerik}<div class="no">Sayfa ${i + 1} / ${sayfalar.length}</div></section>`)
  .join("")}</body></html>`;

const tarayici = await chromium.launch();
const sayfa = await tarayici.newPage();
await sayfa.setContent(html, { waitUntil: "load" });
await sayfa.pdf({ path: cikti, preferCSSPageSize: true, printBackground: true });
await tarayici.close();
console.log(`yazıldı: ${cikti}`);
