"""Operasyon metrikleri birim testleri — histogram, SLO yargısı, fail-open."""

from __future__ import annotations

from typing import Any, cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from tenderiq_core.ops import (
    JOB_PHASE_TOTAL,
    SLO_API_P95_MS,
    ApiWindow,
    PhaseWindow,
    collect_snapshot,
    evaluate_slos,
    record_api_request,
    record_job_phase,
)


class _Store:
    """İki istemcinin (senkron worker / async API) paylaştığı sahte Redis verisi."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, int]] = {}
        self.ttls: dict[str, int] = {}
        self.lists: dict[str, int] = {}


class _FakePipeline:
    def __init__(self, store: _Store) -> None:
        self._store = store
        self._ops: list[tuple[str, Any, Any]] = []

    def hincrby(self, key: str, field: str, amount: int) -> None:
        self._ops.append(("hincrby", key, (field, amount)))

    def expire(self, key: str, seconds: int) -> None:
        self._ops.append(("expire", key, seconds))

    def hgetall(self, key: str) -> None:
        self._ops.append(("hgetall", key, None))

    def llen(self, key: str) -> None:
        self._ops.append(("llen", key, None))

    def _run(self) -> list[Any]:
        results: list[Any] = []
        for name, key, payload in self._ops:
            if name == "hincrby":
                field, amount = payload
                bucket = self._store.hashes.setdefault(key, {})
                bucket[field] = bucket.get(field, 0) + amount
                results.append(bucket[field])
            elif name == "expire":
                self._store.ttls[key] = cast("int", payload)
                results.append(True)
            elif name == "hgetall":
                # Gerçek istemci gibi bytes döndürür — çözümleme yolu da sınanır.
                results.append(
                    {
                        field.encode(): str(value).encode()
                        for field, value in self._store.hashes.get(key, {}).items()
                    }
                )
            else:
                results.append(self._store.lists.get(key, 0))
        self._ops.clear()
        return results

    def execute(self) -> list[Any]:
        return self._run()


class _FakeAsyncPipeline(_FakePipeline):
    async def execute(self) -> list[Any]:  # type: ignore[override]
        return self._run()


class _FakeRedis:
    """Senkron istemci (worker yolu)."""

    def __init__(self, store: _Store | None = None) -> None:
        self.store = store or _Store()

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        return _FakePipeline(self.store)


class _FakeAsyncRedis:
    """Async istemci (API yolu) — aynı veriyi paylaşabilir."""

    def __init__(self, store: _Store | None = None) -> None:
        self.store = store or _Store()

    def pipeline(self, transaction: bool = True) -> _FakeAsyncPipeline:
        return _FakeAsyncPipeline(self.store)


class _BrokenRedis:
    """Her işlemde bağlantı hatası veren istemci (fail-open doğrulaması)."""

    def pipeline(self, transaction: bool = True) -> Any:
        raise RedisConnectionError("redis yok")


def _as_async(store: _FakeAsyncRedis) -> Redis:
    return cast("Redis", store)


async def test_istek_gecikmesi_dogru_kovaya_yazilir() -> None:
    store = _FakeAsyncRedis()
    await record_api_request(_as_async(store), duration_ms=300, status_code=200)

    fields = next(iter(store.store.hashes.values()))
    assert fields["n"] == 1
    assert fields["le:500"] == 1  # 250 < 300 ≤ 500
    assert "e5" not in fields


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(200, None), (404, "e4"), (500, "e5"), (503, "e5")],
)
async def test_durum_sinifi_ayri_sayilir(status_code: int, expected: str | None) -> None:
    store = _FakeAsyncRedis()
    await record_api_request(_as_async(store), duration_ms=10, status_code=status_code)

    fields = next(iter(store.store.hashes.values()))
    for candidate in ("e4", "e5"):
        assert (candidate in fields) is (candidate == expected)


async def test_kova_ttl_alir() -> None:
    """TTL olmadan dakikalık kovalar sonsuza dek birikirdi."""
    store = _FakeAsyncRedis()
    await record_api_request(_as_async(store), duration_ms=10, status_code=200)

    assert all(ttl > 0 for ttl in store.store.ttls.values())


async def test_redis_yoksa_istek_bozulmaz() -> None:
    """Ölçüm hata-toleranslıdır: Redis kopsa da çağıran akış devam eder."""
    await record_api_request(cast("Redis", _BrokenRedis()), duration_ms=5, status_code=200)


def test_basarisiz_faz_sureye_degil_hata_sayacina_yazilir() -> None:
    """Yarıda kalan fazın süresi 'işleme ne kadar sürüyor'u değil, ne zaman patladığını ölçer."""
    store = _FakeRedis()
    record_job_phase("parsing", duration_seconds=12, ok=False, redis=cast("Any", store))

    fields = next(iter(store.store.hashes.values()))
    assert fields == {"parsing:n": 1, "parsing:fail": 1}


def test_basarili_faz_sure_kovasina_yazilir() -> None:
    store = _FakeRedis()
    record_job_phase("parsing", duration_seconds=45, ok=True, redis=cast("Any", store))

    fields = next(iter(store.store.hashes.values()))
    assert fields == {"parsing:n": 1, "parsing:le:60": 1}  # 30 < 45 ≤ 60


def test_worker_metrigi_redis_yoksa_isi_bozmaz() -> None:
    record_job_phase("parsing", duration_seconds=1, ok=True, redis=cast("Any", _BrokenRedis()))


async def test_anlik_goruntu_pencereyi_toplar() -> None:
    """API ve worker aynı pencereye yazar; okuma tarafı ikisini de görür."""
    shared = _Store()
    client = _as_async(_FakeAsyncRedis(shared))
    for _ in range(19):
        await record_api_request(client, duration_ms=40, status_code=200)
    await record_api_request(client, duration_ms=3000, status_code=500)
    record_job_phase(
        JOB_PHASE_TOTAL,
        duration_seconds=120,
        ok=True,
        redis=cast("Any", _FakeRedis(shared)),
    )
    shared.lists["tenderiq"] = 7

    snapshot = await collect_snapshot(client, window_minutes=5)

    assert snapshot.api.requests == 20
    assert snapshot.api.server_errors == 1
    assert snapshot.api.availability == pytest.approx(0.95)
    assert snapshot.api.p50_ms == 50  # çoğunluk 40 ms → 50 ms kovası
    assert snapshot.queue_depth == 7

    total = next(phase for phase in snapshot.phases if phase.phase == JOB_PHASE_TOTAL)
    assert total.completed == 1
    assert total.p95_seconds == 120


async def test_tek_yavas_istek_p95i_ucurmaz() -> None:
    """20 istekte 1 yavaş: p95 hızlı kovada kalır — yüzdelik tanımının kendisi budur."""
    client = _as_async(_FakeAsyncRedis())
    for _ in range(19):
        await record_api_request(client, duration_ms=40, status_code=200)
    await record_api_request(client, duration_ms=3000, status_code=200)

    snapshot = await collect_snapshot(client, window_minutes=5)

    assert snapshot.api.p95_ms == 50


async def test_cogunluk_yavaslayinca_p95_gorulur() -> None:
    """Yavaşlık yaygınlaşınca p95 kovası yukarı taşınır ve SLO ihlali doğar."""
    client = _as_async(_FakeAsyncRedis())
    for _ in range(10):
        await record_api_request(client, duration_ms=40, status_code=200)
    for _ in range(10):
        await record_api_request(client, duration_ms=900, status_code=200)

    snapshot = await collect_snapshot(client, window_minutes=5)

    assert snapshot.api.p95_ms == 1000
    breaching = {verdict.key for verdict in snapshot.breaching}
    assert "api_latency_p95" in breaching


async def test_bos_pencerede_slo_yargisi_verilmez() -> None:
    """Veri yokken SLO 'ihlal' sayılmaz — sessiz bir sistem, bozuk bir sistem değildir."""
    snapshot = await collect_snapshot(_as_async(_FakeAsyncRedis()), window_minutes=5)

    assert all(verdict.ok is None for verdict in snapshot.slos)
    assert snapshot.breaching == ()


def test_yuzdelik_esigi_asinca_slo_ihlal_edilir() -> None:
    api = ApiWindow(
        requests=100,
        server_errors=0,
        client_errors=0,
        p50_ms=100,
        p95_ms=SLO_API_P95_MS * 2,
    )
    phases = (
        PhaseWindow(
            phase=JOB_PHASE_TOTAL, completed=100, failed=0, p50_seconds=60, p95_seconds=120
        ),
    )

    verdicts = {verdict.key: verdict for verdict in evaluate_slos(api, phases)}

    assert verdicts["api_latency_p95"].ok is False
    assert verdicts["api_availability"].ok is True
    assert verdicts["processing_duration_p95"].ok is True
    assert verdicts["processing_success_rate"].ok is True


def test_isleme_basari_orani_esikte_tutar() -> None:
    """%98 hedefinde tam 98/100, ihlal DEĞİLDİR (sınır dâhil)."""
    phases = (
        PhaseWindow(phase=JOB_PHASE_TOTAL, completed=98, failed=2, p50_seconds=60, p95_seconds=60),
    )
    api = ApiWindow(requests=1, server_errors=0, client_errors=0, p50_ms=10, p95_ms=10)

    verdicts = {verdict.key: verdict for verdict in evaluate_slos(api, phases)}

    assert verdicts["processing_success_rate"].ok is True
