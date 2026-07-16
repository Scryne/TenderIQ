"""Oran sınırlama birim testleri — sahte Redis ile sayaç/fail-open davranışı."""

from __future__ import annotations

from typing import Any, cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from tenderiq_core.services.rate_limit import (
    RateLimitExceededError,
    check_rate_limit,
    reset_rate_limit,
)


class _FakePipeline:
    def __init__(self, store: _FakeRedis) -> None:
        self._store = store
        self._ops: list[tuple[Any, ...]] = []

    async def __aenter__(self) -> _FakePipeline:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def incr(self, key: str) -> None:
        self._ops.append(("incr", key))

    def expire(self, key: str, seconds: int, nx: bool = False) -> None:
        self._ops.append(("expire", key, seconds, nx))

    async def execute(self) -> list[Any]:
        results: list[Any] = []
        for op in self._ops:
            if op[0] == "incr":
                self._store.counters[op[1]] = self._store.counters.get(op[1], 0) + 1
                results.append(self._store.counters[op[1]])
            else:
                _, key, seconds, nx = op
                if not (nx and key in self._store.ttls):
                    self._store.ttls[key] = seconds
                results.append(True)
        return results


class _FakeRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        return _FakePipeline(self)

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -1)

    async def delete(self, key: str) -> int:
        existed = key in self.counters
        self.counters.pop(key, None)
        self.ttls.pop(key, None)
        return int(existed)


class _BrokenRedis:
    """Her işlemde bağlantı hatası veren Redis (fail-open doğrulaması)."""

    def pipeline(self, transaction: bool = True) -> Any:
        raise RedisConnectionError("redis kapalı")

    async def delete(self, key: str) -> int:
        raise RedisConnectionError("redis kapalı")


async def test_sinir_altinda_sessiz_gecer() -> None:
    fake = _FakeRedis()
    for _ in range(3):
        await check_rate_limit(
            cast(Redis, fake), scope="login:email", identifier="a@b.co", limit=3, window_seconds=60
        )
    assert fake.counters["rl:login:email:a@b.co"] == 3


async def test_sinir_asiminda_hata_ve_retry_after() -> None:
    fake = _FakeRedis()
    for _ in range(5):
        await check_rate_limit(
            cast(Redis, fake), scope="login:ip", identifier="1.2.3.4", limit=5, window_seconds=60
        )
    with pytest.raises(RateLimitExceededError) as excinfo:
        await check_rate_limit(
            cast(Redis, fake), scope="login:ip", identifier="1.2.3.4", limit=5, window_seconds=60
        )
    assert excinfo.value.retry_after_seconds == 60


async def test_farkli_ozneler_ayri_sayilir() -> None:
    fake = _FakeRedis()
    await check_rate_limit(
        cast(Redis, fake), scope="login:email", identifier="a@b.co", limit=1, window_seconds=60
    )
    # Farklı e-posta aynı pencerede sınırdan etkilenmez.
    await check_rate_limit(
        cast(Redis, fake), scope="login:email", identifier="c@d.co", limit=1, window_seconds=60
    )


async def test_sifirlama_pencereyi_temizler() -> None:
    """Başarılı girişte sayaç silinir; sonraki denemeler taze pencereden sayılır."""
    fake = _FakeRedis()
    for _ in range(5):
        await check_rate_limit(
            cast(Redis, fake), scope="login:email", identifier="a@b.co", limit=5, window_seconds=60
        )
    await reset_rate_limit(cast(Redis, fake), scope="login:email", identifier="a@b.co")
    # Sıfırlama olmasaydı bu 6. deneme RateLimitExceededError yükseltirdi.
    await check_rate_limit(
        cast(Redis, fake), scope="login:email", identifier="a@b.co", limit=5, window_seconds=60
    )
    assert fake.counters["rl:login:email:a@b.co"] == 1


async def test_sifirlama_redis_hatasinda_sessiz() -> None:
    await reset_rate_limit(cast(Redis, _BrokenRedis()), scope="login:email", identifier="a@b.co")


async def test_redis_hatasinda_fail_open() -> None:
    # Redis'e ulaşılamıyorsa kimlik doğrulama engellenmez (yalnızca log).
    await check_rate_limit(
        cast(Redis, _BrokenRedis()),
        scope="login:ip",
        identifier="1.2.3.4",
        limit=1,
        window_seconds=60,
    )
