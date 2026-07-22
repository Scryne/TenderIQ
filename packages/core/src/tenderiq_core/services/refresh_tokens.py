"""Rotasyonlu, tek-kullanımlık refresh token'lar (Redis) — oturum yaşam döngüsü (3.3-C).

Refresh token, backend'te SAKLANMAYAN yüksek-entropili opak bir dizedir; Redis'te
yalnızca SHA-256 **özeti** tutulur (veri sızıntısında tersine çevrilemez). Her
kullanımda rotasyon uygulanır: sunulan token "kullanıldı" işaretlenir ve aynı
**aileden** (family) yeni bir token verilir. Kullanılmış bir token yeniden
sunulursa hırsızlık varsayılır ve tüm aile iptal edilir (reuse detection). Çıkış
(logout) aileyi iptal eder.

Redis'e ulaşılamazsa doğrulama/rotasyon **fail-CLOSED**'dur (kimlik güvenliği
erişilebilirlikten önce gelir); ``RedisError`` çağırana yükselir, o da 401/503'e
eşler. Yalnızca giriş anındaki token ÜRETİMİ, oturum açmayı Redis'e bağımlı
kılmamak için çağıran tarafından fail-open ele alınabilir.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis

_TOKEN_PREFIX = "rt"  # noqa: S105 - Redis anahtar ön-eki, parola değil
_FAMILY_PREFIX = "rtfam"
_USER_PREFIX = "rtuser"  # kullanıcı → aile indeksi (tüm oturumları iptal için)
_TOKEN_BYTES = 32  # 256-bit entropi (secrets.token_urlsafe)


class InvalidRefreshTokenError(Exception):
    """Refresh token bulunamadı, süresi doldu veya biçimi bozuk."""


class ReusedRefreshTokenError(Exception):
    """Kullanılmış bir token yeniden sunuldu → aile iptal edildi (olası hırsızlık)."""


@dataclass(frozen=True)
class RefreshIdentity:
    """Refresh token'a bağlı kimlik (yeni erişim token'ı bundan üretilir)."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


@dataclass(frozen=True)
class RotatedRefresh:
    """Rotasyon sonucu: kimlik + yeni (tek-kullanımlık) refresh token."""

    identity: RefreshIdentity
    token: str


def _hash(token: str) -> str:
    """Token'ın Redis anahtarı olarak kullanılan SHA-256 özeti (ham token saklanmaz)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_key(token_hash: str) -> str:
    return f"{_TOKEN_PREFIX}:{token_hash}"


def _family_key(family: str) -> str:
    return f"{_FAMILY_PREFIX}:{family}"


def _user_key(user_id: str) -> str:
    return f"{_USER_PREFIX}:{user_id}"


async def issue_refresh_token(
    redis: Redis, *, identity: RefreshIdentity, ttl_seconds: int, family: str | None = None
) -> str:
    """Yeni bir refresh token üretir, özetini Redis'e yazar ve ham token'ı döndürür.

    ``family`` verilirse token o aileye eklenir (rotasyon); verilmezse yeni bir
    aile başlatılır (yeni giriş). Aile kümesi, reuse-detection'da tüm zinciri
    iptal edebilmek için token özetlerini tutar.
    """
    family = family or uuid.uuid4().hex
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    token_hash = _hash(token)
    record = json.dumps(
        {
            "user_id": str(identity.user_id),
            "tenant_id": str(identity.tenant_id),
            "role": identity.role,
            "family": family,
            "used": False,
        }
    )
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(_token_key(token_hash), record, ex=ttl_seconds)
        pipe.sadd(_family_key(family), token_hash)
        pipe.expire(_family_key(family), ttl_seconds)
        # Kullanıcı → aile indeksi: parola sıfırlamada tüm oturumları iptal etmek için.
        pipe.sadd(_user_key(str(identity.user_id)), family)
        pipe.expire(_user_key(str(identity.user_id)), ttl_seconds)
        await pipe.execute()
    return token


async def _revoke_family(redis: Redis, family: str) -> None:
    """Bir ailenin tüm token'larını ve aile kümesini siler (iptal)."""
    # redis-py senkron/async paylaşımlı stub'ı smembers'ı birleşik tiple döndürür;
    # async istemcide gerçek dönüş awaitable'dır (cast yalnız tip daraltması).
    members = await cast("Awaitable[set[bytes]]", redis.smembers(_family_key(family)))
    keys = [
        _token_key(member.decode() if isinstance(member, bytes) else member) for member in members
    ]
    keys.append(_family_key(family))
    await redis.delete(*keys)


async def rotate_refresh_token(redis: Redis, token: str, *, ttl_seconds: int) -> RotatedRefresh:
    """Bir refresh token'ı doğrular, tek-kullanım işaretler ve aynı aileden yenisini verir.

    - Token yoksa/süresi dolmuşsa: ``InvalidRefreshTokenError``.
    - Token zaten kullanılmışsa: aile iptal edilir + ``ReusedRefreshTokenError``.
    """
    token_hash = _hash(token)
    raw = await redis.get(_token_key(token_hash))
    if raw is None:
        raise InvalidRefreshTokenError
    data = json.loads(raw)
    family: str = data["family"]
    if data.get("used"):
        await _revoke_family(redis, family)
        raise ReusedRefreshTokenError
    # Tek-kullanım: mevcut token'ı "kullanıldı" işaretle (TTL korunur), sonra rotasyon.
    data["used"] = True
    await redis.set(_token_key(token_hash), json.dumps(data), keepttl=True)
    identity = RefreshIdentity(
        user_id=uuid.UUID(data["user_id"]),
        tenant_id=uuid.UUID(data["tenant_id"]),
        role=data["role"],
    )
    new_token = await issue_refresh_token(
        redis, identity=identity, ttl_seconds=ttl_seconds, family=family
    )
    return RotatedRefresh(identity=identity, token=new_token)


async def revoke_refresh_token(redis: Redis, token: str) -> None:
    """Bir token'ın ait olduğu tüm aileyi iptal eder (logout / güvenlik iptali).

    Token bulunamazsa sessizce döner (idempotent).
    """
    token_hash = _hash(token)
    raw = await redis.get(_token_key(token_hash))
    if raw is None:
        return
    data = json.loads(raw)
    await _revoke_family(redis, data["family"])


async def revoke_all_for_user(redis: Redis, user_id: uuid.UUID) -> None:
    """Bir kullanıcının TÜM oturumlarını (aileler) iptal eder (ör. parola sıfırlama).

    Kullanıcı → aile indeksinden tüm aileler okunur, her biri iptal edilir ve
    indeks silinir. İndeks yoksa (hiç aktif oturum yok) sessizce döner.
    """
    families = await cast("Awaitable[set[bytes]]", redis.smembers(_user_key(str(user_id))))
    for family in families:
        await _revoke_family(redis, family.decode() if isinstance(family, bytes) else family)
    await redis.delete(_user_key(str(user_id)))
