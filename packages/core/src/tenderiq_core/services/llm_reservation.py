"""LLM bütçe rezervasyonu — eşzamanlı işlerin tavanı BİRLİKTE aşmasını engeller.

## Neden yalnız "harcanan < tavan" bakmak yetmez

Harcama iş BİTTİKTEN sonra yazılır. Aynı anda başlayan iki iş de "harcanan"ı
aynı (düşük) değerde görür, ikisi de geçer ve tavan birlikte aşılır. Rezervasyon
bu boşluğu kapatır: kabul anında muhafazakâr bir tutar ayrılır, karar
``harcanan + rezerve`` üzerinden verilir. Aşım böylece
**(eşzamanlılık × rezervasyon tahmini)** ile sınırlı kalır — sınırsız değil.

## Neden Lua

"Topla, karşılaştır, yaz" üç ayrı komut olsaydı arada başka bir işçi araya
girebilirdi — yani yarışı kapatmak için eklenen mekanizmanın kendisi yarışırdı.
Lua betiği Redis'te tek adımda koşar.

## Sızıntı: her rezervasyon kendi son kullanma damgasını taşır

Worker çökerse ``release`` hiç çağrılmaz. Bu yüzden tutar değil,
``tutar:son_kullanma`` saklanır ve toplam alınırken süresi geçmişler SAYILMAZ
(ayrıca fırsat buldukça silinir). Çöken bir worker kiracıyı kendi tavanına
kilitlemez; en fazla TTL kadar rezerve görünür.

## Redis kesintisi

Bu modül kesintiyi YUTMAZ; hatayı yükseltir. Karar (muhafazakâr DB kontrolüne
düşmek) çağıran katmanın işidir — bkz. ``services.llm_budget``. E-posta
yolundaki "kesintide korumayı atla" kuralı burada GEÇERLİ DEĞİL: orada risk
kaybolan bir mesajdı, burada sınırsız harcama.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.services.llm_reservation")

#: Alan değeri: "<mikro_tl>:<unix_son_kullanma>".
_KEY_PREFIX = "llm:reserved"

#: Atomik "topla + karar ver + rezerve et".
#:
#: KEYS[1] = hash anahtarı, ARGV[1] = iş kimliği, ARGV[2] = istenen tutar,
#: ARGV[3] = kalan bütçe (tavan - harcanan), ARGV[4] = şimdi (unix),
#: ARGV[5] = son kullanma (unix), ARGV[6] = hash TTL'i.
#: Dönüş: {kabul(0/1), mevcut_rezerve_toplam}
_RESERVE_LUA = """
local key, job = KEYS[1], ARGV[1]
local amount, remaining = tonumber(ARGV[2]), tonumber(ARGV[3])
local now, expires_at, ttl = tonumber(ARGV[4]), ARGV[5], tonumber(ARGV[6])

local total = 0
local entries = redis.call('HGETALL', key)
for i = 1, #entries, 2 do
  local field, value = entries[i], entries[i + 1]
  local sep = string.find(value, ':')
  local value_amount = tonumber(string.sub(value, 1, sep - 1))
  local value_expiry = tonumber(string.sub(value, sep + 1))
  if value_expiry and value_expiry <= now then
    -- Sahipsiz kalmış rezervasyon: sayma ve temizle.
    redis.call('HDEL', key, field)
  elseif field ~= job then
    total = total + value_amount
  end
end

if total + amount > remaining then
  return {0, total}
end

redis.call('HSET', key, job, amount .. ':' .. expires_at)
redis.call('EXPIRE', key, ttl)
return {1, total + amount}
"""


def _key(tenant_id: uuid.UUID, period_key: str) -> str:
    return f"{_KEY_PREFIX}:{tenant_id}:{period_key}"


def try_reserve(
    redis: Any,
    *,
    tenant_id: uuid.UUID,
    period_key: str,
    job_id: uuid.UUID,
    amount_micros: int,
    remaining_micros: int,
    ttl_seconds: int,
) -> tuple[bool, int]:
    """Atomik rezervasyon denemesi.

    ``(kabul_edildi, rezerve_toplam_mikro)`` döndürür. Redis hatası YUTULMAZ.
    """
    now = int(time.time())
    result = redis.eval(
        _RESERVE_LUA,
        1,
        _key(tenant_id, period_key),
        str(job_id),
        str(int(amount_micros)),
        str(int(remaining_micros)),
        str(now),
        str(now + ttl_seconds),
        str(ttl_seconds),
    )
    accepted = bool(int(result[0]))
    total = int(result[1])
    return accepted, total


def release(redis: Any, *, tenant_id: uuid.UUID, period_key: str, job_id: uuid.UUID) -> None:
    """Rezervasyonu bırakır (iş bitti; gerçek maliyet artık kayıtta).

    Hata YUTULUR: bırakamamak işi bozmamalı, TTL zaten üst sınırdır.
    """
    try:
        redis.hdel(_key(tenant_id, period_key), str(job_id))
    except Exception as exc:  # pragma: no cover - Redis kesintisi
        logger.warning("llm_rezervasyon_birakilamadi", error=str(exc), job_id=str(job_id))


def _sum_unexpired(values: Any, now: int) -> int:
    """Hash değerlerinden süresi geçmemiş rezervasyonları toplar (mikro-TL)."""
    total = 0
    for value in values:
        raw = value.decode() if isinstance(value, bytes) else str(value)
        amount_text, _, expiry_text = raw.partition(":")
        try:
            if int(expiry_text) > now:
                total += int(amount_text)
        except ValueError:  # pragma: no cover - bozuk alan
            continue
    return total


def reserved_total(redis: Any, *, tenant_id: uuid.UUID, period_key: str) -> int:
    """Süresi geçmemiş rezervasyonların toplamı (mikro-TL). Senkron/worker."""
    return _sum_unexpired(redis.hgetall(_key(tenant_id, period_key)).values(), int(time.time()))


async def reserved_total_async(redis: Any, *, tenant_id: uuid.UUID, period_key: str) -> int:
    """`reserved_total`ın async ikizi — API tarafı (yönetici görünürlüğü).

    Ayrıştırma mantığı paylaşılır; yalnız Redis çağrısı farklıdır. Aksi hâlde
    "süresi geçmişi sayma" kuralı iki yerde yaşar ve biri güncellenmeden kalır.
    """
    values = await redis.hgetall(_key(tenant_id, period_key))
    return _sum_unexpired(values.values(), int(time.time()))
