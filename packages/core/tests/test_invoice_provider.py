"""Fatura seam'i — yükümlülük sessizce kapanmış sayılmamalı."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from tenderiq_core.billing.invoice import (
    InvoiceOutcome,
    InvoiceRequest,
    MemoryInvoiceProvider,
    NoopInvoiceProvider,
    create_invoice_provider,
)


def _request(reference: str = "pay-1") -> InvoiceRequest:
    return InvoiceRequest(
        tenant_id=uuid.uuid4(),
        payment_reference=reference,
        buyer_title="Örnek Mühendislik Ltd. Şti.",
        buyer_tax_id="1234567890",
        buyer_address="İstanbul",
        description="TenderIQ Pro — aylık abonelik",
        amount_try=Decimal("1500.00"),
        vat_rate=Decimal("0.20"),
    )


async def test_entegrator_yokken_kesilmedi_der() -> None:
    """Sessiz bir 'kesildi', denetimde 'kesildi sanıyorduk' cevabını üretirdi."""
    result = await NoopInvoiceProvider().issue(_request())

    assert result.outcome is InvoiceOutcome.NOT_CONFIGURED
    assert result.document_id is None
    assert "LEGAL_TODO" in (result.detail or "")


async def test_ayni_odeme_icin_mukerrer_fatura_kesilmez() -> None:
    provider = MemoryInvoiceProvider()

    first = await provider.issue(_request("pay-9"))
    second = await provider.issue(_request("pay-9"))

    assert first.outcome is InvoiceOutcome.ISSUED
    assert second.outcome is InvoiceOutcome.ISSUED
    assert len(provider.issued) == 1


def test_baglanmamis_entegrator_sessizce_yok_sayilmaz() -> None:
    with pytest.raises(NotImplementedError, match="LEGAL_TODO"):
        create_invoice_provider("parasut")


def test_varsayilan_noop() -> None:
    assert create_invoice_provider("none").name == "noop"


def test_tutar_decimal_tutulur() -> None:
    """Para hesabı float ile yapılmaz; kuruş kayması faturayı hatalı kılar."""
    assert isinstance(_request().amount_try, Decimal)
