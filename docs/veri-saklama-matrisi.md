# Veri Saklama Matrisi

> **Durum:** taslak · **Son güncelleme:** 2026-07-25 · **Sahibi:** Berkay (Scryne)
>
> KVKK md. 7 ve md. 11 kapsamında "hangi veri, ne kadar süreyle, hangi mekanizmayla
> silinir" sorusunun tek cevabı bu tablodur. Plan referansı: `GELISTIRME_PLANI.md`
> J.3 ve F bölümü. **Bu belge sözleşme eklerine (DPA) girer** — hukuk onayından
> geçmeden yayımlanmamalıdır.

## 1. Silme mekanizmaları

| Mekanizma | Ne yapar | Nerede |
|---|---|---|
| **Yumuşak silme** | `deleted_at` işaretlenir; kayıt tüm okuma yollarından anında düşer. Nesne depolamadaki dosyaya dokunulmaz. | `tenderiq_core.db.soft_delete` (otomatik filtre), `DELETE /api/v1/tenders/{id}`, `DELETE /api/v1/documents/{id}` |
| **Geri alma** | Saklama penceresi içinde yumuşak silmeyi iptal eder. Yalnız ihaleyle birlikte silinen dokümanları geri açar. | `POST /api/v1/tenders/{id}/restore` |
| **Kalıcı silme (purge)** | Saklama penceresi dolunca **önce nesne depolamadaki dosyalar, sonra DB satırları** silinir. Alt tablolar FK `ON DELETE CASCADE` ile gider. | `data.purge_deleted` Celery beat işi (günde bir) |

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
| Kullanıcı hesabı | `user_account` | Hesap silinene dek | *(bkz. Açık uçlar)* |
| Üyelik | `membership` | Organizasyon/kullanıcı ile | CASCADE |
| Davet | `invitation` | Kabul/iptal/süre aşımı + 30 gün | *(bkz. Açık uçlar)* |
| Oturum (refresh token) | Redis | TTL (kısa ömürlü); logout'ta anında iptal | TTL + `revoke_all_for_user` |
| Tek kullanımlık token (doğrulama/sıfırlama) | Redis | TTL; ilk kullanımda atomik tüketim | TTL / GETDEL |
| Oran sınırlama sayaçları | Redis | Pencere süresi (300 sn) | TTL |
| Yapılandırılmış loglar | Log altyapısı | ≥ 30 gün (J.4) | Log rotasyonu · **PII maskeleme doğrulanmalı** |
| LLM istemleri/çıktıları | Sağlayıcı | **Sıfır saklama (zero-retention)** — ADR-0007 | Sağlayıcı tarafında saklanmaz |

## 3. LLM ve alt-işleyenler

ADR-0007 gereği LLM sağlayıcısıyla **zero-retention + no-training** yapılandırması
zorunludur. Doküman içeriği sağlayıcıda kalıcı olarak saklanmaz; bu nedenle
"silme" talebi LLM sağlayıcısına ayrıca iletilmez. Alt-işleyen listesi trust
sayfasında yayımlanır.

## 4. Açık uçlar — GA öncesi kapatılmalı

Bu maddeler **henüz uygulanmadı**; matris eksiksiz sayılmaz:

1. **Hesap/organizasyon kapatma akışı yok.** Şu an ihale ve doküman silinebiliyor;
   "organizasyonumu ve tüm verimi sil" (KVKK md. 7 tam silme) ucu yazılmadı.
   Organizasyon silinince `tenant_id` FK'leri CASCADE ile her şeyi götürür, ancak
   R2 nesnelerinin toplu silinmesi ve fatura kayıtlarının VUK gereği ayrı
   tutulması ayrıca kurgulanmalı.
2. **Veri sahibi erişim hakkı (veri dışa aktarma) ucu yok.** KVKK md. 11
   kapsamında kullanıcı kendi verisinin kopyasını isteyebilir. Bugün yalnız
   ihale bazlı Word/Excel export var; hesap düzeyinde dışa aktarma yok.
3. **Davet ve hesap kayıtları için otomatik temizlik yok.** Süresi dolmuş davetler
   silinmiyor, yalnız geçersiz sayılıyor.
4. **Log PII maskelemesi doğrulanmadı.** J.4 maddesi; loglarda e-posta/doküman
   içeriği sızmadığı denetlenmeli.
5. **R2 bucket versioning + yaşam döngüsü kuralları kurulmadı** (J.3). Versioning
   açıksa `delete_object` eski sürümü bırakabilir — hard-delete ile uyumu
   yapılandırma seviyesinde doğrulanmalı.

## 5. Doğrulama

Silme akışının davranışı `apps/api/tests/integration/test_deletion_flow.py`
altında sınanır: yumuşak silmenin tüm okuma yollarından düşürmesi (liste, detay,
bulgular, doküman listesi, **imzalı dosya URL'i**, panel, export), geri alma,
CASCADE ile alt tabloların gitmesi, nesne silinemediğinde satırın korunması ve
kiracılar arası izolasyon.
