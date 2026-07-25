# CLAUDE.md — TenderIQ

## Frontend kuralları — ATLANAMAZ

UI/frontend içeren HER görevde, kod yazmadan önce `DESIGN.md` dosyasını baştan sona
oku ve `design/refs/README.md` içindeki referans notlarını incele.

- `DESIGN.md` Bölüm 13 (Anti-slop) ve Bölüm 14 (Görsel doğrulama döngüsü) atlanamaz.
- Görev, Bölüm 15'teki Definition of Done listesi doldurulmadan "bitti" sayılmaz.
- Her UI görevinin sonunda `design/decisions.md` güncellenir.
- Doldurulmuş BRIEF `DESIGN.md` Bölüm 4'tedir; `kirmizi_cizgiler` bağlayıcıdır.

### Görsel doğrulama nasıl çalıştırılır

`chrome-devtools` MCP bu projede kurulu değil. Yerine kurulu Playwright kullanılır:

```bash
pnpm --filter @tenderiq/web dev        # ayrı terminalde, :3000
node scripts/shoot.mjs <rota> [etiket] # 375/768/1440/1920 → design/shots/
```

Alınan PNG'ler **gerçekten okunur** (Read tool görseli gösterir), her viewport için
ayrı kritik yazılır. En az 2 tur (DESIGN.md §14.1).

## Genel proje kuralları

- Türkçe biçimlendirme `Intl.*` ile yapılır; elle biçimlendirme yok (DESIGN.md Ek B).
- Frontend backend'e yalnız `@tenderiq/api-client` üzerinden erişir (tip-güvenli sözleşme).
- 21st.dev Magic MCP gibi harici kod üreten araçların çıktısı commit'lenmeden önce
  okunur (prompt injection riski — DESIGN.md §2.4).
- `next build`, dev sunucusu ayaktayken **çalıştırılmaz** (`.next` bozulur).
