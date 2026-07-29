# LEGAL_TODO — hukuki metinlerde doldurulacaklar

> **Sahibi:** Berkay (Scryne) · **Son güncelleme:** 2026-07-29
>
> Bu dosya, hukuki sayfaların (`/kvkk`, `/sartlar`, `/trust`, `/dpa`) yayına
> çıkabilmesi için **yalnızca sende bulunan** bilgileri listeler. Hepsi tek bir
> yerden okunur: `apps/web/src/config/legal.config.ts`.
>
> **Örnek/uydurma değer yazma.** Aydınlatma metnindeki sahte bir VKN, boş
> bırakmaktan ağırdır: doğru göründüğü için kimse fark etmez. Eksik alan varken
> sayfalar amber bir taslak bandı gösterir ve o bant **elle kapatılamaz** —
> `isLegalDraft()` doğrudan bu dosyadaki alanlardan türetilir.

Durumu her an şöyle görebilirsin:

```bash
grep -n "undefined" apps/web/src/config/legal.config.ts
```

---

## A. Kurumsal kimlik — `LEGAL_CONFIG.company`

| Alan | Ne isteniyor | Nereden alınır |
|---|---|---|
| `tradeName` | Ticaret sicilindeki **tam unvan** (ör. "… Yazılım Anonim Şirketi") | Ticaret sicil gazetesi / faaliyet belgesi |
| `address` | Tebligata elverişli açık adres | Ticaret sicil kaydı |
| `city` | Merkezin bulunduğu il | Ticaret sicil kaydı — **yetkili mahkeme bundan türetilir**, metne şehir yazılmaz |
| `taxId` | Vergi kimlik numarası (VKN) | Vergi levhası |
| `mersis` | Mersis numarası | Ticaret sicil kaydı (opsiyonel; boşsa cümle o alanı atlar) |
| `kep` | Kayıtlı elektronik posta adresi | KEP hizmet sağlayıcısı (PTT/TürkKep vb.) |
| `contactEmail` | Genel iletişim adresi | Kendi belirleyeceğin adres |
| `privacyEmail` | **KVKK md. 11 başvuru adresi** | Ayrı bir kutu önerilir (ör. `kvkk@…`) |
| `securityEmail` | Güvenlik açığı bildirimi (opsiyonel) | Ör. `guvenlik@…` |
| `salesEmail` | Kurumsal/SLA talepleri (opsiyonel) | Ör. `satis@…` |

## B. İşleme bölgeleri — `LEGAL_CONFIG.regions`

Bunlar dağıtım kararına bağlıdır; barındırma seçilince (J.1) netleşir.

| Alan | Ne isteniyor |
|---|---|
| `hosting` | Uygulama + veritabanının barındırıldığı bölge (ör. "Frankfurt, Almanya (AB)") |
| `objectStorage` | Cloudflare R2 bucket bölgesi / yer kısıtı |
| `llm` | Çözümleme sağlayıcısının işleme bölgesi (bkz. ADR-0013) |
| `email` | İşlemsel e-posta sağlayıcısının bölgesi (opsiyonel) |

> Alt işleyen **listesi** doldurulmana gerek yok: `SUB_PROCESSORS` koddaki
> gerçek bağımlılıklardan türetildi (boto3/R2, sentry-sdk, anthropic/openai/
> ollama, langfuse, `*_PROVIDER` anahtarları). Sen yalnız bölgeleri ve
> yapılandırmayla seçilen sağlayıcı adlarını verirsin.

## C. VERBİS — `LEGAL_CONFIG.verbisStatus`

Metin üç duruma göre kendini değiştirir; senin yapman gereken **durumu
belirlemek**:

- `"kayitli"` → sicile kayıt yapıldı,
- `"muaf"` → eşiklerin altında kalındı,
- `"belirlenmedi"` → **varsayılan**, sayfada amber uyarı gösterilir.

**Nasıl karar verilir:** yıllık çalışan sayısı **50'den çok** *veya* yıllık mali
bilanço toplamı **25 milyon TL'den çok** ise kayıt yükümlülüğü doğar; ana
faaliyeti özel nitelikli kişisel veri işlemek olanlar eşiksiz yükümlüdür.

> **Yapılacak:** mali müşavirinle son yıl bilanço ve çalışan sayısını teyit et,
> sonucu bu alana yaz. Eşik aşılıyorsa VERBİS kaydını yap ve `"kayitli"` seç.

## D. Yurt dışına aktarım — standart sözleşme (ADR-0013)

Karar verildi: **standart sözleşme** yolu kullanılıyor (açık rıza değil).
Uygulanması için gereken adımlar:

1. LLM sağlayıcısı ve bölge seçilir (`LLM_PROVIDER`, `LLM_REGION`).
2. Kurul'un yayımladığı **veri sorumlusundan veri işleyene** standart sözleşme
   metni, sağlayıcıyla (veya kurumsal müşteriyle) imzalanır.
3. İmza tarihinden itibaren **5 iş günü içinde** Kurum'a bildirilir.
4. İmzalı nüsha `/dpa` ekine konur.

> **Yapılacak:** 2-3. adımlar; imza tarihini ve bildirim referansını sakla.

## E. e-Arşiv / e-Fatura entegrasyonu (YAPILMADI — sıradaki tur)

**iyzico fatura kesmez.** Ödeme alındığında Türkiye'de fatura düzenleme
yükümlülüğü doğar (VUK); bu ayrı bir entegratör gerektirir (Paraşüt, Birfatura,
Logo İşbaşı vb.). Kod tarafında `InvoiceProvider` seam'i **henüz yazılmadı**.

> **Yapılacak (sen):** entegratör seç ve hesap aç. Mükellefiyet türüne göre
> e-Fatura (mükellefe) / e-Arşiv (mükellef olmayana) ayrımı gerekir; entegratör
> bunu GİB mükellef sorgusuyla çözer.
>
> **Yapılacak (kod, sıradaki tur):** `InvoiceProvider` arayüzü + no-op
> implementasyon + ödeme başarılı olayına bağlanması.

## F. Hukuk onayı — `LEGAL_CONFIG.reviewedByCounsel`

Metinler sistemin gerçeğine göre yazıldı (VUK×KVKK çakışması, 30 günlük saklama
penceresi, RLS izolasyonu, sıfır saklama yapılandırması — hepsinin kodda
karşılığı var). Ama **hukuki onay verilemez, alınır**.

> **Yapılacak:** dört metni bir avukata okut; onay alınınca bu alanı `true` yap.
> Bu alan `false` olduğu sürece taslak bandı kalkmaz.

---

## Senin kararına bırakılmayanlar (bilgi için)

Aşağıdakiler ürün kararı sayıldı ve `LEGAL_TERMS` içinde sabitlendi; istersen
değiştir, metinler otomatik uyar:

| Konu | Karar |
|---|---|
| Cayma hakkı | 14 gün koşulsuz; kullanılan dönem oransal düşülür, yıllıkta ilk 14 gün tam iade |
| Hizmet seviyesi | GA öncesi **hedef**, taahhüt değil, tazminat doğurmaz; kurumsalda ayrı SLA ekine dönüşür |
| Veri ihlali bildirimi | 24 saat içinde veri sorumlusuna; Kurul'a bildirim müşteride |
| Alt işleyen değişikliği | 30 gün önceden bildirim, itiraz hakkı, itirazda cezasız fesih |
| Denetim | Yılda 1 kez, 30 gün önceden; bağımsız denetim raporuyla ikame edilebilir |
| Yetkili mahkeme | Şirket merkezinin bulunduğu yer (şehirden türetilir) |
| Sorumluluk tavanı | Son 12 ayda ödenen abonelik bedeli |
