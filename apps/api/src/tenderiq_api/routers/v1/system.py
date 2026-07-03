"""/api/v1/system — servis meta bilgisi."""

from __future__ import annotations

from fastapi import APIRouter

from tenderiq_api import __version__
from tenderiq_api.schemas import VersionResponse
from tenderiq_core.config import get_settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """Servis adı, sürümü ve çalışma ortamını döndürür."""
    settings = get_settings()
    return VersionResponse(
        name=settings.project_name,
        version=__version__,
        environment=settings.environment,
    )
