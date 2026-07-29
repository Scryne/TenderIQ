# DURUM — çalışma günlüğü

> **Bu dosya bir sonraki oturumun TEK giriş noktasıdır.** Nerede kalındığı,
> sırada ne olduğu ve hangi süreçlerin ayakta bırakıldığı buradan okunur.
> Her madde bitiminde güncellenir.

**Son güncelleme:** 2026-07-29 · **Aktif tur:** Tur 7 — iptal/plan değişimi + webhook borcu
> Tur 7'nin iki maddesi de bitti. **Yayın engeli kalktı.**
> Sıradaki iş: **DLQ + yönetici yeniden işleme ucu**.

---

## Tur 7 — biten

| # | Madde | Durum |
|---|---|---|
| 1 | İptal + plan değişimi uçları, arayüzü ve testleri | bitti |
| 2 | `scripts/replay_billing_webhook.py` + uçta bulunan kusurun düzeltilmesi | bitti |
| — | ADR-0014'e "koşul" bölümü (modül açılmazsa ne olur) | bitti |

### Yayın engeli kalktı

`/sartlar` §3'ün üç kuralı da artık **kodda uygulanıyor ve test edilmiş**:

- **Yükseltme anında** — `request_plan_change`, sağlayıcıya `immediate=True`.
- **Düşürme dönem sonunda** — `pending_plan` + `current_period_end`; kota bu
  dönem boyunca DEĞİŞMEZ.
- **İptal dönem sonunda erişimi keser** — `cancel_at_period_end`; erişim
  ödenmiş dönemin sonuna kadar sürer, durum ACTIVE kalır.

Kullanıcı kendi iptal edebiliyor (`POST /billing/subscription/cancel`, kiracı
yöneticisi), dönem sonuna kadar geri alabiliyor (`/resume`), ve planlanmış bir
düşürmeyi de geri alabiliyor (mevcut planını yeniden seçerek).

**Kiracı sınırı yapısal:** yaşam döngüsü uçlarının hiçbiri gövdeden/yoldan
kiracı ya da abonelik kimliği ALMAZ; hepsi `principal.tenant_id` üzerinde
çalışır. "Başka kiracının aboneliğini iptal et" isteği ifade edilemez.
Sızıntı testi yine de var (`test_iptal_yalnizca_kendi_kiracisini_etkiler`).

### Tur 7'nin en önemli bulgusu

`replay_billing_webhook.py` canlı uçta **gerçek bir kusur yakaladı**: imzalı ama
**tanınmayan bir kiracı** taşıyan olay HTTP **500** döndürüyordu. Zincir şuydu —
abonelik INSERT'i yabancı anahtar kısıtına takılıyor →
`quota.get_or_create_subscription` bunu eşzamanlılık yarışı sanıp yeniden okuyor
→ bulamayınca `assert` patlıyor. Sağlayıcı 500'ü **geçici** hata sayar ve asla
başarılı olamayacak bir olayı saatlerce yeniden dener. Düzeltildi: kiracı varlığı
webhook yolunda önceden kontrol ediliyor (kalıcı 400 + `error` seviyesinde log),
ve `get_or_create_subscription` artık her `IntegrityError`'ı yarış saymıyor.
Regresyon testi: `test_webhook_bilinmeyen_kiracida_500_donmez`.

Diğer altı senaryo (geçerli imza, bozuk imza, imzasız, gövde kurcalama, tekrar
gönderim, sırasız damga) **canlı uçta geçti** — imza doğrulama, idempotency ve
sırasız-olay koruması gerçekten çalışıyor.

## ÖNCELİK SIRASI (sıradaki turlar)

1. **DLQ + yönetici yeniden işleme ucu.** Doğrulaması geçip uygulanamayan olay
   şu an kayboluyor.
2. **Olay başına e-posta bildirimi.** Şablonlar `email/templates.py`de hazır;
   webhook işleyicisine bağlanacak. (İptal/geri alma da bildirim istiyor artık.)
3. **Kiracı izolasyonu** — DLQ tablosu eklendiğinde RLS + sızıntı testi.

## Sonraki turlara ertelenenler (bilerek)

- Havale/EFT ile manuel aktivasyon yolu
- Playwright E2E (kayıt→doğrulama→giriş→panel + bekleme listesi)
- CSP'yi zorlayıcıya alma (nonce tabanlı) · Lighthouse ölçümü
- Bounce webhook'u için entegrasyon testi
- `email_suppression` kiracı-dışı kararının ADR'si + sızmama testi
- Onboarding sihirbazı + demo analiz
- J.6 ölçek korkulukları · süresi dolmuş davet temizliği

## Ayakta olan süreçler

| Ne | Kapatma |
|---|---|
| API (uvicorn, :8000 — kullanıcının kendi süreci) | `taskkill //PID 6476 //F` |
| Postgres + Redis konteynerleri | `docker compose -f infra/compose/docker-compose.yml stop postgres redis` |

> **Tur 7'de açılan geçici süreçler — HÂLÂ AYAKTA, elle kapatılmalı.**
> `:8010` ve `:8011`de ek uvicorn, `:3000`de web dev sunucusu
> (`API_URL=http://localhost:8010` ile başlatıldı). Sebep: `:8000`deki süreç
> Tur 7 kodunu servis etmiyordu (aşağıdaki reload tuzağı) ve **kullanıcının
> kendi süreci kapatılmadı**; onun yerine ayrı portta örnek açıldı.
>
> Betikle kapatılamadılar (`Stop-Process`/`taskkill` PID'i bulamıyor, port
> dinlemede kalıyor). Görev yöneticisinden ya da şu komutla kapatın:
>
> ```powershell
> Get-Process python | Where-Object { $_.Path -like '*Tender_IQ*' } | Stop-Process -Force
> ```
>
> **Dikkat:** bu komut `:8000`deki kendi sürecinizi de kapatır.

Yerel veritabanı migration'ı: `0019_subscription_lifecycle`.

## Bilinen borç / dikkat

- Hukuki metinler **taslak**; `LEGAL_TODO.md`de 12 zorunlu alan bekliyor.
- Resend'e **gerçek gönderim yapılmadı** (alan adı doğrulanmamış; hesap kullanıcıda).
- iyzico **imza şeması gerçeğe karşı doğrulandı**; abonelik istek/yanıt ŞEMASI
  hâlâ varsayım (modül kapalı, doğrulanamıyor). Tur 7'de eklenen
  `resume_subscription` (`/v2/subscription/subscriptions/activate`) ve dönem sonu
  alanı (`subscriptionNextChargeDate`) de **dokümantasyondan**.
- **Webhook olay gövdesi ve imza biçimi hâlâ doğrulanmadı** — gerçek bir olay
  alınamadı. Ama artık biçim **tek yerde**:
  `packages/core/src/tenderiq_core/billing/signature.py` (`SCHEMES`). Uç ve
  `scripts/replay_billing_webhook.py` aynı tanımı okur; gerçek olay geldiğinde
  düzeltilecek yer tek ve `verified=False` işareti oradadır.
- **iyzico olay TÜRÜ eşlemesi eksik.** `_resolve_target` bizim adlarımızı
  (`subscription.canceled`, `subscription.expired`…) bekliyor; iyzico ham
  `iyziEventType` gönderiyor ve karşılığı bilinmiyor. Gerçek olay geldiğinde
  `iyzico._to_event` içinde eşlenecek.
- ADR-0014'ün **koşulu kayda geçti**: abonelik modülü etkinleştirilemezse karar
  yeniden açılır (ADR §"Koşul").
- Başarı kontrolü HTTP durumuna GÜVENMEZ (sandbox'ta doğrulandı: geçersiz imza
  `/payment/bin/check`te HTTP 200 + gövdede "Geçersiz imza" ile geliyor).
- `BILLING_ENV=live` ikinci onay bayrağı ister; üretim tabanına çağrı hâlâ
  durma koşulu.
- Testler dış servise çıkmamalı: `conftest`te `EMAIL_PROVIDER=memory` ve
  `billing_client`ta `BILLING_PROVIDER=manual` sabitlenmiş durumda. Yeni sağlayıcı
  eklerken aynı kalıbı uygula.
- Webhook testlerinde **sabit olay kimliği kullanma** — dedup anahtarı Redis'te
  kalıcıdır, ikinci koşuda test yanlış şeyi ölçer.
- **Dönem sonu görevi bir YEDEKTİR**, kaynak değil. Normalde dönem bitişini
  sağlayıcının olayı bildirir; `apply_due_subscription_changes` (saatlik) olay
  hiç gelmezse iptali/düşürmeyi uygular. Sağlayıcıya çıkmaz, bu yüzden sağlayıcı
  kesintisinde yanlış kapatma üretemez.
- **Ortam tuzağı (yeniden doğrulandı).** Windows'ta `uvicorn --reload` olmadan
  psycopg `ProactorEventLoop` hatası veriyor. Ayrıca OneDrive altında
  watchfiles reload'ı bazen **eski bytecode'u servis etmeye devam ediyor**:
  düzeltme uygulanmış görünüp uçta eski davranış sürüyorsa süreci yeniden başlat
  (Tur 7'de bir kez bu yüzden yanlış teşhis kondu).
