"""/api/v1 bulgu inceleme uçları (Sprint 3.2, §4.3) — insan-döngüde onay/düzeltme.

Sözleşme:
- ``PATCH /{koleksiyon}/{finding_id}``: ya ``action`` (approve/reject/reset) ya
  içerik alanları verilir (ikisi birden 400). İçerik düzeltmesi durumu EDITED
  yapar; her yazma AuditLog'a düşer (``resource_type`` = FindingKind değeri,
  ``resource_id`` = bulgu id'si — bulgu başına düzenleme geçmişinin kaynağı).
- ``POST /tenders/{tender_id}/findings/bulk-review``: toplu onay/red. Toplu
  onayda EDITED satırlar atlanır (düzeltilmiş hâl zaten onaylı sayılır; toplu
  işlem "düzeltildi" izini ezmemeli) — toplu red ise açık kullanıcı iradesidir,
  uygulanır.
- ``/findings/{kind}/{finding_id}/history|comments``: beş koleksiyona tek uçtan
  adreslenen düzenleme geçmişi ve ekip yorumları (temel işbirliği).

Grounding sözleşmesi liste uçlarıyla aynıdır: kaynak öğeye bağlanamayan bulgu
API'den dönmediği için burada da adreslenemez (join → 404).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from tenderiq_api.dependencies import PrincipalDep, TenantSessionDep, require_role
from tenderiq_api.errors import NotFoundError, ValidationFailedError
from tenderiq_api.routers.v1.tenders import (
    ComplianceResultResponse,
    DeliverableResponse,
    RequirementResponse,
    RiskResponse,
    TimelineEventResponse,
    compliance_result_response,
    deliverable_response,
    requirement_response,
    risk_response,
    timeline_event_response,
)
from tenderiq_core.findings import (
    ComplianceStatus,
    DeliverableKind,
    FindingKind,
    RequirementKind,
    ReviewStatus,
    RiskCategory,
    RiskSeverity,
    TimelineKind,
)
from tenderiq_core.models import (
    AuditAction,
    AuditLog,
    ComplianceResult,
    Deliverable,
    FindingComment,
    ParsedElement,
    Requirement,
    RiskFlag,
    Role,
    Tender,
    TimelineEvent,
)
from tenderiq_core.services.audit import record_audit

router = APIRouter(tags=["findings"])

_writer = Depends(require_role(Role.ADMIN, Role.MEMBER))


class ReviewAction(StrEnum):
    """Tek bulgu üzerinde inceleme eylemi."""

    APPROVE = "approve"  # onayla → APPROVED
    REJECT = "reject"  # reddet → REJECTED
    RESET = "reset"  # incelemeyi geri al → PENDING (kim/ne zaman temizlenir)


_ACTION_TARGET: dict[ReviewAction, ReviewStatus] = {
    ReviewAction.APPROVE: ReviewStatus.APPROVED,
    ReviewAction.REJECT: ReviewStatus.REJECTED,
    ReviewAction.RESET: ReviewStatus.PENDING,
}

_ACTION_AUDIT: dict[ReviewAction, AuditAction] = {
    ReviewAction.APPROVE: AuditAction.FINDING_APPROVED,
    ReviewAction.REJECT: AuditAction.FINDING_REJECTED,
    ReviewAction.RESET: AuditAction.FINDING_REVIEW_RESET,
}


class _ReviewPatchBase(BaseModel):
    """PATCH gövdesi tabanı: eylem VEYA (alt sınıftaki) içerik alanları."""

    model_config = ConfigDict(extra="forbid")

    action: ReviewAction | None = None


class RequirementPatch(_ReviewPatchBase):
    """Gereksinim düzeltme alanları."""

    text: str | None = Field(default=None, min_length=1)
    kind: RequirementKind | None = None
    is_mandatory: bool | None = None


class DeliverablePatch(_ReviewPatchBase):
    """İstenen belge düzeltme alanları."""

    name: str | None = Field(default=None, min_length=1)
    kind: DeliverableKind | None = None
    is_mandatory: bool | None = None


class RiskPatch(_ReviewPatchBase):
    """Risk maddesi düzeltme alanları."""

    text: str | None = Field(default=None, min_length=1)
    severity: RiskSeverity | None = None
    category: RiskCategory | None = None


class TimelineEventPatch(_ReviewPatchBase):
    """Takvim öğesi düzeltme alanları."""

    label: str | None = Field(default=None, min_length=1)
    kind: TimelineKind | None = None
    value_text: str | None = Field(default=None, min_length=1)


class ComplianceResultPatch(_ReviewPatchBase):
    """Uygunluk değerlendirmesi düzeltme alanları (durum + gerekçe)."""

    status: ComplianceStatus | None = None
    rationale: str | None = Field(default=None, min_length=1)


@dataclass(frozen=True)
class _FindingSpec:
    """Bulgu koleksiyonunun inceleme uçlarındaki sözleşmesi."""

    model: type[Any]  # ORM modeli
    build_response: Callable[[Any, ParsedElement], BaseModel]  # satır+öğe → yanıt


_SPECS: dict[FindingKind, _FindingSpec] = {
    FindingKind.REQUIREMENT: _FindingSpec(Requirement, requirement_response),
    FindingKind.DELIVERABLE: _FindingSpec(Deliverable, deliverable_response),
    FindingKind.RISK: _FindingSpec(RiskFlag, risk_response),
    FindingKind.TIMELINE: _FindingSpec(TimelineEvent, timeline_event_response),
    FindingKind.COMPLIANCE: _FindingSpec(ComplianceResult, compliance_result_response),
}


def _meta_value(value: object) -> object:
    """AuditLog meta'sı için JSON-uyumlu değer (enum → değeri)."""
    return value.value if isinstance(value, StrEnum) else value


async def _load_finding_with_element(
    session: Any, kind: FindingKind, finding_id: uuid.UUID
) -> tuple[Any, ParsedElement]:
    """Bulguyu kaynak öğesiyle yükler; RLS-dışı/kaynaksız bulgu 404."""
    spec = _SPECS[kind]
    row_element = (
        await session.execute(
            select(spec.model, ParsedElement)
            .join(ParsedElement, spec.model.source_element_id == ParsedElement.id)
            .where(spec.model.id == finding_id)
        )
    ).first()
    if row_element is None:
        raise NotFoundError("Bulgu bulunamadı.")
    finding, element = row_element
    return finding, element


async def _patch_finding(
    session: Any,
    principal: Any,
    kind: FindingKind,
    finding_id: uuid.UUID,
    body: _ReviewPatchBase,
) -> tuple[Any, ParsedElement]:
    """Onay/red/geri alma veya içerik düzeltmesini uygular; AuditLog yazar.

    Aynı duruma tekrarlanan eylem idempotenttir (yazma/audit üretmez). İçerik
    düzeltmesinde yalnız gerçekten değişen alanlar geçmişe yazılır; hiçbir alan
    değişmiyorsa 400 döner.
    """
    finding, element = await _load_finding_with_element(session, kind, finding_id)

    edits = {
        name: value
        for name, value in body.model_dump(exclude_unset=True).items()
        if name != "action" and value is not None
    }
    if body.action is not None and edits:
        raise ValidationFailedError("action ile içerik alanları aynı istekte verilemez.")
    if body.action is None and not edits:
        raise ValidationFailedError("Değişiklik yok: action veya en az bir içerik alanı verin.")

    old_status: ReviewStatus = finding.review_status
    now = datetime.now(UTC)

    if body.action is not None:
        target = _ACTION_TARGET[body.action]
        if target is old_status:
            return finding, element  # idempotent: durum zaten hedefte
        finding.review_status = target
        if body.action is ReviewAction.RESET:
            finding.reviewed_by = None
            finding.reviewed_at = None
        else:
            finding.reviewed_by = principal.user_id
            finding.reviewed_at = now
        record_audit(
            session,
            tenant_id=principal.tenant_id,
            action=_ACTION_AUDIT[body.action],
            resource_type=kind.value,
            resource_id=finding.id,
            actor_user_id=principal.user_id,
            meta={"from": old_status.value, "to": target.value},
        )
    else:
        changes: dict[str, dict[str, object]] = {}
        for field, new_value in edits.items():
            old_value = getattr(finding, field)
            if old_value != new_value:
                changes[field] = {"from": _meta_value(old_value), "to": _meta_value(new_value)}
                setattr(finding, field, new_value)
        if not changes:
            raise ValidationFailedError("Değişiklik yok: verilen değerler mevcut değerlerle aynı.")
        finding.review_status = ReviewStatus.EDITED
        finding.reviewed_by = principal.user_id
        finding.reviewed_at = now
        record_audit(
            session,
            tenant_id=principal.tenant_id,
            action=AuditAction.FINDING_EDITED,
            resource_type=kind.value,
            resource_id=finding.id,
            actor_user_id=principal.user_id,
            meta={"from": old_status.value, "to": ReviewStatus.EDITED.value, "changes": changes},
        )

    await session.flush()
    return finding, element


@router.patch(
    "/requirements/{finding_id}", response_model=RequirementResponse, dependencies=[_writer]
)
async def patch_requirement(
    finding_id: uuid.UUID,
    body: RequirementPatch,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> RequirementResponse:
    """Gereksinimi onaylar/reddeder/geri alır veya içeriğini düzeltir (AuditLog'lu)."""
    row, element = await _patch_finding(
        session, principal, FindingKind.REQUIREMENT, finding_id, body
    )
    return requirement_response(row, element)


@router.patch(
    "/deliverables/{finding_id}", response_model=DeliverableResponse, dependencies=[_writer]
)
async def patch_deliverable(
    finding_id: uuid.UUID,
    body: DeliverablePatch,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> DeliverableResponse:
    """İstenen belgeyi onaylar/reddeder/geri alır veya içeriğini düzeltir (AuditLog'lu)."""
    row, element = await _patch_finding(
        session, principal, FindingKind.DELIVERABLE, finding_id, body
    )
    return deliverable_response(row, element)


@router.patch("/risks/{finding_id}", response_model=RiskResponse, dependencies=[_writer])
async def patch_risk(
    finding_id: uuid.UUID,
    body: RiskPatch,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> RiskResponse:
    """Risk maddesini onaylar/reddeder/geri alır veya içeriğini düzeltir (AuditLog'lu)."""
    row, element = await _patch_finding(session, principal, FindingKind.RISK, finding_id, body)
    return risk_response(row, element)


@router.patch(
    "/timeline-events/{finding_id}", response_model=TimelineEventResponse, dependencies=[_writer]
)
async def patch_timeline_event(
    finding_id: uuid.UUID,
    body: TimelineEventPatch,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> TimelineEventResponse:
    """Takvim öğesini onaylar/reddeder/geri alır veya içeriğini düzeltir (AuditLog'lu)."""
    row, element = await _patch_finding(session, principal, FindingKind.TIMELINE, finding_id, body)
    return timeline_event_response(row, element)


@router.patch(
    "/compliance-results/{finding_id}",
    response_model=ComplianceResultResponse,
    dependencies=[_writer],
)
async def patch_compliance_result(
    finding_id: uuid.UUID,
    body: ComplianceResultPatch,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> ComplianceResultResponse:
    """Uygunluk değerlendirmesini onaylar/reddeder/geri alır veya düzeltir (AuditLog'lu)."""
    row, element = await _patch_finding(
        session, principal, FindingKind.COMPLIANCE, finding_id, body
    )
    return compliance_result_response(row, element)


# ── Toplu onay/red ───────────────────────────────────────────────────────────


class BulkReviewAction(StrEnum):
    """Toplu inceleme eylemi (yalnız onay/red — geri alma tekildir)."""

    APPROVE = "approve"
    REJECT = "reject"


class BulkReviewItem(BaseModel):
    """Toplu istekte tek bulgu adresi."""

    kind: FindingKind
    id: uuid.UUID


class BulkReviewRequest(BaseModel):
    """Toplu onay/red isteği."""

    action: BulkReviewAction
    items: list[BulkReviewItem] = Field(min_length=1, max_length=500)


class BulkReviewResponse(BaseModel):
    """Toplu işlem sonucu: değişen / zaten hedefte / bulunamayan."""

    updated: int
    unchanged: int
    skipped: list[uuid.UUID]


@router.post(
    "/tenders/{tender_id}/findings/bulk-review",
    response_model=BulkReviewResponse,
    dependencies=[_writer],
)
async def bulk_review(
    tender_id: uuid.UUID,
    body: BulkReviewRequest,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> BulkReviewResponse:
    """Seçili bulguları tek transaction'da toplu onaylar/reddeder (AuditLog'lu).

    Başka ihaleye/kiracıya ait ya da var olmayan id'ler ``skipped``a düşer.
    Toplu onayda EDITED satırlar ``unchanged`` sayılır (düzeltilmiş hâl onaylı
    sayılır; toplu işlem "düzeltildi" izini ezmez).
    """
    if await session.get(Tender, tender_id) is None:
        raise NotFoundError("İhale bulunamadı.")

    target = (
        ReviewStatus.APPROVED if body.action is BulkReviewAction.APPROVE else ReviewStatus.REJECTED
    )
    audit_action = (
        AuditAction.FINDING_APPROVED
        if body.action is BulkReviewAction.APPROVE
        else AuditAction.FINDING_REJECTED
    )

    ids_by_kind: dict[FindingKind, set[uuid.UUID]] = {}
    for item in body.items:
        ids_by_kind.setdefault(item.kind, set()).add(item.id)

    now = datetime.now(UTC)
    updated = 0
    unchanged = 0
    found: set[uuid.UUID] = set()
    for kind, ids in ids_by_kind.items():
        spec = _SPECS[kind]
        rows = (
            (
                await session.execute(
                    select(spec.model).where(
                        spec.model.id.in_(ids), spec.model.tender_id == tender_id
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            found.add(row.id)
            keep_edited = target is ReviewStatus.APPROVED and (
                row.review_status is ReviewStatus.EDITED
            )
            if row.review_status is target or keep_edited:
                unchanged += 1
                continue
            old_status: ReviewStatus = row.review_status
            row.review_status = target
            row.reviewed_by = principal.user_id
            row.reviewed_at = now
            record_audit(
                session,
                tenant_id=principal.tenant_id,
                action=audit_action,
                resource_type=kind.value,
                resource_id=row.id,
                actor_user_id=principal.user_id,
                meta={"from": old_status.value, "to": target.value, "bulk": True},
            )
            updated += 1

    await session.flush()
    skipped = sorted({item.id for item in body.items} - found, key=str)
    return BulkReviewResponse(updated=updated, unchanged=unchanged, skipped=skipped)


# ── Düzenleme geçmişi + yorumlar ─────────────────────────────────────────────


class FindingHistoryEntry(BaseModel):
    """Bulgu üzerindeki tek denetim kaydı (düzenleme geçmişi satırı)."""

    id: uuid.UUID
    action: str
    actor_user_id: uuid.UUID | None
    created_at: datetime
    meta: dict[str, Any] | None


@router.get("/findings/{kind}/{finding_id}/history", response_model=list[FindingHistoryEntry])
async def list_finding_history(
    kind: FindingKind, finding_id: uuid.UUID, session: TenantSessionDep
) -> list[FindingHistoryEntry]:
    """Bulgunun düzenleme geçmişini (AuditLog) yeniden-eskiye listeler."""
    if await session.get(_SPECS[kind].model, finding_id) is None:
        raise NotFoundError("Bulgu bulunamadı.")
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.resource_type == kind.value, AuditLog.resource_id == finding_id)
        .order_by(AuditLog.created_at.desc())
    )
    return [
        FindingHistoryEntry(
            id=entry.id,
            action=entry.action,
            actor_user_id=entry.actor_user_id,
            created_at=entry.created_at,
            meta=entry.meta,
        )
        for entry in result.scalars().all()
    ]


class FindingCommentCreate(BaseModel):
    """Yeni bulgu yorumu."""

    body: str = Field(min_length=1, max_length=4000)


class FindingCommentResponse(BaseModel):
    """Tek bulgu yorumu."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    finding_kind: FindingKind
    finding_id: uuid.UUID
    author_user_id: uuid.UUID | None
    body: str
    created_at: datetime


@router.get("/findings/{kind}/{finding_id}/comments", response_model=list[FindingCommentResponse])
async def list_finding_comments(
    kind: FindingKind, finding_id: uuid.UUID, session: TenantSessionDep
) -> list[FindingCommentResponse]:
    """Bulgunun ekip yorumlarını eskiden-yeniye listeler."""
    if await session.get(_SPECS[kind].model, finding_id) is None:
        raise NotFoundError("Bulgu bulunamadı.")
    result = await session.execute(
        select(FindingComment)
        .where(FindingComment.finding_kind == kind, FindingComment.finding_id == finding_id)
        .order_by(FindingComment.created_at)
    )
    return [FindingCommentResponse.model_validate(c) for c in result.scalars().all()]


@router.post(
    "/findings/{kind}/{finding_id}/comments",
    response_model=FindingCommentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_writer],
)
async def create_finding_comment(
    kind: FindingKind,
    finding_id: uuid.UUID,
    body: FindingCommentCreate,
    session: TenantSessionDep,
    principal: PrincipalDep,
) -> FindingCommentResponse:
    """Bulguya ekip notu düşer (temel işbirliği; AuditLog'lu)."""
    finding = await session.get(_SPECS[kind].model, finding_id)
    if finding is None:
        raise NotFoundError("Bulgu bulunamadı.")
    comment = FindingComment(
        id=uuid.uuid4(),
        tenant_id=principal.tenant_id,
        tender_id=finding.tender_id,
        finding_kind=kind,
        finding_id=finding_id,
        author_user_id=principal.user_id,
        body=body.body,
    )
    session.add(comment)
    record_audit(
        session,
        tenant_id=principal.tenant_id,
        action=AuditAction.FINDING_COMMENTED,
        resource_type=kind.value,
        resource_id=finding_id,
        actor_user_id=principal.user_id,
        meta={"comment_id": str(comment.id)},
    )
    await session.flush()
    # created_at DB tarafında (server_default) üretilir; async oturumda örtük
    # lazy-load MissingGreenlet fırlatır — açıkça tazelenir.
    await session.refresh(comment)
    return FindingCommentResponse.model_validate(comment)
