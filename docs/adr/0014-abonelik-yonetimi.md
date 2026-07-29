# ADR-0014: Abonelik Sağlayıcı Tarafında Yönetilir (iyzico Abonelik), Yetkilendirme Bizde Aynalanır

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-29 (GA turu 3)
- **Karar veren:** Berkay (Scryne)
- **İlgili:** ADR-0013, `packages/core/src/tenderiq_core/billing/`, `LEGAL_TODO.md` §E

## Bağlam

Ödeme seam'i (`BillingProvider`) checkout + webhook yüzeyiyle zaten var ve
`manual` test sağlayıcısıyla uçtan uca çalışıyor. Gerçek sağlayıcıya (iyzico)
geçerken iki mimari yol var ve seçim, yazılacak kod miktarını **ve taşınan
riski** belirliyor:

**Yol A — Sağlayıcı tarafında abonelik.** Planlar iyzico'da tanımlanır; yenileme,
başarısız tahsilatta yeniden deneme (dunning), kart güncelleme akışı ve
tekrarlayan çekimin kart şeması kuralları sağlayıcıdadır. Biz yalnız **olayları
dinler** ve yetkilendirmeyi (hangi kiracı hangi planda, ne zamana kadar)
kendi veritabanımızda aynalarız.

**Yol B — Kendi tarafımızda abonelik.** Saklı kart (tokenizasyon) sağlayıcıda
kalır ama dönem takibi, yenileme zamanlaması, yeniden deneme merdiveni ve kart
güncelleme akışı bizde olur.

## Karar

**Yol A.** Abonelik yaşam döngüsü iyzico'da yönetilir; TenderIQ veritabanı
yetkilendirmenin **aynası**dır, kaynağı değil.

### Neden

1. **Tekrarlayan çekimde kart şeması kuralları bizim uzmanlık alanımız değil.**
   İlk tahsilat 3D Secure ile müşteri huzurunda (CIT) yapılır; sonraki
   yenilemeler müşteri yokken (MIT) çekilir ve doğru işaretlenmezse banka
   reddeder. Bu işaretlemeyi ve istisnalarını doğru kurmak, tek kişilik bir
   ekibin sessizce yanlış yapacağı türden bir iştir — ve yanlışlığı ancak
   **gelir kaybı olarak** fark edilir.
2. **Dunning bedava gelir.** Yol B'de 3 denemeli artan aralıklı bir merdiven,
   zamanlanmış iş, kilitlenme koruması ve "deneme sırasında kullanıcı planı
   değiştirirse" gibi kenar durumlar yazmak gerekir. Bunların hiçbiri ürünün
   ayırt edici değeri değil.
3. **Kart güncelleme akışı sağlayıcının yüzeyinde kalır.** Kartı süresi dolan
   müşteriye kendi güvenli formumuzu sunmak zorunda kalmayız.
4. **Kota bağlantısı iki yolda da aynı.** Kotalar `billing.plans`tan okunuyor ve
   `Subscription` yalnız kademe + durum tutuyor; yani aynalama modeli mevcut
   tasarıma **hiç dokunmadan** oturuyor.

### Neden Yol B değil (ve ne kaybediyoruz)

Yol B daha çok kontrol verirdi: özellikle **oransal (prorated) plan
değişikliği**. Sağlayıcı tarafında oranlama sınırlıdır. Bu kaybı şöyle
karşılıyoruz:

- **Yükseltme anında geçerlidir**, ücret farkı sağlayıcı tarafında bir sonraki
  dönemde yansır. Müşteri parasını ödemeden önce yeni kotayı kullanır — bu,
  ters yönüne (parayı alıp kotayı vermemek) tercih edilir ve kötüye kullanım
  riski aylık ölçekte önemsizdir.
- **Düşürme dönem sonunda geçerlidir.** Ödenmiş dönemin ortasında kotayı
  kısmak, satın alınan hizmeti geri almaktır.

Bu kural `docs`ta ve `/sartlar` §3'te zaten yazılıdır ("Plan yükseltmeleri
anında etkinleşir; düşürmeler dönem sonunda uygulanır") — yani karar metinle
tutarlıdır.

## Sonuçlar

- `BillingProvider` seam'i **abonelik operasyonlarıyla genişletilir** (iptal,
  plan değişimi, müşteri portalı bağlantısı), ama **dunning ve yenileme
  zamanlaması yazılmaz**.
- Webhook, yetkilendirme değişiminin **tek** kaynağıdır: `activated`, `past_due`,
  `canceled`, `expired` olayları aynayı günceller. Sıra dışı gelen olaylara
  dayanıklılık şart (olay zaman damgası eskiyse yok sayılır).
- Kart verisi hiçbir zaman bize gelmez; PAN/CVV ne loglanır ne saklanır.
- **Fatura ayrı bir yükümlülüktür.** iyzico fatura kesmez; e-Arşiv/e-Fatura
  entegratörü gerekir. `InvoiceProvider` seam'i bunun için ayrılır (no-op
  varsayılan), tetiklendiği nokta kodda işaretlenir. Bkz. `LEGAL_TODO.md` §E.
- **Kart dışı yol korunur:** Türkiye B2B'sinde havale/EFT yaygındır. Kurumsal
  müşteri için sipariş + "ödeme bekliyor" + yönetici onayıyla manuel aktivasyon
  yolu, sağlayıcıdan bağımsız olarak kalır.

## Koşul: bu karar hangi durumda yeniden açılır

**Tetikleyici.** Bu ADR, iyzico'nun abonelik ürününün bize **açılabilir**
olduğunu varsayıyor. 2026-07-29 itibarıyla açık değil: `/v2/subscription/*`
uçlarının hepsi, gövdeden bağımsız olarak `422 errorCode:100001` dönüyor;
aynı anahtarlarla `/payment/bin/check` 200 veriyor — yani kimlik ve imza doğru,
eksik olan merchant hesabındaki abonelik modülü (bkz. `docs/ops/billing-setup.md`).
Bu bir hesap/başvuru işlemidir ve sonucu bizim elimizde değildir. **Modül
etkinleştirilemezse — başvuru reddedilirse, süresiz beklerse ya da ticari
koşulları kabul edilemez çıkarsa — Yol A uygulanamaz ve bu karar yeniden
açılmalıdır.** Karar burada verilmiyor; yalnızca tetikleyici ve alternatifler
kayda geçiriliyor, çünkü tetikleyici geldiğinde bu analiz sıfırdan yapılırsa
zaman baskısı altında yapılacaktır.

**Alternatifler ve çöpe gidecek iş.** İki yol var. Birincisi **Yol B'ye geçmek**:
saklı kartla (tokenizasyon) tahsilatı kendi tarafımızda kurmak — dönem takibi,
yenileme zamanlaması, başarısız tahsilatta yeniden deneme merdiveni ve kart
güncelleme akışı bize geçer; yani bu ADR'nin "yazmayacağız" dediği her şey.
İkincisi **alternatif sağlayıcı** (PayTR, Stripe/Türkiye çözümü, ya da kurumsal
müşteri için havale/EFT + yönetici onaylı manuel aktivasyon). Her iki yolda da
çöpe giden iş `billing/iyzico.py` ile sınırlıdır: adaptörün abonelik istek/yanıt
şeması, plan referans kodu eşlemesi ve webhook gövde ayrıştırması. Bunların
zaten **doğrulanmamış varsayımlar** olduğunu not etmek gerekir — modül kapalı
olduğu için hiçbiri gerçek bir yanıta karşı sınanamadı, dolayısıyla kaybedilen
şey doğrulanmış çalışan kod değil, yazılmış tahmin. Buna karşılık **korunan iş
çok daha büyüktür**: `BillingProvider` seam'i, `Subscription` aynası (iptal ve
planlanmış plan değişimi alanları dâhil), kota katmanı, webhook idempotency ve
sırasız-olay koruması, mutabakat görevi, dönem sonu görevi, iptal/geri alma
uçları ve arayüzü — hepsi sağlayıcıdan bağımsızdır ve olduğu gibi kalır.
Havale/EFT yolu ise zaten bu ADR'de korunmuş durumda, yani en kötü senaryoda
bile tahsilatsız kalmıyoruz.

## Geri dönüş maliyeti

**Orta.** Yol B'ye geçmek, `BillingProvider` implementasyonunu değiştirmek +
yenileme/dunning için zamanlanmış iş eklemek demektir; veri modeli
(`Subscription` aynası) ve kota katmanı **değişmez**, çünkü ikisi de zaten
sağlayıcıdan bağımsız. Uçlar ve webhook sözleşmesi de aynı kalır. Yani karar,
tersine çevrilebilir bir uygulama detayında kilitleniyor; müşteriye görünen
sözleşmede değil.
