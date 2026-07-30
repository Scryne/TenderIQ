"""LlmUsage — kiracı × model × işlem bazında LLM çağrı/maliyet kaydı (J.6; RLS).

Kota sayımı `UsageRecord` (doküman/sayfa) üzerinden yapılıyordu; bu tablo
**para** boyutunu ekler. Ayrı tablo çünkü sayım birimi farklı: bir doküman
işlemesi onlarca LLM çağrısı üretir ve tavan token/tutar üzerinden konur.

`cost_micros_try` mikro-TL'dir (1 TL = 1_000_000). Tam sayı: float toplamı
büyük hacimde sapar ve tavan karşılaştırmasını güvenilmez yapar.

`pricing_status` **belirsizliği gizlememek için** vardır. 0 TL üç ayrı şey
anlamına gelebilir ve üçü ayrı ayrı işaretlenir: gerçekten ücretsiz (`priced`,
ör. yerel Ollama), fiyat doğrulanmamış (`unverified`), model tabloda yok
(`unknown_model`), kur tanımsız (`no_fx_rate`). Tavan yalnız güvenilir
tutarları toplarsa yanlış yerde gevşer; bu yüzden karar veren kod durumu
görmek zorunda.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from tenderiq_core.db.base import Base
from tenderiq_core.db.mixins import TenantMixin, UUIDPKMixin


class LlmUsage(UUIDPKMixin, TenantMixin, Base):
    """Tek bir LLM çağrısının token ve maliyet kaydı (kiracı-özel)."""

    __tablename__ = "llm_usage"

    #: Hangi işi besledi — silinirse kayıt DURUR (dönem toplamı bozulmasın).
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("job.id", ondelete="SET NULL"), index=True
    )
    model: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    #: Çağrıyı yapan işlem (şema/ajan adı, ör. "RequirementExtraction").
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    #: Mikro-TL (1 TL = 1_000_000). BigInteger: aylık toplam int32'yi aşabilir.
    cost_micros_try: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    #: priced | unverified | unknown_model | no_fx_rate (bkz. llm/pricing.py)
    pricing_status: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
