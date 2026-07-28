# Olay Müdahale Runbook'u

> **Durum:** beta · **Son güncelleme:** 2026-07-28 · **Sahibi:** Berkay (Scryne)
>
> Plan referansı: `GELISTIRME_PLANI.md` J.4. Hedefler `docs/slo.md`dedir.
> Bu belge tek kişilik bir ekip için yazılmıştır: her bölüm **belirti → teşhis →
> çözüm → kalıcı önlem** sırasını izler ve teşhis adımları kopyalanıp
> çalıştırılabilir komutlardır.

## 0. İlk 3 dakika — her olayda aynı

```bash
# 1. Ne çalışıyor, ne çalışmıyor?
curl -s localhost:8000/healthz                       # süreç ayakta mı
curl -s localhost:8000/readyz | jq                   # DB/Redis erişilebilir mi
docker compose -f infra/compose/docker-compose.yml ps

# 2. Sayısal durum (SLO yargısı + kuyruk derinliği)
curl -s -H "Authorization: Bearer $OPS_METRICS_TOKEN" \
     localhost:8000/ops/metrics | jq '{queue_depth, api, healthy, slos}'

# 3. Son hatalar (yapılandırılmış log; korelasyon kimliğiyle izlenir)
docker compose -f infra/compose/docker-compose.yml logs --tail=200 api worker \
  | grep -E '"level": ?"(error|warning)"'
```

`/ops/metrics` yanıtındaki `slos[].ok == false` olan kalem, hangi bölüme
gideceğinizi söyler:

| İhlal edilen SLO | Bölüm |
|---|---|
| `processing_duration_p95` · `queue_depth` yüksek | §2 Kuyruk tıkandı |
| `processing_success_rate` | §3 LLM sağlayıcı · §4 OCR/disk |
| `api_availability` · `/readyz` kırmızı | §1 Veritabanı |
| `api_latency_p95` | §5 API yavaşladı |

> **Kimlik doğrulama olayları:** `/ops/metrics` erişilemiyorsa token'ı `.env`den
> teyit edin. Ops token'ı yoksa uç bilinçli olarak **404** döner — bu bir arıza
> belirtisi değildir.

---

## 1. Veritabanı erişilemez / bağlantı havuzu doldu

**Belirti:** `/readyz` → `database.healthy=false`; API 500'leri; loglarda
`OperationalError`, `too many clients`, `disk full`.

**Teşhis**

```bash
# Bağlantı sayısı ve tavan
docker compose exec postgres psql -U tenderiq -d tenderiq -c \
  "SELECT count(*), (SELECT setting FROM pg_settings WHERE name='max_connections') FROM pg_stat_activity;"

# Uzun süren / kilitli sorgular
docker compose exec postgres psql -U tenderiq -d tenderiq -c \
  "SELECT pid, state, wait_event_type, now()-query_start AS suresi, left(query,80)
   FROM pg_stat_activity WHERE state <> 'idle' ORDER BY query_start LIMIT 10;"

# Disk ve tablo büyüklükleri
docker compose exec postgres df -h /var/lib/postgresql/data
docker compose exec postgres psql -U tenderiq -d tenderiq -c \
  "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables
   ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"
```

**Çözüm**

1. **Bağlantı tükenmesi:** önce worker'ı ölçekle (`--concurrency` düşür), sonra
   API replikasını. Havuz `pool_pre_ping` ile kopuk bağlantıyı kendi toparlar;
   yeniden başlatma son çare.
2. **Kilit:** kilidi tutan `pid`'i teyit edip `SELECT pg_cancel_backend(<pid>)`;
   yanıt vermezse `pg_terminate_backend`.
3. **Disk:** §4'e geçin. En büyük tablolar tipik olarak `embedding` ve
   `parsed_element`tir — ikisi de kalıcı silmeyle küçülür.

**Kalıcı önlem:** disk kullanımı > %80 uyarısı; `DATA_RETENTION_DAYS` gözden
geçirmesi; `data.purge_deleted` beat işinin gerçekten koştuğunun teyidi (§2.3).

---

## 2. Kuyruk tıkandı / işler ilerlemiyor

**Belirti:** `queue_depth` sürekli artıyor; dokümanlar `queued`/`parsing`da
takılı; kullanıcı "analiz bitmiyor" diyor; `processing_duration_p95` ihlal.

**Teşhis**

```bash
# Kuyruk derinliği (Celery kuyruğu = Redis listesi)
docker compose exec redis redis-cli LLEN tenderiq

# Worker canlı mı, kaç iş yürütüyor?
docker compose exec worker celery -A tenderiq_worker.celery_app:celery_app inspect ping
docker compose exec worker celery -A tenderiq_worker.celery_app:celery_app inspect active

# Faz bazında nerede takılıyor
curl -s -H "Authorization: Bearer $OPS_METRICS_TOKEN" \
     localhost:8000/ops/metrics | jq '.phases'
```

**Çözüm**

1. **Worker ölü/yok:** `docker compose up -d worker`. `inspect ping` yanıtsızsa
   süreç ayakta ama bloke demektir → `docker compose restart worker`.
   `task_acks_late=True` olduğundan yarım kalan iş **kaybolmaz**, yeniden teslim
   edilir; task'lar idempotenttir ve kaldıkları fazdan devam eder.
2. **Tek doküman worker'ı kilitliyor:** `task_soft_time_limit=25 dk` devreye
   girer ve iş retry/`failed` yoluna düşer. Erken müdahale gerekiyorsa
   `inspect active` çıktısındaki `job_id` ile ilgili işi `failed`e çekin.
3. **Yalnız yük fazlaysa:** worker eşzamanlılığını artırın. `prefetch=1`
   olduğundan her worker slotu tek iş tutar; ölçekleme doğrusaldır.
4. **Beat işleri koşmuyorsa** (`cleanup-stale-uploads`, `purge-deleted`):
   worker `-B` bayrağıyla mı koşuyor? Worker çoğaltıldıysa beat **ayrı bir
   servise** alınmalıdır — aksi hâlde zamanlanmış işler her replikada tekrarlanır.

**Kalıcı önlem:** `queue_depth > 50 ve artıyor` uyarısı (SLO §4); yük testiyle
kapasite doğrulaması (`scripts/load_test.py`).

---

## 3. LLM sağlayıcı kesintisi

**Belirti:** `extracting` fazında yığılma; `processing_success_rate` düşüyor;
loglarda sağlayıcı zaman aşımı/429; işler retry döngüsünde.

**Teşhis**

```bash
docker compose logs --tail=200 worker | grep -E 'extract_adimi|islem_hatasi'
echo $LLM_PROVIDER   # anthropic | nvidia (OpenAI-uyumlu) | ollama | none
```

**Çözüm**

1. **Sağlayıcı kesintisi:** `LLM_PROVIDER`ı yedeğe alın ve worker'ı yeniden
   başlatın. Sağlayıcı seam'i (`tenderiq_core.llm`) bunu yapılandırma
   değişikliğiyle kabul eder; kod değişikliği gerekmez.
   > **KVKK notu:** bulut sağlayıcıya (NVIDIA NIM) geçiş, doküman içeriğinin
   > o sağlayıcıya gitmesi demektir. Zero-retention sözleşmesi olmayan bir
   > sağlayıcıya **acil durumda dahi** geçilmez (ADR-0007).
2. **Kota/429:** worker eşzamanlılığını geçici düşürün; backoff zaten üsteldir
   (5 sn → 300 sn tavan, 5 deneme).
3. **Uzun kesinti:** `LLM_PROVIDER=none` ile hattı çıkarımsız çalıştırın —
   parse+index tamamlanır, bulgular boş kalır. Kullanıcıya durumu duyurun;
   sağlayıcı dönünce etkilenen işler yeniden kuyruklanır (`failed → queued`).

**Kalıcı önlem:** ikinci sağlayıcının anahtarları hazır tutulur; Langfuse'ta
maliyet/gecikme izlenir.

---

## 4. Disk doldu / OCR patlaması

**Belirti:** parse fazı hataları; `No space left on device`; worker konteyneri
CPU/RAM'i tavanda; taranmış büyük PDF sonrası ani yavaşlama.

**Teşhis**

```bash
docker system df                      # imaj/volume/build cache
df -h                                 # host diski
docker compose exec postgres df -h /var/lib/postgresql/data
docker stats --no-stream worker       # OCR sırasında CPU/RAM
```

**Çözüm**

1. **Hızlı yer açma:** `docker system prune -f` (volume'lara **dokunmaz**),
   eski imajlar, build cache.
2. **Postgres şişkinliği:** kalıcı silmeyi elle tetikleyin ve sonra `VACUUM`:
   ```bash
   docker compose exec worker python -c \
     "from tenderiq_worker.tasks.documents import purge_deleted; print(purge_deleted())"
   docker compose exec postgres psql -U tenderiq -d tenderiq -c "VACUUM (ANALYZE);"
   ```
3. **OCR yükü:** EasyOCR CPU'da ağırdır. Tek patolojik doküman
   `task_soft_time_limit` ile kesilir; sık tekrar ediyorsa `UPLOAD_MAX_SIZE_BYTES`
   ve sayfa kotası gözden geçirilir.
4. **Nesne depolama:** R2 tarafında yer sorunu olmaz ama **yetim nesne** olabilir
   (DB satırı silinmiş, dosya kalmış). Kalıcı silme sırası bunu önler: önce
   nesne, sonra satır. Nesne silinemezse satır bilinçli olarak **bırakılır**.

**Kalıcı önlem:** disk > %80 uyarısı; `docs/veri-saklama-matrisi.md` §2 saklama
sürelerinin fiilen uygulandığının dönemsel teyidi.

---

## 5. API yavaşladı (p95 > 500 ms)

**Belirti:** `api_latency_p95` ihlal; kullanıcı "site ağır" diyor; `/healthz`
sağlıklı.

**Teşhis**

```bash
# Hangi uç yavaş? (histogram kardinaliteyi tutmaz; ayrıntı LOGDADIR)
docker compose logs --tail=500 api | grep yavas_istek

# DB tarafı mı?
docker compose exec postgres psql -U tenderiq -d tenderiq -c \
  "SELECT left(query,60), calls, round(mean_exec_time) ms FROM pg_stat_statements
   ORDER BY mean_exec_time DESC LIMIT 10;"   # pg_stat_statements etkinse
```

`yavas_istek` kaydı ≥ 1 sn süren her isteği rota şablonu, metot, süre ve durum
koduyla yazar; `request_id` ile ilgili isteğin tüm log zinciri izlenebilir.

**Çözüm**

1. **Tek uç yavaşsa:** N+1 sorgu ilk şüphelidir (panel bu yüzden toplu uca
   taşındı). Sorguyu `EXPLAIN ANALYZE` ile doğrulayın, eksik indeksi ekleyin.
2. **Her uç yavaşsa:** DB bağlantı havuzu (§1) veya konteyner kaynak sınırı.
3. **Yalnız SSE uçları yavaş görünüyorsa:** bu ölçüme zaten girmez; belirti
   başka yerdedir.

---

## 6. Yanlışlıkla kapatılan hesabı geri alma

Hesap kapatmanın (KVKK md. 7) **geri alma ucu yoktur** — bu bilinçlidir; silme
talebine "geri al" düğmesi koymak talebin kendisini zayıflatır. Saklama
penceresi (`DATA_RETENTION_DAYS`, varsayılan 30 gün) içinde destek elle geri
alabilir:

```sql
-- Kapatılmış organizasyonu ve içeriğini geri getir (purge KOŞMADIYSA).
UPDATE organization SET deleted_at = NULL, name = :gercek_ad, slug = :gercek_slug
 WHERE id = :org_id;
UPDATE tender   SET deleted_at = NULL WHERE tenant_id = :org_id;
UPDATE document SET deleted_at = NULL WHERE tenant_id = :org_id;
```

> **Kalıcı süpürme koştuysa geri dönüş YOKTUR:** içerik ve R2 dosyaları silinmiş,
> organizasyon adı `deleted-<uuid>` olarak anonimleştirilmiştir. Önce
> `audit_log`dan kapatma zamanını ve süpürmenin koşup koşmadığını teyit edin.
> Fatura kayıtları (`subscription`, `usage_record`) VUK gereği durur.

Ayrıntı: `docs/veri-saklama-matrisi.md` §4.

---

## 7. Dağıtımı geri alma

```bash
# Önceki imaja dön (etiketli imaj kullanılıyorsa)
docker compose -f infra/compose/docker-compose.yml up -d --no-deps api worker

# Migration geri alma — DİKKAT: veri kaybı olabilir
docker compose run --rm migrate alembic downgrade -1
```

**Kural:** migration'lar ileri-uyumlu yazılır; kod geri alınabilir olmalı,
migration'ın geri alınması **son çaredir**. Şüphede kalınca önce kodu geri alın,
şemayı olduğu yerde bırakın.

---

## 8. Olay sonrası

Her olay için kısa bir kayıt tutulur (tarih, belirti, kök neden, çözüm süresi,
alınan kalıcı önlem). Tekrar eden bir olay, runbook'a yeni bölüm değil
**otomasyon** gerektirir (J bölümü ilkesi: *otomasyon > runbook*).

Hata bütçesi tüketimi `docs/slo.md` §2'ye göre değerlendirilir.
