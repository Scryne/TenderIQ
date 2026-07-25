"""Refresh token rotasyonu birim testleri — sahte Redis ile atomiklik + grace.

Kritik davranış (bkz. services.refresh_tokens modül docstring'i): tek bir sayfa
yüklemesi çok sayıda paralel API çağrısı üretir; erişim token'ı dolmuşsa hepsi
AYNI refresh token'la yenileme ister. Bu meşru eşzamanlılık oturumu ÖLDÜRMEMELİ,
ama grace penceresi dışındaki tekrar hâlâ hırsızlık sayılmalıdır.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from redis.asyncio import Redis

from tenderiq_core.services import refresh_tokens
from tenderiq_core.services.refresh_tokens import (
    InvalidRefreshTokenError,
    RefreshIdentity,
    ReusedRefreshTokenError,
    issue_refresh_token,
    revoke_all_for_user,
    revoke_refresh_token,
    revoke_user_sessions_for_tenant,
    rotate_refresh_token,
)

TTL = 3600


class _FakePipeline:
    def __init__(self, store: _FakeRedis) -> None:
        self._store = store
        self._ops: list[tuple[Any, ...]] = []

    async def __aenter__(self) -> _FakePipeline:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._ops.append(("set", key, value))

    def sadd(self, key: str, member: str) -> None:
        self._ops.append(("sadd", key, member))

    def expire(self, key: str, seconds: int) -> None:
        self._ops.append(("expire", key, seconds))

    async def execute(self) -> list[Any]:
        for op in self._ops:
            if op[0] == "set":
                self._store.values[op[1]] = op[2]
            elif op[0] == "sadd":
                self._store.sets.setdefault(op[1], set()).add(op[2])
        return [True] * len(self._ops)


class _FakeRedis:
    """Testin ihtiyaç duyduğu Redis alt kümesi (string + set + SET NX)."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        return _FakePipeline(self)

    async def get(self, key: str) -> bytes | None:
        value = self.values.get(key)
        return value.encode() if value is not None else None

    async def set(
        self, key: str, value: str, ex: int | None = None, nx: bool = False
    ) -> bool | None:
        # redis-py sözleşmesi: NX çakışırsa None döner (yazma olmaz).
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            removed += self.values.pop(key, None) is not None
            removed += self.sets.pop(key, None) is not None
        return removed

    async def smembers(self, key: str) -> set[bytes]:
        return {member.encode() for member in self.sets.get(key, set())}


class _Clock:
    """Monotonik olmayan, testin sürdüğü saat (modülün ``time`` bağımlılığı)."""

    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def time(self) -> float:
        return self.value


def _redis() -> Redis:
    return cast("Redis", _FakeRedis())


def _identity() -> RefreshIdentity:
    return RefreshIdentity(user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role="admin")


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr(refresh_tokens, "time", fake)
    return fake


async def test_rotasyon_yeni_token_verir_ve_kimligi_korur(clock: _Clock) -> None:
    redis = _redis()
    identity = _identity()
    token = await issue_refresh_token(redis, identity=identity, ttl_seconds=TTL)

    rotated = await rotate_refresh_token(redis, token, ttl_seconds=TTL)

    assert rotated.token != token
    assert rotated.identity == identity


async def test_paralel_yenileme_oturumu_oldurmez(clock: _Clock) -> None:
    """D-01: aynı token'la gelen eşzamanlı yenilemeler aileyi iptal ETMEMELİ.

    İnceleme ekranı tek yüklemede 7 paralel istek atar; erişim token'ı dolduğunda
    hepsi aynı refresh token'ı sunar. Eski davranışta ikincisi reuse sayılıp tüm
    aileyi (birincinin az önce aldığı token dâhil) iptal ediyor, kullanıcıyı
    login'e atıyordu.
    """
    redis = _redis()
    identity = _identity()
    token = await issue_refresh_token(redis, identity=identity, ttl_seconds=TTL)

    first = await rotate_refresh_token(redis, token, ttl_seconds=TTL)
    second = await rotate_refresh_token(redis, token, ttl_seconds=TTL)

    assert second.identity == identity
    assert second.token != first.token
    # Kritik: birincinin token'ı hâlâ yaşamalı (aile iptal edilmedi).
    still_valid = await rotate_refresh_token(redis, first.token, ttl_seconds=TTL)
    assert still_valid.identity == identity


async def test_grace_disinda_tekrar_hirsizlik_sayilir(clock: _Clock) -> None:
    redis = _redis()
    identity = _identity()
    token = await issue_refresh_token(redis, identity=identity, ttl_seconds=TTL)
    rotated = await rotate_refresh_token(redis, token, ttl_seconds=TTL)

    clock.value += refresh_tokens.REUSE_GRACE_SECONDS + 1
    with pytest.raises(ReusedRefreshTokenError):
        await rotate_refresh_token(redis, token, ttl_seconds=TTL)

    # Aile iptal edildi: rotasyonla verilen taze token da artık geçersiz.
    with pytest.raises(InvalidRefreshTokenError):
        await rotate_refresh_token(redis, rotated.token, ttl_seconds=TTL)


async def test_grace_sinirinda_kabul_edilir(clock: _Clock) -> None:
    redis = _redis()
    token = await issue_refresh_token(redis, identity=_identity(), ttl_seconds=TTL)
    await rotate_refresh_token(redis, token, ttl_seconds=TTL)

    clock.value += refresh_tokens.REUSE_GRACE_SECONDS  # tam sınır: hâlâ içeride
    assert await rotate_refresh_token(redis, token, ttl_seconds=TTL) is not None


async def test_bilinmeyen_token_gecersiz(clock: _Clock) -> None:
    redis = _redis()
    with pytest.raises(InvalidRefreshTokenError):
        await rotate_refresh_token(redis, "bilinmeyen-token", ttl_seconds=TTL)


async def test_eski_kayit_bicimi_reuse_sayilir(clock: _Clock) -> None:
    """Grace öncesi biçimde (``used`` token kaydında) üretilmiş token geriye dönük reddedilir."""
    redis = _redis()
    store = cast("_FakeRedis", redis)
    token = await issue_refresh_token(redis, identity=_identity(), ttl_seconds=TTL)
    key = next(k for k in store.values if k.startswith("rt:"))
    store.values[key] = store.values[key].replace("}", ', "used": true}')

    with pytest.raises(ReusedRefreshTokenError):
        await rotate_refresh_token(redis, token, ttl_seconds=TTL)


async def test_logout_aileyi_iptal_eder(clock: _Clock) -> None:
    redis = _redis()
    token = await issue_refresh_token(redis, identity=_identity(), ttl_seconds=TTL)

    await revoke_refresh_token(redis, token)

    with pytest.raises(InvalidRefreshTokenError):
        await rotate_refresh_token(redis, token, ttl_seconds=TTL)


async def test_iptal_tuketim_isaretini_de_temizler(clock: _Clock) -> None:
    """Aile iptali ``rtused:`` anahtarlarını bırakmamalı (bayat işaret kalmasın)."""
    redis = _redis()
    store = cast("_FakeRedis", redis)
    token = await issue_refresh_token(redis, identity=_identity(), ttl_seconds=TTL)
    await rotate_refresh_token(redis, token, ttl_seconds=TTL)
    assert any(key.startswith("rtused:") for key in store.values)

    await revoke_refresh_token(redis, token)

    assert not any(key.startswith("rtused:") for key in store.values)


async def test_parola_sifirlama_tum_aileleri_iptal_eder(clock: _Clock) -> None:
    redis = _redis()
    identity = _identity()
    first = await issue_refresh_token(redis, identity=identity, ttl_seconds=TTL)
    second = await issue_refresh_token(redis, identity=identity, ttl_seconds=TTL)

    await revoke_all_for_user(redis, identity.user_id)

    for token in (first, second):
        with pytest.raises(InvalidRefreshTokenError):
            await rotate_refresh_token(redis, token, ttl_seconds=TTL)


async def test_uyelik_iptali_yalniz_hedef_kiracinin_oturumunu_duserur(clock: _Clock) -> None:
    """D-05: üyeyi çıkarmak, kullanıcının BAŞKA org'lardaki oturumunu etkilememeli."""
    redis = _redis()
    user_id = uuid.uuid4()
    removed_tenant = uuid.uuid4()
    other_tenant = uuid.uuid4()
    removed = await issue_refresh_token(
        redis,
        identity=RefreshIdentity(user_id=user_id, tenant_id=removed_tenant, role="member"),
        ttl_seconds=TTL,
    )
    kept = await issue_refresh_token(
        redis,
        identity=RefreshIdentity(user_id=user_id, tenant_id=other_tenant, role="admin"),
        ttl_seconds=TTL,
    )

    await revoke_user_sessions_for_tenant(redis, user_id, removed_tenant)

    with pytest.raises(InvalidRefreshTokenError):
        await rotate_refresh_token(redis, removed, ttl_seconds=TTL)
    survivor = await rotate_refresh_token(redis, kept, ttl_seconds=TTL)
    assert survivor.identity.tenant_id == other_tenant
