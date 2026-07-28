# Veri Saklama Matrisi

> **Durum:** taslak · **Son güncelleme:** 2026-07-28 · **Sahibi:** Berkay (Scryne)
>
> KVKK md. 7 ve md. 11 kapsamında "hangi veri, ne kadar süreyle, hangi mekanizmayla
> silinir" sorusunun tek cevabı bu tablodur. Plan referansı: `GELISTIRME_PLANI.md`
> J.3 ve F bölümü. **Bu belge sözleşme eklerine (DPA) girer** — hukuk onayından
> geçmeden yayımlanmamalıdır.

## 1. Silme mekanizmaları

| Mekanizma | Ne yapar | Nerede |
|---|---|---|
| **Yumuşak silme** | `deleted_at` işaretlenir; kayıt tüm okuma yollarından anında düşer. Nesne depolamadaki dosyaya dokunulmaz. | `tenderiq_core.db.soft_delete` (otomatik filtre), `DELETE /api/v1/tenders/{id}`, `DELETE /api/v1/documents/{id}` |
| **Geri alma** | Saklama penceresi içinde yumuşak silmeyi iptal eder. Yalnız ihaleyle birlikte silinen dokümanları geri açar (`deleted_with_tender`). | `POST /api/v1/tenders/{id}/restore` |
| **Hesap kapatma (md. 7)** | Organizasyon + tüm içeriği işaretlenir, üyelerin oturumları iptal edilir, bu organizasyona giriş kapanır. | `POST /api/v1/organizations/current/close` (yönetici + slug onayı) |
| **Veri sahibi erişimi (md. 11)** | Kişisel verinin ve kiracı envanterinin makine-okunur (JSON) kopyası. | `GET /api/v1/organizations/current/export` |
| **Kalıcı silme (purge)** | Saklama penceresi dolunca **önce nesne depolamadaki dosyalar, sonra DB satırları** silinir. Alt tablolar FK `ON DELETE CASCADE` ile gider. Kapatılmış hesaplarda ayrıca üyelik/davet/yetkinlik profili silinir ve organizasyon anonimleştirilir. | `data.purge_deleted` Celery beat işi (günde bir) |

**Kritik sıra kuralı:** nesne depolama silinemezse DB satırı **bırakılır** ve bir
sonraki koşuda yeniden denenir. Tersi yapılsaydı `storage_key` kaybolur ve dosya
depoda sonsuza dek yetim kalırdı — "sildim" beyanı yanlış olurdu.

## 2. Saklama süreleri

Yapılandırma: `DATA_RETENTION_DAYS` (varsayılan **30 gün**).

| Veri sınıfı | Tablo / konum | Saklama | Silme mekanizması |
|---|---|---|---|
| İhale projesi | `tender` | Silinene dek; silme sonrası 30 gün | Yumuşak → purge |
| Yüklenen doküman (dosya) | Cloudflare R2 | İhale/doküman silinene dek; sonra 30 gün | Purge (R2 `delete_object`) |
| Doküman kaydı | `document` | İhale ile aynı | CASCADE (tender) veya doğrudan purge |
| Ayrıştırılmış öğeler | `parsed_element` | Doküman ile aynı | CASCADE |
| Chunk | `chunk` | Doküman ile aynı | CASCADE |
| Vektör (embedding) | `embedding` | Chunk ile aynı | CASCADE (chunk) |
| Çıkarılmış bulgular | `requirement`, `deliverable`, `risk_flag`, `timeline_event`, `compliance_result` | İhale ile aynı | CASCADE |
| Bulgu yorumları | `finding_comment` | İhale ile aynı | CASCADE |
| İşleme işi kaydı | `job` | Doküman ile aynı | CASCADE |
| Kullanım kaydı (kota) | `usage_record` | **Faturalama gereği saklanır** — dönem kapandıktan sonra 10 yıl (VUK) | Ayrı; ihale silmesinden etkilenmez |
| Abonelik | `subscription` | Hesap kapanana + 10 yıl (VUK) | Ayrı |
| Denetim kaydı | `audit_log` | **En az 1 yıl** (kurumsal satış/güvenlik gereği); kalıcı silme kaydı dâhil | Ayrı; silinen kaydın kanıtıdır |
| Organizasyon (mezar taşı) | `organization` | **Süresiz** — anonimleştirilmiş (ad/slug) hâlde kalır; fatura ve denetim kayıtlarının FK hedefi | Anonimleştirme (kalıcı silinmez) |
| Kullanıcı hesabı | `user_account` | Son üyeliği kalkana dek; hesap kapatmada başka üyeliği yoksa **silinir** | Hesap kapatma süpürmesi |
| Üyelik | `membership` | Organizasyon kapatılana dek | Hesap kapatma süpürmesi · CASCADE (kullanıcı) |
| Davet | `invitation` | Organizasyon kapatılana dek | Hesap kapatma süpürmesi · *(süresi dolmuşların otomatik temizliği yok — bkz. Açık uçlar)* |
| Yetkinlik profili | `capability_profile` | Organizasyon kapatılana dek | Hesap kapatma süpürmesi |
| Oturum (refresh token) | Redis | TTL (kısa ömürlü); logout'ta anında iptal | TTL + `revoke_all_for_user` |
| Tek kullanımlık token (doğrulama/sıfırlama) | Redis | TTL; ilk kullanımda atomik tüketim | TTL / GETDEL |
| Oran sınırlama sayaçları | Redis | Pencere süresi (300 sn) | TTL |
| Yapılandırılmış loglar | Log altyapısı | ≥ 30 gün (J.4) | Log rotasyonu · PII yerine korelasyon kimliği (statik kapı: `test_log_pii.py`) |
| Operasyon metrikleri | Redis (`ops:*`) | 25 saat (TTL) | TTL; kişisel veri değil, kurulum geneli sayaç |
| LLM istemleri/çıktıları | Sağlayıcı | **Sıfır saklama (zero-retention)** — ADR-0007 | Sağlayıcı tarafında saklanmaz |

## 3. LLM ve alt-işleyenler

ADR-0007 gereği LLM sağlayıcısıyla **zero-retention + no-training** yapılandırması
zorunludur. Doküman içeriği sağlayıcıda kalıcı olarak saklanmaz; bu nedenle
"silme" talebi LLM sağlayıcısına ayrıca iletilmez. Alt-işleyen listesi trust
sayfasında yayımlanır.

## 4. KVKK md. 7 (silme) ile VUK (saklama) çakışması

Hesap kapatıldığında **organizasyon satırı kalıcı olarak silinmez**. Sebebi teknik
değil hukukidir: `subscription`, `usage_record` ve `audit_log` kayıtları
`organization.id`'ye `ON DELETE CASCADE` ile bağlıdır ve fatura/defter kayıtlarının
VUK gereği 10 yıl saklanması zorunludur. KVKK md. 7, **kanuni saklama yükümlülüğü
bulunan veriyi silme hakkının istisnası** sayar.

Uygulanan çözüm:

| Ne olur | Neden |
|---|---|
| İhale, doküman, bulgu, chunk, embedding, yorum, dosya → **kalıcı silinir** | Kişisel veri / müşteri içeriği |
| Üyelik, davet, yetkinlik profili → **kalıcı silinir** | Kişisel veri |
| Başka üyeliği kalmayan kullanıcı hesabı → **kalıcı silinir** | Kişisel veri; işleme sebebi kalmadı |
| Organizasyon adı/slug → **anonimleştirilir** (`Kapatılmış organizasyon` / `deleted-<uuid>`) | Ticari unvan kişisel veri sayılabilir |
| `subscription`, `usage_record` → **korunur** | VUK 10 yıl |
| `audit_log` → **korunur** (`actor_user_id` kullanıcı silinince `NULL` olur) | Kanuni/kurumsal denetim; kim olduğu anonimleşir |

> Bu istisna **aydınlatma metninde açıkça beyan edilmelidir**: "hesabınızı
> kapatsanız da fatura kayıtlarınız vergi mevzuatı gereği 10 yıl saklanır."

## 5. Açık uçlar — GA öncesi kapatılmalı

1. **Süresi dolmuş davetler için otomatik temizlik yok.** Geçersiz sayılıyor ama
   satır duruyor; kapatılmayan hesaplarda birikir.
2. ~~**Log PII maskelemesi doğrulanmadı.**~~ **Kapandı (2026-07-28).** Denetim
   statik bir kapıya bağlandı: `packages/core/tests/test_log_pii.py` tüm log
   çağrılarını AST ile tarar, PII taşıyabilecek alan adlarını (`email=`, `body=`,
   `text=`, `token=`…) ve f-string olay adlarını reddeder. Denetimde bulunan
   gerçek sızıntı kapatıldı: e-posta sağlayıcı uyarısı alıcı adresini düz metin
   logluyordu → `logging.mask_email` (`b***@example.com`). Bilinçli tek istisna
   (dev'e özel `hesap_epostasi` kaydı) gerekçesiyle listelenmiştir. Ayrıntı:
   `docs/slo.md` §6.
3. **R2 bucket versioning + yaşam döngüsü kuralları kurulmadı** (J.3). Versioning
   açıksa `delete_object` eski sürümü bırakabilir — hard-delete ile uyumu
   yapılandırma seviyesinde doğrulanmalı. **Bu, "sildim" beyanını doğrudan
   etkilediği için en öncelikli açık uçtur.**
4. **Hesap kapatmanın geri alma ucu yok** (bilinçli). Yanlışlıkla kapatılan hesap
   saklama penceresi içinde elle (`organization.deleted_at = NULL`) geri alınır.
   **Runbook'a yazıldı (2026-07-28):** `docs/runbook.md` §6 — adım adım SQL,
   süpürme koştuysa geri dönüşün olmadığı uyarısı ve `audit_log` teyidi dâhil.
5. **Dışa aktarma tek organizasyon kapsamlıdır.** Çok org'lu kullanıcı her biri
   için ayrı çağırır; RLS kiracı bağlamını delmemek için bilinçlidir.

## 5. Doğrulama

Silme akışının davranışı `apps/api/tests/integration/test_deletion_flow.py`
altında sınanır: yumuşak silmenin tüm okuma yollarından düşürmesi (liste, detay,
bulgular, doküman listesi, **imzalı dosya URL'i**, panel, export), geri alma,
CASCADE ile alt tabloların gitmesi, nesne silinemediğinde satırın korunması ve
kiracılar arası izolasyon.
