"""LLM fiyat tablosu ve maliyet hesabı (J.6).

## Neden dosyadan okunuyor

Fiyatlar sağlayıcının ilanına bağlıdır ve kod sürümünden bağımsız değişir.
Kodda sabit rakam tutmak, fiyat değiştiğinde faturayı sessizce yanlış
hesaplamak demektir. Tablo `LLM_PRICING_PATH` ile değiştirilebilir.

## Para birimi

Sağlayıcılar USD/1M token ilan eder; planlar ve tavanlar TL cinsindendir.
Dönüşüm `LLM_USD_TRY_RATE` ile yapılır. **Kur tanımlı değilse maliyet
HESAPLANMAZ** — 0 TL yazmak, tavanı sessizce sonsuz yapardı. Kayıt bu durumda
`pricing_status="no_fx_rate"` ile işaretlenir.

## Belirsizliği gizlememe kuralı

Üç durum ayrı ayrı işaretlenir ve hiçbiri "0 TL" ile karıştırılmaz:

- ``unknown_model`` — model tabloda yok (yeni model eklenmiş, tablo güncellenmemiş).
- ``no_fx_rate`` — kur yok.
- ``unverified`` — fiyat tabloda var ama sağlayıcıya karşı doğrulanmamış;
  tutar hesaplanır ama TAHMİN olduğu kayıtta durur.

Yalnız ``priced`` durumundaki tutar kesin sayılır.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from tenderiq_core.config import Settings, get_settings
from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.llm.pricing")

#: 1 TL = 1_000_000 mikro-TL. Tutarlar tam sayı tutulur: float toplamı büyük
#: hacimde sapar ve tavan karşılaştırmasını güvenilmez yapar.
MICROS_PER_TRY = 1_000_000
_TOKENS_PER_UNIT = 1_000_000


class PricingStatus(StrEnum):
    """Bir kaydın maliyetinin ne kadar güvenilir olduğu."""

    PRICED = "priced"
    UNVERIFIED = "unverified"
    UNKNOWN_MODEL = "unknown_model"
    NO_FX_RATE = "no_fx_rate"


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Bir modelin 1M token başına USD fiyatı."""

    input_per_mtok_usd: float
    output_per_mtok_usd: float
    verified: bool


@dataclass(frozen=True, slots=True)
class PricingTable:
    """Yüklenmiş fiyat tablosu + kur."""

    models: dict[str, ModelPrice]
    usd_try_rate: float | None
    source: str

    def cost_micros_try(
        self, model: str, *, input_tokens: int, output_tokens: int
    ) -> tuple[int, PricingStatus]:
        """Tutarı mikro-TL cinsinden hesaplar ve GÜVENİLİRLİĞİNİ döndürür.

        Hesaplanamayan hâllerde tutar 0'dır ama durum bunu açıkça söyler —
        çağıran taraf 0'ı "bedava" sanmamalıdır.
        """
        price = self.models.get(model)
        if price is None:
            return 0, PricingStatus.UNKNOWN_MODEL
        if self.usd_try_rate is None:
            return 0, PricingStatus.NO_FX_RATE

        usd = (
            input_tokens * price.input_per_mtok_usd + output_tokens * price.output_per_mtok_usd
        ) / _TOKENS_PER_UNIT
        micros = round(usd * self.usd_try_rate * MICROS_PER_TRY)
        status = PricingStatus.PRICED if price.verified else PricingStatus.UNVERIFIED
        return micros, status


def _resolve_path(settings: Settings) -> Path:
    path = Path(settings.llm_pricing_path)
    if path.is_absolute():
        return path
    # Depo kökü: packages/core/src/tenderiq_core/llm/pricing.py → 5 seviye yukarı.
    return Path(__file__).resolve().parents[5] / path


_cache: dict[str, PricingTable] = {}


def load_pricing(settings: Settings | None = None, *, refresh: bool = False) -> PricingTable:
    """Fiyat tablosunu okur (süreç ömrü boyunca önbelleklenir).

    Dosya okunamazsa **boş tablo** döner: her kayıt ``unknown_model`` olur ve
    bu görünür bir arızadır. Sessizce 0 TL saymak yerine "fiyatlandırılamadı"
    demek, tavanın neden uygulanmadığını sorulabilir kılar.
    """
    settings = settings or get_settings()
    path = _resolve_path(settings)
    key = f"{path}|{settings.llm_usd_try_rate}"
    if not refresh and key in _cache:
        return _cache[key]

    models: dict[str, ModelPrice] = {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        for name, entry in raw.get("models", {}).items():
            models[name] = ModelPrice(
                input_per_mtok_usd=float(entry["input_per_mtok"]),
                output_per_mtok_usd=float(entry["output_per_mtok"]),
                verified=bool(entry.get("verified", False)),
            )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("llm_fiyat_tablosu_okunamadi", path=str(path), error=str(exc))

    table = PricingTable(models=models, usd_try_rate=settings.llm_usd_try_rate, source=str(path))
    _cache[key] = table
    return table


def reset_pricing_cache() -> None:
    """Önbelleği boşaltır (testler ve yapılandırma değişiklikleri için)."""
    _cache.clear()
