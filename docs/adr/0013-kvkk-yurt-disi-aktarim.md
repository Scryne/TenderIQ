# ADR-0013: KVKK md. 9 — Yurt Dışına Aktarımın Hukuki Dayanağı: Standart Sözleşme

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-29 (Faz 4 / GA hazırlığı)
- **Karar veren:** Berkay (Scryne)
- **İlgili:** ADR-0007 (zero-retention LLM), `docs/veri-saklama-matrisi.md`, `LEGAL_TODO.md`

## Bağlam

Ürünün çekirdek işlevi, kullanıcının yüklediği şartnamenin **içeriğini** bir dil
modeli sağlayıcısına göndererek çözümlemektir. Varsayılan sağlayıcılar
(Anthropic, NVIDIA NIM) yurt dışındadır. Bu, KVKK md. 9 anlamında bir **yurt
dışına aktarımdır** ve bir hukuki dayanağa oturmak zorundadır.

7499 sayılı Kanun'la değişen md. 9, üç kademeli bir yapı kurar:

1. **Yeterlilik kararı** bulunan ülkeye aktarım (Kurul henüz yeterlilik kararı
   yayımlamadı — bu yol fiilen kapalı).
2. **Uygun güvenceler**: standart sözleşme, taahhütname, bağlayıcı şirket
   kuralları, uluslararası sözleşme.
3. **İstisnai hâller** (md. 9/6) — bunların içinde **açık rıza**, açıkça
   *"arızi olmak kaydıyla"* ifadesiyle sınırlandırılmıştır.

## Karar

**Standart sözleşme** (md. 9/3-b) birincil ve tek dayanak olarak seçildi.

### Neden açık rıza değil

Açık rıza yolu iki ayrı nedenle elverişsizdir:

1. **Arızilik şartı karşılanmıyor.** Doküman içeriği her çözümlemede, ürünün
   asli işlevinin bir parçası olarak aktarılıyor. Bu süreklilik arz eden bir
   aktarımdır; "arızi" sayılamaz. Bu şartı zorlamak, dayanağın Kurul denetiminde
   çökmesi riskini taşır.
2. **Hizmetin koşuluna bağlanmış rıza geçersizdir.** Kayıt akışına "aktarımı
   kabul ediyorum" kutusu koyup işaretlenmedikçe hizmeti vermemek, rızayı *özgür
   irade* unsurundan yoksun bırakır. Yani kutu hem gereksiz hem zararlıdır:
   kullanıcıya seçim sunuyormuş gibi görünürken hukuken hiçbir şey üretmez.

### Neden taahhütname değil

Taahhütname **Kurul izni** gerektirir; izin süreci öngörülemez ve GA takvimini
bir kurumun iş yüküne bağlar. Standart sözleşme yalnızca **bildirim** ister
(imzadan itibaren 5 iş günü). Solo-dev gerçekliğinde bu fark belirleyicidir.

## Uygulama

1. **Metinler.** `/kvkk` ve `/dpa`, aktarımı ve dayanağını açıkça yazar; alıcı
   ülke/bölge `legal.config.ts → regions.llm` alanından okunur, metne sabit
   yazılmaz.
2. **Kayıt akışı.** Hizmetin koşulu hâline getirilmiş rıza kutusu **eklenmedi**.
   Ayrılabilir/opsiyonel işlemeler (ör. ürün geliştirme amaçlı kullanım) ileride
   eklenirse, ayrı ve **varsayılanı kapalı** bir onay kutusuyla alınır.
3. **İmza + bildirim.** `LEGAL_TODO.md` §D'de adım adım yazılı; imzalı nüsha
   `/dpa` ekine konur.

## Mimari korkuluk — aktarımı tamamen kaldırabilmek

Hukuki dayanak kurmak yetmez; kurumsal müşteri "veri yurt dışına çıkmasın"
dediğinde bunun **kod değişikliği gerektirmemesi** gerekir. Bu yüzden:

- Sağlayıcı seçimi zaten yapılandırmadan geliyordu (`LLM_PROVIDER`).
- Buna **`LLM_REGION`** eklendi: sağlayıcının işleme bölgesini beyan eder ve
  hukuki metinlere aynı kaynaktan akar.
- **`LLM_ALLOW_CROSS_BORDER`** bayrağı eklendi. `false` iken, yurt dışı olarak
  işaretlenmiş bir sağlayıcıyla açılış **reddedilir** (fail-fast). Böylece
  "yalnızca yurt içi/AB" taahhüdü veren bir kurulumda, bir yapılandırma hatası
  sessizce aktarım başlatamaz.

Yerel sağlayıcı (Ollama) hattı zaten çalışır durumdadır ve `LLM_REGION=local`
ile bu modun referans uygulamasıdır.

## Alternatifler ve neden reddedildi

| Seçenek | Neden reddedildi |
|---|---|
| Açık rıza | Arızilik şartı karşılanmıyor; hizmet koşuluna bağlı rıza geçersiz |
| Taahhütname | Kurul izni gerekir; takvim öngörülemez |
| Yeterlilik kararına dayanma | Kurul henüz karar yayımlamadı |
| Yalnız yurt içi sağlayıcı (aktarımı hiç yapmama) | Bugün TR'de eşdeğer Türkçe kalitesinde yönetilen model yok; **ama seam korunuyor**, kurumsal talep gelirse yol açık |

## Geri dönüş maliyeti

**Düşük.** Karar iki yerde yaşıyor: hukuki metinler (config'ten okuyor) ve iki
ayar (`LLM_REGION`, `LLM_ALLOW_CROSS_BORDER`). Kurul yeterlilik kararı
yayımlarsa veya taahhütname yoluna geçilirse, değişen tek şey metinlerdeki
dayanak cümlesidir — veri modeli ve hat etkilenmez. Aktarımı tümüyle kaldırmak
ise bir ortam değişkeni değişikliğidir (sağlayıcı seam'i mevcut).
