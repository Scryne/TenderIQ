"""/api/v1/jobs — asenkron işleme işi durum sorgulama + yeniden kuyruklama (§9.1)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from tenderiq_api.dependencies import (
    EnqueueDep,
    PrincipalDep,
    SessionDep,
    TenantSessionDep,
    require_role,
)
from tenderiq_api.errors import ConflictError, NotFoundError
from tenderiq_core.db.tenant import set_tenant_context
from tenderiq_core.models import AuditAction, Job, JobStatus, Role
from tenderiq_core.services.audit import record_audit

router = APIRouter(prefix="/jobs", tags=["jobs"])

_writer = Depends(require_role(Role.ADMIN, Role.MEMBER))


class JobResponse(BaseModel):
    """İşleme işinin durumu."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    status: JobStatus
    attempts: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, session: TenantSessionDep) -> JobResponse:
    """Tek bir işin durumunu döndürür (RLS: başka kiracınınki 404)."""
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("İş bulunamadı.")
    return JobResponse.model_validate(job)


@router.post("/{job_id}/retry", response_model=JobResponse, dependencies=[_writer])
async def retry_job(
    job_id: uuid.UUID,
    session: SessionDep,
    principal: PrincipalDep,
    enqueue: EnqueueDep,
) -> JobResponse:
    """``failed`` bir işi yeniden kuyruklar (``failed → queued``, §5.5).

    Kuyruklama commit SONRASI yapılır (worker'ın görünmeyen satırı okuma yarışı
    yok); ``attempts`` sıfırlanmaz — toplam deneme geçmişi korunur.
    """
    async with session.begin():
        await set_tenant_context(session, principal.tenant_id)
        # with_for_update: eşzamanlı iki retry çağrısının çifte yayın yapmasını önler.
        job = await session.get(Job, job_id, with_for_update=True)
        if job is None:
            raise NotFoundError("İş bulunamadı.")
        if job.status is not JobStatus.FAILED:
            raise ConflictError("Yalnızca failed durumdaki işler yeniden kuyruklanabilir.")
        job.transition_to(JobStatus.QUEUED)
        job.error_message = None
        job.finished_at = None
        record_audit(
            session,
            tenant_id=principal.tenant_id,
            action=AuditAction.JOB_RETRIED,
            resource_type="job",
            resource_id=job.id,
            actor_user_id=principal.user_id,
        )
        await session.flush()
        response = JobResponse.model_validate(job)

    enqueue(job.id, principal.tenant_id)
    return response
