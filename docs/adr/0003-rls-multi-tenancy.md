# ADR-0003: Çok-kiracılılık — tenant_id + PostgreSQL RLS

- **Durum:** Kabul edildi
- **Tarih:** 2026-07-03
- **Karar veren:** Berkay (Scryne)

## Bağlam
İhale dokümanları ticari sır içerir; kiracılar arası veri sızıntısı en kritik
tehdittir (Ürün Planı §10.1). İzolasyon yalnızca uygulama katmanına bırakılamaz —
tek bir kod hatası tüm izolasyonu bozmamalıdır.

## Karar
Kiracıya-özel her tablo bir `tenant_id` taşır; **PostgreSQL Row-Level Security (RLS)**
politikaları her sorguyu aktif kiracıyla sınırlar. Uygulama, her transaction'da aktif
`tenant_id`'yi bir oturum değişkenine (`app.current_tenant`, transaction-local) set eder;
RLS bunu zorunlu kılar. Bağlam set edilmezse `current_setting(..., true)` NULL döner ve
hiçbir satır görünmez (**fail-closed**).

**Kritik uygulama detayı:** PostgreSQL süper-kullanıcıları — ve `FORCE` olmadan tablo
sahibi — RLS'yi baypas eder. Bu yüzden: (1) kiracı-özel tablolarda `FORCE ROW LEVEL
SECURITY` etkindir; (2) uygulama (api/worker) **süper-kullanıcı olmayan** `tenderiq_app`
rolüyle bağlanır; migration'lar ise ayrıcalıklı `tenderiq` rolüyle çalışır
(`DATABASE_URL` vs `DATABASE_ADMIN_URL`).

**Kural (çift katman):** Uygulama katmanı hatası olsa bile veritabanı izolasyonu korunur.
Yeni bir kiracı-özel tablo eklenirken; `tenant_id` + RLS politikası + kiracılar-arası
izolasyon testi **aynı PR'da** eklenir.

## Sonuçlar
**Olumlu:** Güçlü, veritabanı-düzeyinde izolasyon; tek şema ile düşük operasyonel yük.
**Ödünler:** Her tabloda RLS disiplini gerekir; oturum değişkeni yönetimi ve testi
zorunludur.

## Alternatifler
- **Şema-per-tenant / DB-per-tenant:** Daha güçlü izolasyon ama yüksek operasyon;
  çok duyarlı kurumsal müşteriler için ileride yükseltme yolu olarak açık tutulur.
- **Yalnızca uygulama-katmanı filtreleme:** Tek hata noktası; kabul edilemez.

## İlgili
Geliştirme Planı §C.7, §F; Sprint 0.2 (görev #11, #12); Ürün Planı §5.4, §8.3.
