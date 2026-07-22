"""Amaç-kapsamlı, tek-kullanımlık, süreli token'lar (Redis) — 3.3-D.

E-posta doğrulama ve parola sıfırlama gibi akışlar için yüksek-entropili opak
token'lar üretir; Redis'te yalnızca token'ın SHA-256 **özeti** + hedef kullanıcı
tutulur (sızıntıda tersine çevrilemez). Tüketim ``GETDEL`` ile **atomiktir**:
token bir kez kullanılır ve yarış olmadan silinir. TTL ile süre-sınırlıdır.

Redis erişilemezken üretim/tüketim ``RedisError`` yükseltir (fail-closed);
çağıran uygun HTTP durumuna eşler.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis

# Token amacı (Redis anahtar ad alanını ayırır: bir amacın token'ı diğerinde geçmez).
EMAIL_VERIFY = "email_verify"
PASSWORD_RESET = "password_reset"  # noqa: S105 - amaç adı, parola değil

_KEY_PREFIX = "ott"
_TOKEN_BYTES = 32  # 256-bit entropi


class InvalidOneTimeTokenError(Exception):
    """Token bulunamadı, süresi doldu veya zaten kullanıldı."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _key(purpose: str, token_hash: str) -> str:
    return f"{_KEY_PREFIX}:{purpose}:{token_hash}"


async def issue(redis: Redis, *, purpose: str, user_id: uuid.UUID, ttl_seconds: int) -> str:
    """Bir amaç için tek-kullanımlık token üretir ve ham token'ı döndürür."""
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    await redis.set(_key(purpose, _hash(token)), str(user_id), ex=ttl_seconds)
    return token


async def consume(redis: Redis, *, purpose: str, token: str) -> uuid.UUID:
    """Token'ı doğrular ve **atomik** olarak tüketir (GETDEL); hedef kullanıcıyı döndürür.

    Geçersiz/süresi dolmuş/kullanılmış token → ``InvalidOneTimeTokenError``.
    """
    raw = await cast("Awaitable[bytes | None]", redis.getdel(_key(purpose, _hash(token))))
    if raw is None:
        raise InvalidOneTimeTokenError
    value = raw.decode() if isinstance(raw, bytes) else raw
    try:
        return uuid.UUID(value)
    except ValueError as exc:  # pragma: no cover - bozuk kayıt teorik
        raise InvalidOneTimeTokenError from exc
