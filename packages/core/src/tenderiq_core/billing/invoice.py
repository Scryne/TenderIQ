"""Fatura seam'i — e-Arşiv / e-Fatura entegratörü için ayrılmış yüzey.

**Neden ayrı bir seam:** iyzico fatura KESMEZ. Ödeme alındığında Türkiye'de
fatura düzenleme yükümlülüğü doğar (VUK) ve bu ayrı bir entegratör gerektirir
(Paraşüt, Birfatura, Logo İşbaşı…). Mükellefiyet türüne göre **e-Fatura**
(mükellefe) / **e-Arşiv** (mükellef olmayana) ayrımını da entegratör, GİB
mükellef sorgusuyla çözer — bu ayrımı biz yapmayız.

Varsayılan implementasyon **no-op**tur ve bilinçli olarak "kesilmedi" der:
sessizce başarı döndürmek, yükümlülüğün yerine getirildiği yanılsaması üretirdi.
Entegratör bağlanana kadar her tetiklenme loglanır ve `LEGAL_TODO.md` §E'de
takip edilir.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from tenderiq_core.logging import get_logger

logger = get_logger("tenderiq.core.invoice")


class InvoiceOutcome(StrEnum):
    """Fatura talebinin sonucu."""

    ISSUED = "issued"
    #: Entegratör bağlı değil — yükümlülük DURUYOR, kapanmadı.
    NOT_CONFIGURED = "not_configured"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class InvoiceRequest:
    """Bir tahsilat için fatura talebi.

    Alıcı bilgileri kiracıdan gelir; ``tax_id`` boşsa entegratör e-Arşiv yolunu
    seçer. Tutar **kuruş değil** TL cinsindendir (``Decimal``) — float ile para
    hesabı yapılmaz.
    """

    tenant_id: uuid.UUID
    #: Sağlayıcı ödeme/olay kimliği — mükerrer fatura kesilmesini engeller.
    payment_reference: str
    buyer_title: str
    buyer_tax_id: str | None
    buyer_address: str | None
    description: str
    amount_try: Decimal
    vat_rate: Decimal


@dataclass(frozen=True, slots=True)
class InvoiceResult:
    """Fatura sonucu; ``document_id`` entegratörün belge kimliğidir."""

    outcome: InvoiceOutcome
    document_id: str | None = None
    detail: str | None = None


class InvoiceProvider(Protocol):
    """Fatura entegratörü sözleşmesi."""

    name: str

    async def issue(self, request: InvoiceRequest) -> InvoiceResult:
        """Faturayı düzenler; entegratör yoksa ``NOT_CONFIGURED`` döner."""
        ...


class NoopInvoiceProvider:
    """Entegratör bağlanana kadarki varsayılan.

    Fatura **kesmez** ve bunu açıkça söyler. Tetiklenmeyi loglar ki yükümlülüğün
    kaç kez doğduğu görünür olsun; sessiz bir ``ISSUED`` döndürmek, denetimde
    "kesildi sanıyorduk" cevabını üretirdi.
    """

    name = "noop"

    async def issue(self, request: InvoiceRequest) -> InvoiceResult:
        logger.warning(
            "fatura_entegratoru_bagli_degil",
            tenant_id=str(request.tenant_id),
            payment_reference=request.payment_reference,
            amount_try=str(request.amount_try),
        )
        return InvoiceResult(
            outcome=InvoiceOutcome.NOT_CONFIGURED,
            detail="e-Arşiv/e-Fatura entegratörü yapılandırılmadı (bkz. LEGAL_TODO.md §E).",
        )


class MemoryInvoiceProvider:
    """Test sağlayıcısı — talepleri bellekte tutar."""

    name = "memory"

    def __init__(self) -> None:
        self.issued: list[InvoiceRequest] = []

    async def issue(self, request: InvoiceRequest) -> InvoiceResult:
        # Mükerrer tetiklenme entegratörde de engellenir; burada da aynı
        # sözleşme uygulanır ki testler gerçeği yansıtsın.
        if any(item.payment_reference == request.payment_reference for item in self.issued):
            return InvoiceResult(
                outcome=InvoiceOutcome.ISSUED,
                document_id=f"memory-{request.payment_reference}",
                detail="Zaten kesilmiş.",
            )
        self.issued.append(request)
        return InvoiceResult(
            outcome=InvoiceOutcome.ISSUED, document_id=f"memory-{request.payment_reference}"
        )


def create_invoice_provider(provider_name: str) -> InvoiceProvider:
    """Yapılandırılmış fatura sağlayıcısını üretir."""
    if provider_name in {"", "none", "noop"}:
        return NoopInvoiceProvider()
    if provider_name == "memory":
        return MemoryInvoiceProvider()
    # Entegratör adaptörleri (parasut/birfatura/logo) buraya bağlanacak.
    raise NotImplementedError(
        f"Fatura entegratörü '{provider_name}' henüz bağlanmadı (bkz. LEGAL_TODO.md §E)."
    )
