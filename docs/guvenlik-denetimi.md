# Güvenlik Öz-Denetimi (OWASP ASVS-hafif)

> **Tur:** #1 · **Tarih:** 2026-07-28 · **Denetleyen:** Berkay + Claude
> **Kapsam:** `apps/api`, `apps/worker`, `apps/web`, `packages/core` — tüm kod tabanı
> **Plan referansı:** `GELISTIRME_PLANI.md` Faz 4 (Güvenlik gözden geçirmesi) + J.2

Bu belge bir kerelik rapor değil, **tekrarlanan bir turun kaydı**dır. Her tur
aynı bölümleri gezer; bulgular ya kapatılır ya da "kabul edilen risk" olarak
gerekçesiyle yazılır. Kapatılan bulgunun **regresyon testi olmak zorundadır** —
aksi hâlde bir sonraki turda yeniden bulunur.

## 1. Bu turda bulunan ve kapatılan açıklar

### B-1 · Excel dışa aktarımında formül enjeksiyonu — **Yüksek**

`build_xlsx_report` hücreleri saldırgan kontrolündeki metinden gelir: içerik
müşterinin yüklediği **üçüncü-taraf şartnameden** çıkarılır ve alıntılar birebir
taşınır. openpyxl (3.1), `=` ile başlayan bir string'i sessizce **formül** olarak
işaretler (`data_type='f'`); `#REF!` gibi değerleri de hata hücresine çevirir.

*Etki:* Şartnameye `=cmd|'/c ...'!A0` gömen biri, raporu açan **satın alma
yetkilisinin makinesinde** DDE tetikleyebilir; `=WEBSERVICE(...)` ile rapor
içeriğini dışarı sızdırabilir. Ürünün asıl kullanım biçimi tam olarak budur:
dış kaynaklı belgeyi analiz edip Excel'e aktarıp paylaşmak.

*Düzeltme:* `_write_row` metin hücrelerinin tipini `s`'ye sabitler. **İçerik
değiştirilmez** (kesme işareti eklenmez) — bu ürün alıntı sadakati üzerine kurulu.

*Regresyon:* `test_xlsx_hicbir_hucre_formul_olarak_yazilmaz`,
`test_xlsx_icerik_degistirilmeden_korunur`.

### B-2 · Güvenlik başlıkları hiç gönderilmiyordu — **Orta**

Ne web (Next) ne API yanıtları `nosniff`, `X-Frame-Options`, `Referrer-Policy`,
CSP veya HSTS taşıyordu (J.1 açık maddesi).

*Düzeltme:*
- **Web:** `next.config.ts → headers()` — CSP **rapor modunda**
  (`Content-Security-Policy-Report-Only`), `X-Frame-Options: DENY`, `nosniff`,
  `Referrer-Policy`, `Permissions-Policy`, `COOP`; HSTS yalnız production'da.
  CSP `connect-src`i env'den beslenir (`NEXT_PUBLIC_STORAGE_ORIGIN`, Sentry),
  çünkü PDF baytları tarayıcıya doğrudan nesne depolamadan iner.
- **API:** `SecurityHeadersMiddleware` — `nosniff`, `X-Frame-Options` (`/docs`
  clickjacking'i), `Referrer-Policy` ve yanıt kendi değerini vermediyse
  `Cache-Control: no-store` (kiracı verisi ara belleklerde kalmasın).

*Neden rapor modu:* Next'in hidrasyon betikleri satır içidir; zorlayıcı CSP
nonce ister ve her sayfayı dinamik render'a zorlar. Önce ihlalleri görüyoruz.
**Zorlayıcı moda geçiş GA kontrol listesindedir.**

*Regresyon:* `apps/api/tests/test_security_headers.py`.

### B-3 · E-posta doğrulaması hiçbir yerde zorlanmıyordu — **Orta**

`email_verified` yalnızca **gösteriliyordu**; hiçbir uç onu kontrol etmiyordu.

*Etki:* Herhangi biri **başkasının e-posta adresiyle** hesap açıp doküman
yükleyebilir; OCR + LLM maliyetini üretir, ücretsiz kotayı harcar ve adresin
sahibi olan biteni yalnızca istemediği bir doğrulama e-postasından anlar.

*Düzeltme:* `require_verified_email` bağımlılığı + `REQUIRE_VERIFIED_EMAIL`
ayarı. Kapı **yalnız maliyet doğuran işlemde** (doküman kaydı açma) durur;
okuma yolları açık kalır — ürünü tamamen kilitlemek doğrulanmamış davetli
kullanıcıyı da dışarıda bırakırdı. Production'da açık olmak **zorundadır**
(açılışta fail-fast, mevcut `manual` ödeme / `logging` e-posta kalıbıyla aynı).
Kontrol token claim'inden değil **DB'den** okunur: doğrulamayı az önce yapan
kullanıcı token'ının dolmasını beklemez.

*Regresyon:* `apps/api/tests/integration/test_verified_email_gate.py` (4 test),
`test_production_rejects_unverified_email_uploads`.

### B-4 · Erişim token'ı ömrü yetki iptalini 1 saat geciktiriyordu — **Orta**

Rol ve kiracı JWT'nin **içinde** taşınır ve her istekte DB'den doğrulanmaz. Yani
bir üyeyi organizasyondan çıkarmak veya yönetici yetkisini almak, elindeki token
dolana kadar **fiilen etkisizdi** (60 dk).

*Düzeltme:* `ACCESS_TOKEN_EXPIRE_MINUTES` 60 → **15**. Kullanıcı bunu hissetmez:
web proxy'si 401'de refresh token'la sessizce yeniler. Alternatif (her istekte
DB'den rol okuma) istek başına ekstra sorgu maliyeti getirirdi; 15 dk, iptal
gecikmesinin **belgelenmiş üst sınırıdır**.

*Regresyon:* `test_erisim_tokeni_kisa_omurlu`.

### B-5 · `refresh`, organizasyonun kapatılmış olmasını denetlemiyordu — **Düşük**

`login` ve `switch-org` üyeliği `Organization` ile join'leyerek yumuşak silme
filtresini devreye sokuyordu; `refresh` join'siz sorguluyordu.

*Etki (derinlemesine savunma):* Hesap kapatma akışı oturumları iptal ettiği için
aktif bir sömürü yolu yok. Ama iptal herhangi bir nedenle eksik kalırsa (elle
`deleted_at` işaretlemesi, ileride eklenecek başka bir kapatma yolu) o refresh
token rotasyonla **süresiz** yaşardı.

*Düzeltme:* Aynı join `refresh`e de eklendi — üç yol artık aynı sözleşmede.

### B-6 · `/panel` yönlendirme kapsamının dışındaydı — **Düşük**

Next middleware'inin korumalı yol listesi `/panel`i içermiyordu; oturumsuz
kullanıcı boş bir panele düşüyordu (gerçek yetkilendirme API'de olduğundan veri
sızıntısı yok — yalnızca kırık deneyim).

*Düzeltme:* `/panel` hem `isProtected` hem `matcher` listesine eklendi.

## 2. Denetlenen ve temiz bulunan alanlar

| ASVS bölümü | Kontrol | Durum |
|---|---|---|
| V2 Kimlik | Argon2 (`pwdlib`), parola min. 8, kullanıcı numaralandırmasına karşı sabit-zamanlı sahte hash | ✅ |
| V2 Kimlik | Giriş/kayıt/parola-sıfırlama oran sınırı (IP 20 + e-posta 5 / 5 dk), fail-open ama denetlenmiş | ✅ |
| V3 Oturum | Refresh token tek-kullanımlık + rotasyon + aile iptali (reuse-detection); Redis kesintisinde **fail-closed** | ✅ |
| V3 Oturum | Token'lar `httpOnly` + `SameSite=Lax` + prod'da `Secure`; tarayıcı JWT'yi hiç görmez (aynı-origin proxy) | ✅ |
| V4 Erişim | PostgreSQL RLS + `app.current_tenant` transaction-local GUC; uygulama non-superuser rolle bağlanır | ✅ |
| V4 Erişim | RBAC `require_role`; kiracılar arası izolasyon gerçek DB ile test ediliyor | ✅ |
| V5 Doğrulama | SQLAlchemy parametreli sorgular; ham SQL yalnız GUC ayarında ve bind parametreli | ✅ |
| V5 Doğrulama | Yükleme: içerik türü allowlist + **magic byte** doğrulaması + boyut tavanı; red → nesne silinir | ✅ |
| V5 Doğrulama | `safe_key_component` yol geçişini (`../`) depolama anahtarından temizler | ✅ |
| V7 Loglama | Yapılandırılmış log + korelasyon kimlikleri; **PII statik kapısı** (`test_log_pii.py`) | ✅ |
| V7 Loglama | Sentry `send_default_pii=False` + `before_send` scrub (gövde/cookie/sorgu dizesi gitmez) | ✅ |
| V8 Veri | Zero-retention LLM (ADR-0007); Langfuse'a varsayılan olarak istem/çıktı gitmez | ✅ |
| V9 İletişim | Webhook HMAC-SHA256 + `compare_digest`; **sır yoksa fail-closed**; Redis ile idempotency | ✅ |
| V11 İş mantığı | Kota aşımında 402; `Idempotency-Key` kiracı kapsamlı | ✅ |
| V12 Dosya | Nesne erişimi yalnız **imzalı, süreli** URL; doğrudan bucket erişimi yok | ✅ |
| V13 API | Açık yönlendirme savunması (`next` yalnız site-içi yol); CORS allowlist | ✅ |
| V14 Yapılandırma | Production fail-fast (AUTH_SECRET, DEBUG, ödeme/e-posta sağlayıcı, e-posta doğrulama) | ✅ |
| V14 Yapılandırma | CI'da `gitleaks` + `pip-audit` + Trivy + Dependabot, **bloke edici** (J.2 #7) | ✅ |
| Token entropisi | Refresh/davet/tek-kullanımlık token'lar `secrets.token_urlsafe(32)` = 256 bit | ✅ |
| XSS | `dangerouslySetInnerHTML`/`eval` kullanımı **yok**; React varsayılan kaçışı | ✅ |

## 3. Kabul edilen riskler (gerekçeli)

1. **JWT durumsuzdur; iptal 15 dakikaya kadar gecikir.** Anlık iptal, istek
   başına bir Redis/DB okuması demektir. Kapalı beta ölçeğinde 15 dk penceresi
   kabul edildi. GA'da kiracı bazlı "oturum epoch"u değerlendirilecek.
2. **Oran sınırlaması yalnız kimlik uçlarında.** Pahalı uçlarda (yükleme, export)
   kota/plan sınırı iş katmanında zaten var; istek-frekansı sınırı J.6 "kuyruk
   adaleti" maddesine bağlandı.
3. **CSP zorlayıcı değil, rapor modunda.** Gerekçe B-2'de.
4. **`'unsafe-inline'` script-src'de.** Next hidrasyonu nonce'a geçilene dek.

## 4. Bu turda YAPILMAYAN, dışarıdan gelmesi gereken kontroller

- **Üçüncü-taraf hafif pentest** (plan: bütçeye göre) — yapılmadı.
- **TLS/HSTS canlı doğrulaması** — staging/prod alan adı yok (J.1).
- **Dependency güncellemesi sonrası yeniden tarama** — Dependabot açık; her PR'da CI koşar.

## 5. Sonraki tur ne zaman

- GA öncesi (J.5 kontrol listesi kapanırken) **zorunlu**.
- Kimlik, yetkilendirme, dosya yükleme veya ödeme yüzeylerinde bir değişiklik
  olduğunda o yüzey için kısmi tur.
