"""FastAPI uygulama fabrikası ve ASGI giriş noktası."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from tenderiq_api import __version__
from tenderiq_api.errors import register_exception_handlers
from tenderiq_api.middleware import RequestContextMiddleware
from tenderiq_api.queueing import enqueue_process_document
from tenderiq_api.routers.health import router as health_router
from tenderiq_api.routers.v1 import api_v1_router
from tenderiq_core.config import Environment, get_settings
from tenderiq_core.db import create_engine, create_session_factory
from tenderiq_core.logging import configure_logging
from tenderiq_core.storage import StorageNotConfiguredError, StorageService

# Windows'ta psycopg'nin async modu ProactorEventLoop ile çalışmaz; selector
# event-loop politikası gerekir (Linux/Docker'da bu dal çalışmaz).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Uygulama yaşam döngüsü: DB engine, session fabrikası ve depolama servisi."""
    settings = get_settings()
    engine = create_engine()
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = Redis.from_url(settings.redis_url)
    app.state.enqueue_document_job = enqueue_process_document
    try:
        app.state.storage = StorageService.from_settings(settings)
    except StorageNotConfiguredError:
        app.state.storage = None
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    """Yapılandırılmış bir FastAPI uygulaması üretir."""
    settings = get_settings()
    configure_logging(json_logs=settings.environment is not Environment.DEVELOPMENT)

    app = FastAPI(
        title="TenderIQ API",
        version=__version__,
        description="TenderIQ — AI destekli ihale/RFP analiz platformu API'si.",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
