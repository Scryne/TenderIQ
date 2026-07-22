"""/api/v1/usage — kiracının plan/kota kullanımı (Sprint 3.3-A)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from tenderiq_api.dependencies import PrincipalDep, TenantSessionDep
from tenderiq_core.billing.plans import PlanTier
from tenderiq_core.models import SubscriptionStatus
from tenderiq_core.services import quota

router = APIRouter(prefix="/usage", tags=["usage"])


class QuotaUsage(BaseModel):
    """Tek bir kota boyutu: kullanılan / limit (``limit=None`` ⇒ sınırsız)."""

    used: int
    limit: int | None


class UsageResponse(BaseModel):
    """Kiracının içinde bulunulan dönemdeki kullanımı ve plan limitleri."""

    plan: PlanTier
    plan_name: str
    status: SubscriptionStatus
    period_start: datetime
    period_end: datetime
    documents: QuotaUsage
    pages: QuotaUsage


@router.get("", response_model=UsageResponse)
async def get_usage(session: TenantSessionDep, principal: PrincipalDep) -> UsageResponse:
    """Aktif kiracının kullanımını döndürür.

    Abonelik yoksa ilk erişimde varsayılan FREE plan oluşturulur.
    """
    snapshot = await quota.compute_usage(session, principal.tenant_id)
    return UsageResponse(
        plan=snapshot.plan.tier,
        plan_name=snapshot.plan.display_name,
        status=snapshot.status,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        documents=QuotaUsage(used=snapshot.documents_used, limit=snapshot.plan.documents_per_month),
        pages=QuotaUsage(used=snapshot.pages_used, limit=snapshot.plan.pages_per_month),
    )
