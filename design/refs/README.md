# Referans notları

> **DURUM: BOŞ — doldurulması gereken tek manuel adım.**
> BASLANGIÇ.md Adım 4'e göre bu klasör kalitenin ~%40'ıdır. Ajan siteyi göremez,
> link işe yaramaz — **PNG indir**.

## Nasıl doldurulur

1. Şu üç kaynaktan 5–8 ekran görüntüsü indir:
   - [refero.design](https://refero.design/) — gerçek ürün ekranları
   - [boardui.com](https://www.boardui.com/) — panel odaklı
   - [mobbin.com](https://mobbin.com/) — akış bazlı (boş durum, onboarding)
2. Bu klasöre `01-…png`, `02-…png` olarak koy.
3. Aşağıdaki listeye her biri için **ALIYORUM / ALMIYORUM** satırlarını yaz.

**Kural:** layout'u en fazla 1–2 referanstan al; gerisi detay (kart, tablo, rozet)
içindir. Aksi halde Frankenstein çıkar.

## TenderIQ için özellikle aranacak referanslar

Bu ürünün kendine özgü üç ekran problemi var; referansları buna göre seç:

| Ne aranacak | Neden |
|---|---|
| **İki bölmeli inceleme/annotation arayüzü** (sol liste ↔ sağ doküman) | `/tenders/[id]/review` — çekirdek ekran. Legal-tech, PDF review, code-review arayüzleri iyi kaynak. |
| **Kanıt/alıntı gösterimi** (kaynak referansı, sayfa vurgusu) | Ürünün tek ayırt edici vaadi. |
| **Uzun süreli işlem/pipeline durumu** | `/tenders/[id]` yükleme → ayrıştırma → çıkarım hattı. |
| **Kota / plan / kullanım ekranı** | `/usage`. |

## Referanslar

<!-- Örnek biçim — doldurunca bu yorumu sil:

- `01-<isim>.png`
  ALIYORUM: <yapı / ritim / anatomi — somut ol>
  ALMIYORUM: <renk / tipografi / layout>
-->

_(henüz referans yok)_

## Genel yön

Kanıtlı, ölçülü, hukuki-ciddi. Gösterişli efekt yok. Referanslardan yalnızca
**YAPI ve RİTİM** alınır; renk ve tipografi TenderIQ'ya özel belirlenir
(DESIGN.md §5–6, `design/decisions.md`).
