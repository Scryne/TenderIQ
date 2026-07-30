# Lighthouse erişilebilirlik skorları

> DESIGN.md §12 ve §15: **skor ≥95 olmadan bir UI görevi kapanmaz.** Bu dosya o
> eşiğin ölçüldüğü yerdir. Skorlar tarih ve yöntemle birlikte yazılır; yöntemi
> olmayan sayı karşılaştırılamaz.

## Nasıl ölçülür

```bash
# 1. ÜRETİM derlemesi (dev sunucusu ölçülmez: HMR ve kaynak haritaları skoru bozar)
pnpm --filter @tenderiq/web build
API_URL=http://127.0.0.1:8020 pnpm --filter @tenderiq/web start --port 3200

# 2. Tohum verisi (kimlikli sayfalar boş ekranla ölçülmesin)
uv run python scripts/seed_e2e.py

# 3. Ölçüm — 16 rota, kimlikli olanlar oturum çereziyle
CHROME_PATH="<playwright chromium>" \
  node scripts/lighthouse-a11y.mjs --base http://127.0.0.1:3200 --json skorlar.json
```

Betik çıkış kodu **eşiği zorlar**: bir rota 95'in altındaysa 1 döner. Kimlikli
sayfalar Playwright ile giriş yapılıp `--extra-headers` ile ölçülür — yalnız
herkese açık sayfaları ölçmek borcun büyük kısmını gizlerdi.

Araç sürümü kilitli (`lighthouse` kök `devDependencies`); `pnpm dlx` ile
koşulmaz, çünkü sürüm değişince skor sessizce kayar.

---

## 2026-07-30 · Tur 10 · ölçüm sonrası (düzeltmeler uygulanmış)

Yöntem: Lighthouse 13.4.1 · `--preset=desktop` · `--only-categories=accessibility`
· Chromium 1234 (Playwright) · üretim derlemesi `next start` :3200 · zorlayıcı
nonce CSP açık · commit: bu turun commit'i.

| Rota | Skor | Düşen denetim |
|---|---|---|
| `/` | **100** | — |
| `/login` | **100** | — |
| `/register` | **100** | — |
| `/forgot-password` | **100** | — |
| `/reset-password` | **100** | — |
| `/verify-email` | **100** | — |
| `/accept-invitation` | **100** | — |
| `/kvkk` | **100** | — |
| `/sartlar` | **100** | — |
| `/trust` | **100** | — |
| `/dpa` | **100** | — |
| `/panel` | **100** | — |
| `/tenders` | **100** | — |
| `/usage` | **100** | — |
| `/settings` | **100** | — |
| `/capability` | **100** | — |

16 rotanın tamamı 100/100, düşen denetim yok.

### Aynı gün, düzeltmelerden ÖNCEKİ ölçüm

Sayıların nereden geldiği görünsün diye ilk ölçüm de kayda geçiyor. Görev
eşiği (90) hiçbir sayfada aşılmamıştı; yani **skor bakmak yetmezdi** — üç
gerçek kusur 95–100 aralığında saklanıyordu.

| Rota | Önce | Düşen denetim |
|---|---|---|
| `/tenders` | 95 | `aria-valid-attr-value`, `label-content-name-mismatch` |
| `/usage` | 98 | `heading-order`, `label-content-name-mismatch` |
| `/settings` | 98 | `heading-order`, `label-content-name-mismatch` |
| `/capability` | 98 | `heading-order`, `label-content-name-mismatch` |
| `/panel` | 100 | `label-content-name-mismatch` (ağırlığı 0 olduğu için skoru düşürmüyordu) |
| diğer 11 rota | 100 | — |

### Bulunan üç kusur ve düzeltmesi

1. **`label-content-name-mismatch` — hesap menüsü butonu (tüm kimlikli sayfalar).**
   Butonun görünür metni kullanıcının adı ve rolüydü, erişilebilir adı ise sabit
   `aria-label="Hesap menüsü"`. WCAG 2.5.3 "Label in Name" ihlali: sesli komutla
   "Berkay" diyen kullanıcı butonu çalıştıramaz. `aria-label` kaldırıldı; amaç
   bilgisi `sr-only` metinle verildi, böylece erişilebilir ad görünen metni
   **kapsıyor**. (`components/shell/app-shell.tsx`)
2. **`heading-order` — kart başlıkları (`/usage`, `/settings`, `/capability`).**
   `CardTitle` her yerde `h3`tü; bu sayfalarda kart doğrudan sayfa başlığının
   (`h1`) altında olduğu için bir başlık kademesi atlanıyordu. `CardTitle`a `as`
   verildi (varsayılan `h3` — kartlar çoğu yerde `SectionHeader`ın (h2) altında);
   sayfa düzeyindeki kartlar `as="h2"` aldı. Görünüm seviyeden bağımsız olduğu
   için tasarım değişmedi. (`components/ui/card.tsx` + 6 çağrı yeri)
3. **`aria-valid-attr-value` — segment kontrolü (`/tenders`, inceleme ekranı).**
   Radix `Tabs`, panel olmadan segment filtresi olarak kullanılıyordu. Radix her
   tetikleyiciye `role="tab"` + `aria-controls="radix-…-content-…"` yazıyor, panel
   hiç render edilmediği için o kimlik DOM'da yoktu: hem geçersiz ARIA hem de
   ekran okuyucuya yanlış zihinsel model ("açılacak bir panel var"). DESIGN.md
   §8.11 zaten "segment sekme değildir" diyordu. `SegmentedControl` çıkarıldı
   (`role="group"` + `aria-pressed`), sınıflar `tabs.tsx`ten geldiği için görünüm
   birebir aynı kaldı. Gerçek sekmeler (`/settings`) `Tabs`ta kaldı.

### Kapsam dışı kalan

- **`/tenders/[id]` ve `/tenders/[id]/review`** ölçülmedi: ikisi de tohumdaki
  ihale kimliğine bağlı dinamik rota; betiğin rota listesi sabit. İnceleme
  ekranı ürünün çekirdek çalışma alanı olduğu için bu **açık bir borç** —
  segment düzeltmesi orayı da kapsıyor ama skoru ölçülmedi.
- Yalnız `accessibility` kategorisi ölçüldü. Performance/Best Practices ayrı bir
  iş (nonce CSP tüm rotaları dinamik render'a geçirdi; performans etkisi
  ölçülmedi).
- Lighthouse otomatik denetimler otomatikleştirilebilenlerin altını çizer:
  klavye tuzağı, odak sırası mantığı ve ekran okuyucu akışı **elle** kontrol
  gerektirir (DESIGN.md §15 "Tab ile tüm sayfa gezilebildi" maddesi).
