"""Rotasyonlu, tek-kullanımlık refresh token'lar (Redis) — oturum yaşam döngüsü (3.3-C).

Refresh token, backend'te SAKLANMAYAN yüksek-entropili opak bir dizedir; Redis'te
yalnızca SHA-256 **özeti** tutulur (veri sızıntısında tersine çevrilemez). Her
kullanımda rotasyon uygulanır: sunulan token "kullanıldı" işaretlenir ve aynı
**aileden** (family) yeni bir token verilir. Kullanılmış bir token yeniden
sunulursa hırsızlık varsayılır ve tüm aile iptal edilir (reuse detection). Çıkış
(logout) aileyi iptal eder.

Tüketim işareti AYRI bir anahtara (``rtused:``) ``SET NX`` ile yazılır; kazananı
Redis atomik olarak seçer. Buna ek olarak kısa bir **grace penceresi**
(``REUSE_GRACE_SECONDS``) vardır: tek bir sayfa yüklemesi çok sayıda paralel API
çağrısı üretir ve erişim token'ı dolmuşsa hepsi AYNI refresh token'la aynı anda
yenileme ister. Bu meşru eşzamanlılık hırsızlık değildir — pencere içindeki
tekrarlar aileyi iptal etmez, her biri aynı aileden kendi yeni token'ını alır
(kullanılmayanlar TTL'de ölür). Pencere dışındaki tekrar gerçek reuse sayılır.

Redis'e ulaşılamazsa doğrulama/rotasyon **fail-CLOSED**'dur (kimlik güvenliği
erişilebilirlikten önce gelir); ``RedisError`` çağırana yükselir, o da 401/503'e
eşler. Yalnızca giriş anındaki token ÜRETİMİ, oturum açmayı Redis'e bağımlı
kılmamak için çağıran tarafından fail-open ele alınabilir.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis

_TOKEN_PREFIX = "rt"  # noqa: S105 - Redis anahtar ön-eki, parola değil
_FAMILY_PREFIX = "rtfam"
_USER_PREFIX = "rtuser"  # kullanıcı → aile indeksi (tüm oturumları iptal için)
_USED_PREFIX = "rtused"  # token → ilk tüketim zamanı (atomik tek-kullanım işareti)
_TOKEN_BYTES = 32  # 256-bit entropi (secrets.token_urlsafe)

# Aynı token'la gelen eşzamanlı yenilemelerin hırsızlık SAYILMADIĞI pencere.
# Tek sayfa yüklemesindeki paralel istekler saniyenin altında toplanır; 10 sn
# rahat bir tavandır ve çalınmış bir token'ın istismar penceresini anlamlı
# ölçüde genişletmez (asıl savunma kısa TTL + rotasyon + aile iptalidir).
REUSE_GRACE_SECONDS = 10


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


def _used_key(token_hash: str) -> str:
    return f"{_USED_PREFIX}:{token_hash}"


def _as_int(raw: object) -> int | None:
    """Redis'ten dönen (bytes|str|None) değeri tam sayıya çevirir; bozuksa None."""
    if raw is None:
        return None
    text = raw.decode() if isinstance(raw, bytes) else str(raw)
    try:
        return int(text)
    except ValueError:  # pragma: no cover - bozuk kayıt teorik
        return None


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
    """Bir ailenin tüm token'larını, tüketim işaretlerini ve aile kümesini siler."""
    # redis-py senkron/async paylaşımlı stub'ı smembers'ı birleşik tiple döndürür;
    # async istemcide gerçek dönüş awaitable'dır (cast yalnız tip daraltması).
    members = await cast("Awaitable[set[bytes]]", redis.smembers(_family_key(family)))
    hashes = [member.decode() if isinstance(member, bytes) else member for member in members]
    keys = [_token_key(token_hash) for token_hash in hashes]
    # Tüketim işaretleri de gitmeli: kalırlarsa aynı özetle üretilecek bir sonraki
    # token (teorik) doğrudan "kullanılmış" görünürdü.
    keys.extend(_used_key(token_hash) for token_hash in hashes)
    keys.append(_family_key(family))
    await redis.delete(*keys)


async def rotate_refresh_token(
    redis: Redis,
    token: str,
    *,
    ttl_seconds: int,
    grace_seconds: int = REUSE_GRACE_SECONDS,
) -> RotatedRefresh:
    """Bir refresh token'ı doğrular, tek-kullanım işaretler ve aynı aileden yenisini verir.

    - Token yoksa/süresi dolmuşsa: ``InvalidRefreshTokenError``.
    - Token ``grace_seconds`` DIŞINDA yeniden sunulmuşsa: aile iptal edilir +
      ``ReusedRefreshTokenError``.
    - Pencere İÇİNDEKİ tekrar (paralel yenileme) kabul edilir; çağıran kendi yeni
      token'ını alır (modül docstring'indeki gerekçe).
    """
    token_hash = _hash(token)
    raw = await redis.get(_token_key(token_hash))
    if raw is None:
        raise InvalidRefreshTokenError
    data = json.loads(raw)
    family: str = data["family"]
    if data.get("used"):
        # Eski kayıt biçimi (tüketim token kaydına yazılırdı): grace öncesi
        # üretilmiş kullanılmış token — geriye dönük olarak reuse sayılır.
        await _revoke_family(redis, family)
        raise ReusedRefreshTokenError
    now = int(time.time())
    # Tek-kullanımı Redis atomik seçer: SET NX kazananı belirler. Eski
    # GET-then-SET sırası, aynı token'la gelen eşzamanlı iki yenilemenin ikisini
    # birden "kullanılmamış" görmesine izin veriyordu.
    claimed = await redis.set(_used_key(token_hash), str(now), nx=True, ex=ttl_seconds)
    if not claimed:
        first_used = _as_int(await redis.get(_used_key(token_hash)))
        # ``grace_seconds <= 0`` AÇIKÇA "tolerans yok" demektir. Yalnız
        # ``now - first_used > grace_seconds`` bakmak yetmez: zaman damgası saniye
        # çözünürlüklü olduğundan aynı saniyedeki tekrar 0 > 0 ile yanlışlıkla
        # meşru sayılırdı — yani 0 ayarı sessizce "aynı saniyeye tolerans"a
        # dönüşürdü.
        if first_used is None or grace_seconds <= 0 or now - first_used > grace_seconds:
            await _revoke_family(redis, family)
            raise ReusedRefreshTokenError
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


async def revoke_user_sessions_for_tenant(
    redis: Redis, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    """Kullanıcının YALNIZCA bir organizasyondaki oturumlarını iptal eder.

    Üyelik kaldırıldığında kullanılır. Kullanıcının başka kiracılardaki oturumları
    korunur: bir org yöneticisinin işlemi, o kullanıcının başka müşterilerdeki
    oturumlarını düşürmemelidir (kiracı sınırı). Aile→kiracı eşlemesi, ailenin
    herhangi bir canlı token kaydından okunur.
    """
    families = await cast("Awaitable[set[bytes]]", redis.smembers(_user_key(str(user_id))))
    target = str(tenant_id)
    for raw_family in families:
        family = raw_family.decode() if isinstance(raw_family, bytes) else raw_family
        members = await cast("Awaitable[set[bytes]]", redis.smembers(_family_key(family)))
        for member in members:
            token_hash = member.decode() if isinstance(member, bytes) else member
            record = await redis.get(_token_key(token_hash))
            if record is None:
                continue  # süresi dolmuş/iptal edilmiş girdi; sıradakine bak
            if json.loads(record).get("tenant_id") == target:
                await _revoke_family(redis, family)
            break  # ailenin kiracısı tek bir kayıttan belirlenir


async def revoke_all_for_user(redis: Redis, user_id: uuid.UUID) -> None:
    """Bir kullanıcının TÜM oturumlarını (aileler) iptal eder (ör. parola sıfırlama).

    Kullanıcı → aile indeksinden tüm aileler okunur, her biri iptal edilir ve
    indeks silinir. İndeks yoksa (hiç aktif oturum yok) sessizce döner.
    """
    families = await cast("Awaitable[set[bytes]]", redis.smembers(_user_key(str(user_id))))
    for family in families:
        await _revoke_family(redis, family.decode() if isinstance(family, bytes) else family)
    await redis.delete(_user_key(str(user_id)))
