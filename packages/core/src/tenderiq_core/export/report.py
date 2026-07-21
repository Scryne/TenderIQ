"""Export rapor sözleşmesi (Sprint 3.2, §4.1) — veri modeli + TR etiketleri.

API katmanı DB satırlarını bu nötr modele indirger; docx/xlsx builder'ları
yalnız bu modeli tüketir (DB'siz, saf → birim-testli). Kaynak referansları
(doküman + sayfa + bölüm + doğrulanmış alıntı) her satırda taşınır — export'ta
kaynak izlenebilirliği citation-first ilkesinin devamıdır (ADR-0006).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from tenderiq_core.findings import ReviewStatus

# Backend export etiketleri (TR) — web'deki lib/findings.ts ile hizalı tutulur.
REVIEW_STATUS_LABELS: dict[ReviewStatus, str] = {
    ReviewStatus.PENDING: "Onay bekliyor",
    ReviewStatus.APPROVED: "Onaylandı",
    ReviewStatus.EDITED: "Düzeltildi",
    ReviewStatus.REJECTED: "Reddedildi",
}

REQUIREMENT_KIND_LABELS: dict[str, str] = {
    "technical": "Teknik",
    "administrative": "İdari",
    "financial": "Mali",
}

DELIVERABLE_KIND_LABELS: dict[str, str] = {
    "document": "Belge",
    "certificate": "Sertifika",
    "guarantee": "Teminat",
    "other": "Diğer",
}

RISK_SEVERITY_LABELS: dict[str, str] = {
    "high": "Yüksek",
    "medium": "Orta",
    "low": "Düşük",
}

RISK_CATEGORY_LABELS: dict[str, str] = {
    "penalty": "Cezai şart",
    "termination": "Fesih",
    "warranty": "Garanti",
    "payment": "Ödeme",
    "other": "Diğer",
}

TIMELINE_KIND_LABELS: dict[str, str] = {
    "tender_date": "İhale tarihi",
    "bid_deadline": "Son teklif",
    "delivery": "Teslim/süre",
    "warranty": "Garanti süresi",
    "other": "Diğer",
}

COMPLIANCE_STATUS_LABELS: dict[str, str] = {
    "met": "Karşılanıyor",
    "partial": "Kısmen",
    "unmet": "Karşılanmıyor",
}

# Kaynakça alıntısı tavanı: satır kaynağı okunur kalsın, rapor şişmesin.
QUOTE_MAX_CHARS = 300


@dataclass(frozen=True)
class SourceRef:
    """Bulgunun kaynak referansı (doküman + sayfa no + bölüm + alıntı)."""

    document: str
    page: int
    section: str | None
    quote: str

    def location(self) -> str:
        """Kısa konum metni: ``sartname.pdf, s. 12 · Madde 7.2``."""
        base = f"{self.document}, s. {self.page}"
        section = (self.section or "").strip()
        return f"{base} · {section}" if section else base


@dataclass(frozen=True)
class ReportItem:
    """Rapor tablosunda tek satır: kategoriye özgü hücreler + inceleme + kaynak."""

    cells: tuple[str, ...]
    review_status: ReviewStatus
    source: SourceRef


@dataclass(frozen=True)
class ReportSection:
    """Tek kategori bölümü (ör. Gereksinimler) — başlıklar hücrelerle hizalı."""

    title: str
    headers: tuple[str, ...]
    items: tuple[ReportItem, ...]


@dataclass(frozen=True)
class TenderReport:
    """Export'a giren rapor: kimlik bilgileri + bölümler."""

    organization: str
    tender_title: str
    generated_at: datetime
    sections: tuple[ReportSection, ...]

    def is_empty(self) -> bool:
        return all(len(section.items) == 0 for section in self.sections)


def truncate_quote(quote: str, *, max_chars: int = QUOTE_MAX_CHARS) -> str:
    """Alıntıyı kaynakça için kısaltır (kelime ortasından kesmeden, '…' ile)."""
    quote = " ".join(quote.split())
    if len(quote) <= max_chars:
        return quote
    cut = quote[:max_chars].rsplit(" ", 1)[0]
    return f"{cut}…"
