"""Sağlık uçları: /healthz (liveness) ve /readyz (readiness)."""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from redis.asyncio import Redis
from sqlalchemy import text

from tenderiq_api.schemas import HealthResponse, ReadinessComponent, ReadinessResponse
from tenderiq_core.config import get_settings
from tenderiq_core.db.session import create_engine

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness — süreç ayakta mı (bağımlılık kontrol etmez)."""
    return HealthResponse(status="ok")


async def _check_database() -> ReadinessComponent:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return ReadinessComponent(name="database", healthy=True)
    except Exception as exc:
        return ReadinessComponent(name="database", healthy=False, detail=str(exc))
    finally:
        await engine.dispose()


async def _check_redis() -> ReadinessComponent:
    client: Redis = Redis.from_url(get_settings().redis_url)
    try:
        await client.ping()
        return ReadinessComponent(name="redis", healthy=True)
    except Exception as exc:
        return ReadinessComponent(name="redis", healthy=False, detail=str(exc))
    finally:
        await client.aclose()


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(response: Response) -> ReadinessResponse:
    """Readiness — DB ve Redis erişilebilir mi; değilse 503 döner."""
    components = [await _check_database(), await _check_redis()]
    ready = all(component.healthy for component in components)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(ready=ready, components=components)
