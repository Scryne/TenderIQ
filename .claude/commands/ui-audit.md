DESIGN.md dosyasını oku ve $ARGUMENTS ile belirtilen sayfayı/bileşeni Bölüm 15
Definition of Done listesine göre denetle.

Dev sunucusunun ayakta olduğunu doğrula, sonra:

```bash
node scripts/shoot.mjs $ARGUMENTS audit
```

375, 768, 1440, 1920 genişliklerindeki PNG'leri `design/shots/` altından **Read ile
gerçekten aç ve incele**. Tarayıcı konsol mesajlarını script çıktısından listele.

Çıktı: DoD listesinin her maddesi için ✅ / ❌ + ❌ olanlar için tek satır gerekçe ve
`dosya:satır` referansı.

Sonunda "Bu ekranın en zayıf 3 yanı" başlığı altında somut düzeltmeler öner.
DÜZELTME YAPMA, sadece raporla.
