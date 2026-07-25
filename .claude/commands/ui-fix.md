DESIGN.md oku. $ARGUMENTS ekranını 1440x900'de aç ve ekran görüntüsü al:

```bash
node scripts/shoot.mjs $ARGUMENTS fix
```

DESIGN.md Bölüm 5-8, 10, 12, 13'e göre denetle. Her bulgu için:
`[önem: kritik/orta/düşük] · [dosya:satır] · [ihlal] · [önerilen düzeltme]`

Bulguları önem sırasına diz ve ONAY BEKLE. Sonra sadece onaylananları, en kritikten
başlayarak düzelt. Her 3 düzeltmede bir ekran görüntüsü al ve göster.

Bitince `design/decisions.md` dosyasına bu turun kritiğini §14.4 biçiminde yaz.
