"""Fiyatlandırma duruşu: tavanın hangi zeminde durduğunu AÇILIŞTA görünür kılar.

## Neden ayrı bir kontrol

LLM bütçe tavanı üç sessiz yoldan işlevsizleşir ve üçü de "hata" üretmez:

1. **Kur yok.** ``LLM_USD_TRY_RATE`` boşsa her kayıt ``no_fx_rate`` olur, tutar
   0 TL yazılır, toplam harcama sıfır kalır ve tavan HİÇBİR ZAMAN dolmaz.
   Sistem sağlıklı görünür; tavan yoktur.
2. **Kur bayat.** Kur statiktir ve otomatik çekilmez (dış servis bağımlılığı
   bilinçli olarak eklenmedi). TL oynaklığında aylar önce yazılmış bir kur,
   gerçek maliyeti olduğundan düşük gösterir — tavan geç kapanır.
3. **Fiyat doğrulanmamış.** ``verified: false`` satırın tutarı bir TAHMİNDİR.
   Tahmin, doğrulanmış bir sayı gibi toplama girerse tavan uydurma bir zeminin
   üstünde durur.

Bu modül üçünü de **açılışta** rapor eder. Karar bilinçli olarak *uyarmak*,
*durdurmak* değil: bayat kur kursuzluktan, tahmini fiyat fiyatsızlıktan iyidir.
Durdurmak, ölçümü hiç olmayan bir sisteme geri dönmek olurdu.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from tenderiq_core.config import Settings, get_settings
from tenderiq_core.llm.pricing import PricingTable, load_pricing
from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.llm.pricing_posture")

__all__ = ["PricingPosture", "evaluate_pricing_posture", "log_pricing_posture"]


@dataclass(frozen=True, slots=True)
class PricingPosture:
    """Fiyat tablosu + kurun açılış anındaki durumu."""

    #: Kur hiç tanımlı değil → maliyet HESAPLANMAZ, tavan fiilen yok.
    fx_rate_missing: bool
    #: Kurun yaşı (gün); tarih yazılmamışsa ``None``.
    fx_rate_age_days: int | None
    #: Kur tarihi yazılmamış → bayatlık ÖLÇÜLEMEZ.
    fx_rate_date_missing: bool
    #: Yaş eşiği aştı.
    fx_rate_stale: bool
    #: `verified: false` kalan model adları (sıralı).
    unverified_models: tuple[str, ...]
    #: Tablodaki toplam model sayısı.
    total_models: int

    @property
    def degraded(self) -> bool:
        """Tavanın zemini kusurlu mu (uyarı üretilmeli mi)."""
        return bool(
            self.fx_rate_missing
            or self.fx_rate_stale
            or self.fx_rate_date_missing
            or self.unverified_models
        )

    @property
    def cap_effectively_disabled(self) -> bool:
        """Tavan FİİLEN yok mu — kur olmadan harcama hep 0 TL sayılır."""
        return self.fx_rate_missing


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        logger.warning("llm_kur_tarihi_okunamadi", value=raw)
        return None


def evaluate_pricing_posture(
    settings: Settings | None = None,
    table: PricingTable | None = None,
    *,
    today: date | None = None,
) -> PricingPosture:
    """Fiyat tablosu ve kur ayarlarını değerlendirir (yan etkisiz)."""
    settings = settings or get_settings()
    table = table if table is not None else load_pricing(settings)
    today = today or datetime.now(UTC).date()

    rate_date = _parse_date(settings.llm_usd_try_rate_date)
    age = (today - rate_date).days if rate_date is not None else None
    unverified = tuple(sorted(name for name, price in table.models.items() if not price.verified))

    return PricingPosture(
        fx_rate_missing=settings.llm_usd_try_rate is None,
        fx_rate_age_days=age,
        fx_rate_date_missing=settings.llm_usd_try_rate is not None and rate_date is None,
        fx_rate_stale=age is not None and age > settings.llm_usd_try_rate_max_age_days,
        unverified_models=unverified,
        total_models=len(table.models),
    )


def log_pricing_posture(posture: PricingPosture | None = None) -> PricingPosture:
    """Duruşu loglar ve ops sayaçlarına yazar; duruşu döndürür.

    Açılışta (API + worker) çağrılır. Sayaç yazımı fail-open: metrik yazamamak
    açılışı bozmamalı.
    """
    posture = posture if posture is not None else evaluate_pricing_posture()

    if posture.fx_rate_missing:
        logger.error(
            "llm_kuru_tanimsiz_tavan_fiilen_yok",
            hint=(
                "LLM_USD_TRY_RATE boş: her kayıt no_fx_rate ile 0 TL yazılır, "
                "harcama toplamı sıfır kalır ve bütçe tavanı hiç dolmaz"
            ),
        )
    elif posture.fx_rate_date_missing:
        logger.warning(
            "llm_kur_tarihi_yazilmamis",
            hint="LLM_USD_TRY_RATE_DATE boş: kurun bayatlığı ÖLÇÜLEMİYOR",
        )
    elif posture.fx_rate_stale:
        logger.warning(
            "llm_kuru_bayat",
            age_days=posture.fx_rate_age_days,
            threshold_days=get_settings().llm_usd_try_rate_max_age_days,
            hint="kuru elle güncelleyip LLM_USD_TRY_RATE_DATE'i bugüne çekin",
        )

    if posture.unverified_models:
        logger.warning(
            "llm_fiyatlari_dogrulanmamis",
            models=list(posture.unverified_models),
            total=posture.total_models,
            hint=(
                "bu modellerin tutarı TAHMİNDİR (pricing_status=unverified); "
                "config/llm-pricing.json içinde source + verified_at doldurun"
            ),
        )

    _record(posture)
    return posture


def _record(posture: PricingPosture) -> None:
    """Duruşu `ops` sayaçlarına yazar (fail-open)."""
    from tenderiq_core.ops import record_llm_pricing_posture

    try:
        record_llm_pricing_posture(
            unverified_models=len(posture.unverified_models),
            fx_rate_missing=posture.fx_rate_missing,
            fx_rate_stale=posture.fx_rate_stale or posture.fx_rate_date_missing,
        )
    except Exception as exc:  # metrik, açılışı ASLA bozmaz
        logger.debug("llm_fiyat_durusu_metrigi_yazilamadi", error=str(exc))
