"""/api/v1 router toplayıcısı."""

from __future__ import annotations

from fastapi import APIRouter

from tenderiq_api.routers.v1 import (
    auth,
    capability_profile,
    documents,
    export,
    findings,
    jobs,
    members,
    system,
    tenders,
    usage,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(tenders.router)
api_v1_router.include_router(findings.router)
api_v1_router.include_router(export.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(capability_profile.router)
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(members.router)
api_v1_router.include_router(system.router)
api_v1_router.include_router(usage.router)

__all__ = ["api_v1_router"]
