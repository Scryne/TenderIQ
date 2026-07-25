"""/api/v1/panel — genel bakış ekranının tek çağrılık özeti.

Panel önceden beş ayrı uçtan besleniyordu: ihale listesi + kullanım + incelemeye
hazır her ihale için ayrı takvim/risk/uygunluk çağrısı. Bu, ihale sayısıyla
büyüyen bir N+1'di ve istemci ilk beş ihaleyle sınırlayarak sorunu maskeliyordu —
yani panel "en yakın teklif tarihi"ni değil, "ilk beş ihalenin en yakın teklif
tarihi"ni gösteriyordu. Bu uç veriyi kiracının TAMAMI üzerinden hesaplar.

Sözleşme notları:
- **Grounding (ADR-0006) korunur:** bulgular kaynak öğeye join'lenir; kaynağa
  bağlanamayan satır panelde de görünmez.
- **Reddedilen bulgular hariçtir:** kullanıcı elemişse panelde yer almaz.
- Yalnız ``review_ready`` ihalelerin bulguları sayılır; analizi süren ihalenin
  yarım çıkarımı "yaklaşan son tarih" diye sunulmamalıdır.
- Tarih sıralaması sunucuda yapılır (``parse_tr_date``); ayrıştırılamayan değerler
  listenin sonuna düşer ve ham metinleriyle gösterilir.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from tenderiq_api.dependencies import PrincipalDep, TenantSessionDep
from tenderiq_api.routers.v1.usage import QuotaUsage
from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.dates import parse_tr_date
from tenderiq_core.findings import ComplianceStatus, ReviewStatus, RiskSeverity
from tenderiq_core.models import (
    ComplianceResult,
    ParsedElement,
    RiskFlag,
    Tender,
    TenderStatus,
    TimelineEvent,
)
from tenderiq_core.services import quota

router = APIRouter(prefix="/panel", tags=["panel"])

# Panel bir çalışma listesi değil, bir ÖZET. Üst sınır hem yanıtı sınırlar hem de
# "ekranda gösterilmeyecek 2.000 satırı taşıma" durumunu engeller.
_MAX_ITEMS = 100


class PanelTenderCounts(BaseModel):
    """İhalelerin duruma göre dağılımı."""

    total: int
    draft: int
    analyzing: int
    review_ready: int
    archived: int


class PanelTenderRef(BaseModel):
    """Panelden ihaleye geçiş için asgari referans."""

    id: uuid.UUID
    title: str


class PanelDeadline(BaseModel):
    """Yaklaşan tarih/süre öğesi — kaynağıyla birlikte."""

    id: uuid.UUID
    tender_id: uuid.UUID
    tender_title: str
    label: str
    value_text: str  # ham metin (kaynağa sadık gösterim)
    due_date: date | None  # ayrıştırılabildiyse; sıralama buna göre
    page: int
    section: str | None


class PanelExposure(BaseModel):
    """Eleme riski taşıyan madde: yüksek risk veya karşılanmayan gereksinim."""

    id: uuid.UUID
    tender_id: uuid.UUID
    tender_title: str
    text: str
    source: Literal["risk", "compliance"]
    page: int
    section: str | None


class PanelResponse(BaseModel):
    """Genel bakış ekranının tüm verisi."""

    tenders: PanelTenderCounts
    plan: PlanTier
    plan_name: str
    period_end: datetime
    documents: QuotaUsage
    pages: QuotaUsage
    deadlines: list[PanelDeadline]
    exposures: list[PanelExposure]
    in_progress: list[PanelTenderRef]


@router.get("", response_model=PanelResponse)
async def get_panel(
    session: TenantSessionDep,
    principal: PrincipalDep,
    limit: int = Query(default=20, ge=1, le=_MAX_ITEMS),
) -> PanelResponse:
    """Aktif kiracının panel özetini tek çağrıda döndürür.

    ``limit`` son tarih ve maruziyet listelerinin her birine ayrı ayrı uygulanır.
    """
    counts_result = await session.execute(
        select(Tender.status, func.count()).group_by(Tender.status)
    )
    by_status: dict[TenderStatus, int] = dict(counts_result.all())  # type: ignore[arg-type]
    counts = PanelTenderCounts(
        total=sum(by_status.values()),
        draft=by_status.get(TenderStatus.DRAFT, 0),
        analyzing=by_status.get(TenderStatus.ANALYZING, 0),
        review_ready=by_status.get(TenderStatus.REVIEW_READY, 0),
        archived=by_status.get(TenderStatus.ARCHIVED, 0),
    )

    snapshot = await quota.compute_usage(session, principal.tenant_id)

    in_progress_result = await session.execute(
        select(Tender.id, Tender.title)
        .where(Tender.status == TenderStatus.ANALYZING)
        .order_by(Tender.created_at.desc())
        .limit(limit)
    )
    in_progress = [
        PanelTenderRef(id=row_id, title=title) for row_id, title in in_progress_result.all()
    ]

    # --- Son tarihler -------------------------------------------------------
    # Sıralama ham metnin ayrıştırılmasına bağlı olduğundan LIMIT'i SQL'de
    # uygulayamayız (SQL sıralaması metin sırası olurdu). Kiracının incelemeye
    # hazır takvim öğeleri _MAX_ITEMS ile sınırlanıp Python'da sıralanır.
    deadline_rows = await session.execute(
        select(TimelineEvent, ParsedElement, Tender.title)
        .join(ParsedElement, TimelineEvent.source_element_id == ParsedElement.id)
        .join(Tender, TimelineEvent.tender_id == Tender.id)
        .where(
            Tender.status == TenderStatus.REVIEW_READY,
            TimelineEvent.review_status != ReviewStatus.REJECTED,
        )
        .order_by(TimelineEvent.tender_id, TimelineEvent.seq)
        .limit(_MAX_ITEMS)
    )
    deadlines = [
        PanelDeadline(
            id=event.id,
            tender_id=event.tender_id,
            tender_title=title,
            label=event.label,
            value_text=event.value_text,
            due_date=parse_tr_date(event.value_text),
            page=element.page,
            section=element.section,
        )
        for event, element, title in deadline_rows.all()
    ]
    # Ayrıştırılabilenler yakından uzağa; ayrıştırılamayanlar sonda (date.max).
    deadlines.sort(key=lambda item: item.due_date or date.max)
    deadlines = deadlines[:limit]

    # --- Maruziyet ----------------------------------------------------------
    risk_rows = await session.execute(
        select(RiskFlag, ParsedElement, Tender.title)
        .join(ParsedElement, RiskFlag.source_element_id == ParsedElement.id)
        .join(Tender, RiskFlag.tender_id == Tender.id)
        .where(
            Tender.status == TenderStatus.REVIEW_READY,
            RiskFlag.severity == RiskSeverity.HIGH,
            RiskFlag.review_status != ReviewStatus.REJECTED,
        )
        .order_by(RiskFlag.tender_id, RiskFlag.seq)
        .limit(_MAX_ITEMS)
    )
    compliance_rows = await session.execute(
        select(ComplianceResult, ParsedElement, Tender.title)
        .join(ParsedElement, ComplianceResult.source_element_id == ParsedElement.id)
        .join(Tender, ComplianceResult.tender_id == Tender.id)
        .where(
            Tender.status == TenderStatus.REVIEW_READY,
            ComplianceResult.status == ComplianceStatus.UNMET,
            ComplianceResult.review_status != ReviewStatus.REJECTED,
        )
        .order_by(ComplianceResult.tender_id, ComplianceResult.seq)
        .limit(_MAX_ITEMS)
    )

    # Karşılanmayan gereksinim sözleşme riskinden ÖNCE gelir: eleme sebebi odur.
    exposures = [
        PanelExposure(
            id=row.id,
            tender_id=row.tender_id,
            tender_title=title,
            text=row.requirement_text,
            source="compliance",
            page=element.page,
            section=element.section,
        )
        for row, element, title in compliance_rows.all()
    ]
    exposures += [
        PanelExposure(
            id=row.id,
            tender_id=row.tender_id,
            tender_title=title,
            text=row.text,
            source="risk",
            page=element.page,
            section=element.section,
        )
        for row, element, title in risk_rows.all()
    ]
    exposures = exposures[:limit]

    return PanelResponse(
        tenders=counts,
        plan=snapshot.plan.tier,
        plan_name=snapshot.plan.display_name,
        period_end=snapshot.period_end,
        documents=QuotaUsage(used=snapshot.documents_used, limit=snapshot.plan.documents_per_month),
        pages=QuotaUsage(used=snapshot.pages_used, limit=snapshot.plan.pages_per_month),
        deadlines=deadlines,
        exposures=exposures,
        in_progress=in_progress,
    )
