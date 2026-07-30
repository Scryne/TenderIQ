# Yapılandırma manifestosu — dağıtımda doldurulacak tek liste

> **Dağıtım kararı verildiğinde bakılacak liste budur.** Tek kaynak
> `apps/web/env-manifest.json`; bu belge onu okunur hâle getirir ve backend
> tarafını da ekler.
>
> Denetim: `apps/api/tests/test_yapilandirma_denetimi.py` — manifestodaki her
> değişkenin `.env.example`, compose build arg, Dockerfile `ARG` ve CI job
> env'inde bulunduğunu doğrular; ayrıca kodda okunup manifestoya yazılmamış bir
> değişken kalmasını engeller.

## Neden bu belge var

Tur 11'de `NEXT_PUBLIC_STORAGE_ORIGIN` **hiçbir yerde kurulmuyordu** ve
eksikliği sessizce doküman tuvalini öldürdü. Tek bir unutulmuş satır değildi;
bir sınıfın örneğiydi:

1. Değer **derleme anında** gömülür (`NEXT_PUBLIC_*` ya da build `ARG`), yani
   çalışma anında verilmesi etkisizdir.
2. Politikayı üreten middleware **edge runtime**'da koşar; orada `process.env`
   derleme sırasında sabite çevrilir.
3. Eksik değişken `undefined` olur, kod `?? ""` ile devam eder ve arıza
   **davranışa gömülür** — log üretmez.

Üç savunma kondu: derleme kapısı (`next.config.ts` → `assertBuildTimeEnv`),
açılış kapısı (`instrumentation.ts` → `assertRuntimeEnv`) ve dağıtım-dosyası
denetimi (yukarıdaki test).

## Web (apps/web)

| Değişken | Ne zaman okunur | Katman | Zorunlu | Eksikse |
|---|---|---|---|---|
| `NEXT_PUBLIC_STORAGE_ORIGIN` | **derleme** | edge | **üretimde** | CSP `connect-src` aynı-origin'e kilitlenir → **doküman tuvali sessizce boş kalır** |
| `STORAGE_ORIGIN` | **derleme** | edge | hayır (yedek ad) | tek başına arıza üretmez |
| `NEXT_PUBLIC_API_URL` | **derleme** | server | hayır (varsayılan) | `http://localhost:8000`e düşer — üretimde tüm API çağrıları kendine gider |
| `API_URL` | çalışma anı | server | hayır (varsayılan) | container ağında backend'e ulaşamaz |
| `NEXT_PUBLIC_SENTRY_DSN` | **derleme** | edge+server+client | hayır | hata izleme sessizce kapalı (bilinçli) |

> **Derleme anında gömülenler nereye yazılır:** compose `web.build.args`,
> `infra/docker/web.Dockerfile` `ARG`, CI'da ilgili job'ın `env`i. Dördü de
> denetim kapsamındadır.

## Backend (api / worker)

Backend değişkenleri `.env.example`de bölüm bölüm belgelidir ve **çalışma
anında** okunur (`pydantic-settings`), yani yeniden derleme gerektirmez. Üretim
açılışında fail-fast uygulayanlar:

| Değişken | Kural |
|---|---|
| `AUTH_SECRET` | üretimde ≥32 karakter, yoksa açılış reddedilir |
| `DEBUG` | üretimde `true` olamaz |
| `LLM_REGION` + `LLM_ALLOW_CROSS_BORDER` | yurt dışı bölge, izin bayrağı olmadan açılışı reddeder (ADR-0013) |
| `BILLING_ENV=live` | ikinci onay bayrağı ister |
| `EMAIL_PROVIDER=memory` | üretimde reddedilir |
| `RESEND_WEBHOOK_SECRET` | boşsa bounce webhook ucu 404 döner (kapalı kurulum) |
| `OPS_METRICS_TOKEN` | boşsa `/ops/metrics` 404 döner |
| `LLM_PRICING_PATH` | okunamazsa her kayıt `unknown_model` olur; tutar hesaplanamaz ve bu KAYITTA görünür |
| `LLM_USD_TRY_RATE` | boşsa maliyet hesaplanmaz (`no_fx_rate`). **0 yazmayın** — 0 TL tavanı sessizce sonsuz yapar |

## Dağıtım öncesi kontrol listesi

- [ ] `NEXT_PUBLIC_STORAGE_ORIGIN` = nesne depolamanın tarayıcıdan erişilen
      origin'i (`OBJECT_STORAGE_ENDPOINT_URL` ile aynı origin) — **web imajı bu
      değerle derlenmeli**, sonradan değiştirilemez.
- [ ] `NEXT_PUBLIC_API_URL` = API'nin tarayıcıdan erişilen kök adresi.
- [ ] `API_URL` = container ağında backend adresi.
- [ ] `AUTH_SECRET` üretildi (`openssl rand -base64 32`).
- [ ] `DATABASE_URL` RLS'ye tabi rol, `DATABASE_ADMIN_URL` ayrıcalıklı rol
      (ADR-0003).
- [ ] Fiyat tablosu (`config/llm-pricing.json`) sağlayıcının güncel fiyatlarıyla
      doğrulandı ve `LLM_USD_TRY_RATE` güncel.
- [ ] `LLM_REGION` / `LLM_ALLOW_CROSS_BORDER` hukuki beyanla tutarlı (ADR-0013).

> Değişken eklerken: önce `apps/web/env-manifest.json`a (web ise) ya da
> `.env.example`e yaz, **eksikse ne kırılacağını** belirt, sonra kodda oku.
> Ters sıra Tur 11'deki arızayı üretir.
