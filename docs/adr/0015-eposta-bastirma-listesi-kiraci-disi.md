# ADR-0015: E-posta bastırma listesi kiracı-dışıdır

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-30
- **Karar veren:** Berkay (Scryne)

## Bağlam

`email_suppression` tablosu, kalıcı bounce (hard bounce) ya da spam şikâyeti almış
adresleri tutar. Bu tablo — ADR-0003'ün "kiracıya-özel her tablo `tenant_id` taşır ve
RLS'ye tabidir" kuralının **bilinçli bir istisnasıdır**: `tenant_id` kolonu yoktur,
RLS kapalıdır ve kayıtlar tüm kiracılar için ortaktır.

İstisnanın kayda geçmesi gerekiyordu, çünkü ADR-0003 çok-kiracılılığın en kritik
tehdidini "kiracılar arası veri sızıntısı" olarak tanımlıyor ve bu tablo tam olarak
kiracı sınırını aşan bir veri kümesi. Yazılı gerekçe olmadan, sonraki bir oturumun
"burada `tenant_id` eksik" diye onu kiracıya bağlaması ya da tersine, ortak olduğunu
bilerek bir uçtan içeriğini sızdırması muhtemeldi.

## Karar

**Bastırma listesi global kalır.** Gerekçe, korunan kaynağın kendisinin ortak
olmasıdır: gönderen alan adı ve onun itibarı (sender reputation) tüm kiracılar için
tek ve paylaşılmıştır.

Liste kiracı başına tutulursa, A kiracısının gönderiminde kalıcı bounce almış bir
adrese B kiracısı göndermeye devam eder. Sağlayıcı bounce oranını **alan adı**
düzeyinde ölçtüğü için, B'nin gönderimi A'nın da teslimat oranını düşürür ve bir süre
sonra her iki kiracının **meşru** e-postaları spam'e düşer. Yani kiracı başına
bastırma, izolasyon kazandırmaz; ortak bir kaynağı korumasız bırakır.

Adresin teslim edilemez olması, kiracı ilişkisinin değil **adresin** bir özelliğidir.

### Bunun bedeli ve onu kapatan kural

Ortak tablo, doğası gereği kiracı sınırını aşan bir bilgi taşır: "bu adres bounce
aldı" bilgisi bir kiracının gönderiminden doğar, başka bir kiracıyı da etkiler.
Bedeli şu kuralla sınırlanır:

> **Hiçbir uç, bastırma listesinin içeriğini ya da bir adresin listede olup
> olmadığını çağırana göstermez** — çağıranın kendi kayıt olmakta olduğu adres tek
> istisnadır.

Uygulamadaki karşılıkları:

1. **Davet ve üyelik uçları gönderim sonucunu ATAR.** `POST /api/v1/invitations`
   `send_email(...)` çağrısının dönüşünü kullanmaz ve `InvitationResponse` teslim
   durumu taşımaz. Taşısaydı, bir kiracının yöneticisi herhangi bir adresi davet
   ederek o adresin başka bir kiracının gönderiminde bounce alıp almadığını
   öğrenebilirdi — kiracılar arası bir gözlem kanalı.
2. **Bildirim/abonelik e-postaları da sonucu göstermez;** yalnız loglanır
   (`eposta_bastirildi`, maskeli alıcı ile).
3. **Tek istisna `POST /auth/register`in `email_delivery` alanıdır.** Burada
   gösterilir çünkü kullanıcı kendi adresini kaydediyor ve doğrulama e-postası
   gitmediyse arayüzün "adresini güncelle" diyebilmesi gerekir; aksi hâlde kullanıcı
   asla gelmeyecek bir e-postayı bekler. Bu bilgi çağıranın kendi hesabına ait
   olduğu için kiracılar arası bir gözlem değildir.
4. **Operatör uçları listeyi yayımlamaz.** `/ops/*` altında bastırma listesini
   listeleyen bir uç yoktur; eklenirse kiracı belirteciyle değil operatör
   belirteciyle korunur.

Bu kurallar `apps/api/tests/integration/test_email_suppression_leak.py` ile
kilitlenmiştir: davet ucunun yanıtında teslim durumu belirirse test kırılır.

## Sonuçlar

**Olumlu:** Gönderen itibarı tek noktadan korunur; aynı adres için tekrarlayan
bounce üretilmez; kural testle zorlanabilir hâle geldi.

**Ödünler:**

- Bir kiracının gönderiminden doğan bastırma, diğer kiracıları da etkiler: A'nın
  yanlış yazılmış adresi bounce alırsa, aynı adresi doğru sahibiyle kullanan B'ye de
  otomatik gönderim yapılmaz. Bu, `manual_retry` ile açıkça aşılabilir
  (`send_email(..., manual_retry=True)`) — yani kullanıcının açık isteği bastırmayı
  geçebilir, sistemin kendiliğinden yeniden denemesi geçemez.
- Adres bir kez bastırıldığında geri alma yolu şu an yalnız elle (DB) mevcut.
  Destek akışı gerektiğinde ayrı bir operatör ucu açılacak.

## Alternatifler

- **`tenant_id` + RLS ile kiracı başına bastırma:** ADR-0003 kalıbına uyar ama ortak
  kaynağı (alan adı itibarı) korumaz — asıl amacı ıskalıyor. Reddedildi.
- **Sağlayıcının kendi bastırma listesine güvenmek (Resend/SES tarafında):** Sağlayıcı
  değiştiğinde liste taşınmaz ve `EmailOutcome.SUPPRESSED` gibi ürün davranışı
  sağlayıcıya bağımlı hâle gelir. Reddedildi; sağlayıcı listesi ek bir katman olarak
  yine çalışır.
- **Hiç bastırma listesi tutmamak:** Kalıcı bounce'a yeniden göndermek gönderen
  itibarını düşürür (Tur 4'te otomatik yeniden deneme tam bu yüzden kaldırıldı).
  Reddedildi.

## İlgili

ADR-0003 (RLS çok-kiracılılık — bu ADR onun bilinçli istisnasıdır) ·
`packages/core/src/tenderiq_core/models/email_suppression.py` ·
`apps/api/src/tenderiq_api/routers/v1/email_webhook.py` · `docs/ops/email-setup.md`
