DESIGN.md dosyasını baştan sona oku, `design/refs/` görsellerini ve README.md
notlarını incele, `design/decisions.md`'deki geçmiş kararları oku.

GÖREV: $ARGUMENTS sayfasını tasarla ve kodla.

ÇALIŞMA SIRASI — bu sırayı bozma:

═══ 1. PLAN (henüz kod yazma) ═══
- Bu sayfa hangi tek soruyu 5 saniyede cevaplamalı?
- Bilgi hiyerarşisi: 1., 2., 3. seviye ne? Neyi büyük, neyi küçük yapıyorum?
- ASCII wireframe çiz.
- DESIGN.md Bölüm 8'den hangi bileşen spec'lerini kullanacağım? (numara ver)
- Kullanacağım token'ları listele.
- SIGNATURE: bu sayfayı akılda kalıcı yapacak TEK öğe ne?

═══ 2. ÖZ-ELEŞTİRİ (planı göstermeden önce, kendin) ═══
Her kararı sor: "Bu kararı herhangi bir dashboard için de verir miydim?" Evet ise o
karar bir DEFAULT'tur, seçim değil. Değiştir ve neyi neden değiştirdiğini yaz.
Sonra planı göster ve ONAY BEKLE.

═══ 3. KOD ═══
- shadcn MCP ile bileşen YAPISINI al; STİLİNİ DESIGN.md'den ver.
- Gerçekçi Türkçe veri. Lorem ipsum ve "Company A" yasak. KVKK: gerçek şartname yok.
- 5 durumu da kodla: dolu / boş / filtre-boş / yükleniyor / hata.

═══ 4. GÖRSEL DOĞRULAMA — ATLANAMAZ (§14) ═══
`node scripts/shoot.mjs <rota> <etiket>` → PNG'leri Read ile aç ve her biri için
"İyi olan 2 şey" / "Kötü olan EN AZ 3 şey" yaz. Bölüm 13 yasak listesini madde madde
geç. Düzelt, tekrar çek. EN AZ 2 TUR. Konsolda 0 hata.

═══ 5. KAPANIŞ ═══
Bölüm 15 DoD listesini doldur; `design/decisions.md`'ye turun kritiğini yaz.

Kırmızı çizgiler: DESIGN.md Bölüm 4 `kirmizi_cizgiler` — bağlayıcı.
