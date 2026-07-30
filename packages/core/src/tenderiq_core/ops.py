"""Operasyonel metrikler (J.4): yuvarlanan pencere sayaçları + SLO değerlendirmesi.

Neden Redis, neden DB değil
---------------------------
SLO'ların ölçüm kaynağı **işletim penceresi**dir ("son 60 dakikada p95 neydi"),
kalıcı kayıt değil. Bunu ``job`` tablosundan sorgulamak iki sorun doğururdu:
``job`` kiracı-özel ve RLS'ye tabidir (kiracılar arası toplam için ayrıcalıklı
bağlantı gerekirdi) ve izleme ucunun her çağrısı üretim veritabanında tarama
üretirdi — yani izlemenin kendisi bir yük kaynağı olurdu. Bunun yerine yazan
taraf (API middleware'i ve worker fazları) dakikalık **histogram** kovalarını
Redis'te artırır; okuyan taraf yalnız o kovaları toplar.

Sözleşme
--------
- **Ölçüm asla isteği bozmaz.** Tüm yazıcılar hata-toleranslıdır (fail-open):
  Redis erişilemezse metrik kaybolur, istek/iş normal akışına devam eder.
- **Yüzdelikler kova tavanıdır.** ``p95 = 500 ms`` ifadesi "isteklerin %95'i
  500 ms kovasına veya altına düştü" demektir; kova içi enterpolasyon yapılmaz.
  Bu, gerçek değeri hep **yukarı** yuvarlar — SLO yargısı yanlışlıkla "geçti"
  diyemez, en fazla haksız yere "kaldı" der.
- Kovalar dakikada bir hash'tir ve TTL'lidir; temizlik işi gerekmez.

Hedefler ``GELISTIRME_PLANI.md`` J.4'ten gelir ve ``docs/slo.md``de gerekçelendirilir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Final

from redis import Redis as SyncRedis
from redis.asyncio import Redis

from tenderiq_core.config import get_settings
from tenderiq_core.logging import get_logger
from tenderiq_core.queueing import QUEUE_DEFAULT

logger = get_logger("tenderiq.ops")

__all__ = [
    "API_LATENCY_EDGES_MS",
    "JOB_DURATION_EDGES_SECONDS",
    "JOB_PHASE_TOTAL",
    "ApiWindow",
    "OpsSnapshot",
    "PhaseWindow",
    "SloVerdict",
    "collect_snapshot",
    "record_api_request",
    "record_job_phase",
]

# Histogram kova tavanları. Kenarlar SLO eşiklerini (500 ms / 600 sn) **tam
# olarak** içerir; aksi hâlde yargı, eşiğin denk gelmediği bir kovaya yuvarlanır
# ve "p95 < 500 ms" sorusu ölçülemez hâle gelirdi.
API_LATENCY_EDGES_MS: Final[tuple[int, ...]] = (25, 50, 100, 250, 500, 1000, 2500, 5000)
JOB_DURATION_EDGES_SECONDS: Final[tuple[int, ...]] = (30, 60, 120, 300, 600, 1200, 1800, 3600)

#: Tüm fazların toplamı — "doküman işleme süresi" SLI'ının taşıyıcısı.
JOB_PHASE_TOTAL: Final = "total"

# Pencere en fazla 24 saat sorgulanabilir; kovalar bir saat fazlasıyla yaşar.
MAX_WINDOW_MINUTES: Final = 24 * 60
_BUCKET_TTL_SECONDS: Final = 25 * 3600

_API_PREFIX: Final = "ops:api"
_JOB_PREFIX: Final = "ops:job"
_OVERFLOW_EDGE: Final = "inf"

HTTP_CLIENT_ERROR: Final = 400
HTTP_SERVER_ERROR: Final = 500

# ── SLO hedefleri (J.4) ──────────────────────────────────────────────────────
SLO_API_AVAILABILITY: Final = 0.995
SLO_API_P95_MS: Final = 500.0
SLO_JOB_TOTAL_P95_SECONDS: Final = 600.0
SLO_JOB_SUCCESS_RATE: Final = 0.98


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _minute_key(prefix: str, moment: datetime) -> str:
    """Bir dakikalık kovanın Redis anahtarı."""
    return f"{prefix}:{moment.astimezone(UTC):%Y%m%d%H%M}"


def _histogram_field(edges: tuple[int, ...], value: float, namespace: str = "") -> str:
    """Değerin düştüğü kovanın hash alan adı (``le:<tavan>``)."""
    for edge in edges:
        if value <= edge:
            return f"{namespace}le:{edge}"
    return f"{namespace}le:{_OVERFLOW_EDGE}"


def _api_fields(duration_ms: float, status_code: int) -> dict[str, int]:
    """Bir API isteğinin artıracağı hash alanları."""
    fields = {"n": 1, _histogram_field(API_LATENCY_EDGES_MS, duration_ms): 1}
    if status_code >= HTTP_SERVER_ERROR:
        fields["e5"] = 1
    elif status_code >= HTTP_CLIENT_ERROR:
        fields["e4"] = 1
    return fields


def _job_fields(phase: str, duration_seconds: float, *, ok: bool) -> dict[str, int]:
    """Bir işleme fazının artıracağı hash alanları."""
    fields = {f"{phase}:n": 1}
    if ok:
        # Süre yalnız BAŞARILI fazdan anlamlıdır: yarıda kalan bir fazın süresi
        # "işleme ne kadar sürüyor" sorusunu değil, "ne zaman patladı"yı ölçer.
        fields[_histogram_field(JOB_DURATION_EDGES_SECONDS, duration_seconds, f"{phase}:")] = 1
    else:
        fields[f"{phase}:fail"] = 1
    return fields


async def record_api_request(redis: Redis, *, duration_ms: float, status_code: int) -> None:
    """Bir API isteğinin gecikmesini ve durum sınıfını yuvarlanan pencereye yazar."""
    key = _minute_key(_API_PREFIX, _utcnow())
    try:
        pipe = redis.pipeline(transaction=False)
        for field, amount in _api_fields(duration_ms, status_code).items():
            pipe.hincrby(key, field, amount)
        pipe.expire(key, _BUCKET_TTL_SECONDS)
        await pipe.execute()
    except Exception as exc:  # ölçüm, ölçtüğü isteği ASLA bozmaz
        logger.debug("ops_api_metrigi_yazilamadi", error=str(exc))


@lru_cache(maxsize=1)
def _sync_redis() -> SyncRedis:
    """Worker süreci için paylaşılan senkron Redis istemcisi (süreç ömürlü)."""
    return SyncRedis.from_url(get_settings().redis_url)


def record_job_phase(
    phase: str, *, duration_seconds: float, ok: bool, redis: SyncRedis | None = None
) -> None:
    """Bir işleme fazının süresini/sonucunu yuvarlanan pencereye yazar (senkron/worker)."""
    key = _minute_key(_JOB_PREFIX, _utcnow())
    try:
        client = redis if redis is not None else _sync_redis()
        pipe = client.pipeline(transaction=False)
        for field, amount in _job_fields(phase, duration_seconds, ok=ok).items():
            pipe.hincrby(key, field, amount)
        pipe.expire(key, _BUCKET_TTL_SECONDS)
        pipe.execute()
    except Exception as exc:  # ölçüm, ölçtüğü işi ASLA bozmaz
        logger.debug("ops_is_metrigi_yazilamadi", error=str(exc))


def record_llm_usage_lost(amount: int, *, reason: str) -> None:
    """Yazılamayan LLM kullanım kaydı sayacı (J.6).

    Maliyet ölçümünün kendi arızası GÖRÜNÜR olmalı: bu sayaç olmadan "kiracının
    harcaması düşük" ile "kayıtlar kayboluyor" ayırt edilemez ve tavan sessizce
    devre dışı kalır.
    """
    key = _minute_key(_JOB_PREFIX, _utcnow())
    try:
        client = _sync_redis()
        pipe = client.pipeline(transaction=False)
        pipe.hincrby(key, "llm_usage_lost", amount)
        pipe.hincrby(key, f"llm_usage_lost:{reason}", amount)
        pipe.expire(key, _BUCKET_TTL_SECONDS)
        pipe.execute()
    except Exception as exc:  # ölçüm, ölçtüğü işi ASLA bozmaz
        logger.debug("ops_llm_kayip_metrigi_yazilamadi", error=str(exc))


def record_llm_budget_degraded(*, reason: str) -> None:
    """Bütçe kontrolünün REZERVASYONSUZ (muhafazakâr) moda düştüğü sayacı.

    Kesintide sessizce geçmek seçenek değildi: bu sayaç "tavan hâlâ zorlanıyor
    ama yarış koruması yok" hâlini görünür kılar. Sürekli artıyorsa Redis
    arızası tavanı zayıflatıyor demektir.
    """
    key = _minute_key(_JOB_PREFIX, _utcnow())
    try:
        client = _sync_redis()
        pipe = client.pipeline(transaction=False)
        pipe.hincrby(key, "llm_budget_degraded", 1)
        pipe.hincrby(key, f"llm_budget_degraded:{reason}", 1)
        pipe.expire(key, _BUCKET_TTL_SECONDS)
        pipe.execute()
    except Exception as exc:  # ölçüm, ölçtüğü işi ASLA bozmaz
        logger.debug("ops_llm_butce_metrigi_yazilamadi", error=str(exc))


# ── Okuma tarafı ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ApiWindow:
    """Pencere boyunca API isteklerinin özeti."""

    requests: int
    server_errors: int
    client_errors: int
    p50_ms: float | None
    p95_ms: float | None

    @property
    def availability(self) -> float | None:
        """5xx üretmeyen isteklerin oranı (dış izleyicinin uptime'ı DEĞİLDİR)."""
        if self.requests == 0:
            return None
        return 1.0 - self.server_errors / self.requests


@dataclass(frozen=True, slots=True)
class PhaseWindow:
    """Bir işleme fazının (veya toplamın) pencere özeti."""

    phase: str
    completed: int
    failed: int
    p50_seconds: float | None
    p95_seconds: float | None

    @property
    def success_rate(self) -> float | None:
        """Tamamlanan / (tamamlanan + başarısız)."""
        total = self.completed + self.failed
        if total == 0:
            return None
        return self.completed / total


@dataclass(frozen=True, slots=True)
class SloVerdict:
    """Tek bir SLO'nun pencere içindeki durumu. ``ok=None`` → ölçecek veri yok."""

    key: str
    description: str
    target: str
    actual: str
    ok: bool | None


@dataclass(frozen=True, slots=True)
class OpsSnapshot:
    """Operasyon panosunun tek çağrılık görüntüsü."""

    generated_at: datetime
    window_minutes: int
    queue_depth: int
    api: ApiWindow
    phases: tuple[PhaseWindow, ...]
    slos: tuple[SloVerdict, ...]

    @property
    def breaching(self) -> tuple[SloVerdict, ...]:
        """Hedefi tutmayan SLO'lar (veri yoksa ihlal sayılmaz)."""
        return tuple(verdict for verdict in self.slos if verdict.ok is False)


def _quantile(counts: dict[int | float, int], quantile: float) -> float | None:
    """Kova sayımlarından yüzdelik — kovanın TAVANINI döndürür (yukarı yuvarlar)."""
    total = sum(counts.values())
    if total == 0:
        return None
    threshold = quantile * total
    cumulative = 0
    for edge in sorted(counts):
        cumulative += counts[edge]
        if cumulative >= threshold:
            return float(edge)
    return math.inf


def _histogram(
    raw: dict[str, int], edges: tuple[int, ...], namespace: str = ""
) -> dict[int | float, int]:
    """Ham hash alanlarından kova sayımlarını çıkarır."""
    counts: dict[int | float, int] = {}
    for edge in edges:
        value = raw.get(f"{namespace}le:{edge}", 0)
        if value:
            counts[edge] = value
    overflow = raw.get(f"{namespace}le:{_OVERFLOW_EDGE}", 0)
    if overflow:
        counts[math.inf] = overflow
    return counts


def _merge(buckets: list[dict[str, int]]) -> dict[str, int]:
    """Dakikalık hash'leri tek sözlükte toplar."""
    merged: dict[str, int] = {}
    for bucket in buckets:
        for field, value in bucket.items():
            merged[field] = merged.get(field, 0) + value
    return merged


def _decode(raw: object) -> dict[str, int]:
    """``HGETALL`` sonucunu (bytes → str/int) normalleştirir; bozuk alanı atar."""
    if not isinstance(raw, dict):
        return {}
    decoded: dict[str, int] = {}
    for key, value in raw.items():
        field = key.decode() if isinstance(key, bytes) else str(key)
        try:
            decoded[field] = int(value)
        except (TypeError, ValueError):
            continue
    return decoded


def _phase_window(phase: str, raw: dict[str, int]) -> PhaseWindow:
    counts = _histogram(raw, JOB_DURATION_EDGES_SECONDS, f"{phase}:")
    started = raw.get(f"{phase}:n", 0)
    failed = raw.get(f"{phase}:fail", 0)
    return PhaseWindow(
        phase=phase,
        completed=max(0, started - failed),
        failed=failed,
        p50_seconds=_quantile(counts, 0.50),
        p95_seconds=_quantile(counts, 0.95),
    )


def _format_ratio(value: float | None) -> str:
    return "veri yok" if value is None else f"%{value * 100:.2f}"


def _format_duration(value: float | None, unit: str) -> str:
    if value is None:
        return "veri yok"
    if math.isinf(value):
        return f"> en üst kova ({unit})"
    return f"{value:.0f} {unit}"


def evaluate_slos(api: ApiWindow, phases: tuple[PhaseWindow, ...]) -> tuple[SloVerdict, ...]:
    """Pencere ölçümlerini J.4 hedefleriyle karşılaştırır."""
    total = next((phase for phase in phases if phase.phase == JOB_PHASE_TOTAL), None)
    availability = api.availability
    success_rate = total.success_rate if total else None
    job_p95 = total.p95_seconds if total else None

    return (
        SloVerdict(
            key="api_availability",
            description="API erişilebilirliği (5xx üretmeyen istek oranı)",
            target=f"≥ %{SLO_API_AVAILABILITY * 100:.1f}",
            actual=_format_ratio(availability),
            ok=None if availability is None else availability >= SLO_API_AVAILABILITY,
        ),
        SloVerdict(
            key="api_latency_p95",
            description="API p95 gecikmesi (SSE/akış uçları hariç)",
            target=f"< {SLO_API_P95_MS:.0f} ms",
            actual=_format_duration(api.p95_ms, "ms"),
            ok=None if api.p95_ms is None else api.p95_ms <= SLO_API_P95_MS,
        ),
        SloVerdict(
            key="processing_duration_p95",
            description="Doküman işleme süresi p95 (yükleme→review_ready)",
            target=f"< {SLO_JOB_TOTAL_P95_SECONDS / 60:.0f} dk",
            actual=_format_duration(job_p95, "sn"),
            ok=None if job_p95 is None else job_p95 <= SLO_JOB_TOTAL_P95_SECONDS,
        ),
        SloVerdict(
            key="processing_success_rate",
            description="İşleme başarı oranı",
            target=f"≥ %{SLO_JOB_SUCCESS_RATE * 100:.0f}",
            actual=_format_ratio(success_rate),
            ok=None if success_rate is None else success_rate >= SLO_JOB_SUCCESS_RATE,
        ),
    )


async def collect_snapshot(redis: Redis, *, window_minutes: int = 60) -> OpsSnapshot:
    """Yuvarlanan penceredeki tüm operasyon metriklerini tek turda toplar."""
    window = max(1, min(window_minutes, MAX_WINDOW_MINUTES))
    now = _utcnow()
    minutes = [now - timedelta(minutes=index) for index in range(window)]

    pipe = redis.pipeline(transaction=False)
    for moment in minutes:
        pipe.hgetall(_minute_key(_API_PREFIX, moment))
    for moment in minutes:
        pipe.hgetall(_minute_key(_JOB_PREFIX, moment))
    pipe.llen(QUEUE_DEFAULT)
    results = await pipe.execute()

    api_raw = _merge([_decode(item) for item in results[:window]])
    job_raw = _merge([_decode(item) for item in results[window : 2 * window]])
    queue_depth = results[-1] if isinstance(results[-1], int) else 0

    api = ApiWindow(
        requests=api_raw.get("n", 0),
        server_errors=api_raw.get("e5", 0),
        client_errors=api_raw.get("e4", 0),
        p50_ms=_quantile(_histogram(api_raw, API_LATENCY_EDGES_MS), 0.50),
        p95_ms=_quantile(_histogram(api_raw, API_LATENCY_EDGES_MS), 0.95),
    )
    phases = tuple(
        _phase_window(phase, job_raw)
        for phase in ("parsing", "indexing", "extracting", JOB_PHASE_TOTAL)
    )

    return OpsSnapshot(
        generated_at=now,
        window_minutes=window,
        queue_depth=queue_depth,
        api=api,
        phases=phases,
        slos=evaluate_slos(api, phases),
    )
