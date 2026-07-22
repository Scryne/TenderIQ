"""Kök test yapılandırması: platform shim + paylaşılan entegrasyon fixture'ları."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Windows'ta psycopg async, ProactorEventLoop ile çalışmaz; selector şart.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

PROJECT_ROOT = Path(__file__).resolve().parent

APP_ROLE = "tenderiq_app"
APP_PASSWORD = "tenderiq_app"
TEST_AUTH_SECRET = "test-secret-please-change-in-prod"


@pytest.fixture(scope="session")
def app_database_url() -> Iterator[str]:
    """Entegrasyon testleri: pgvector container + migration + non-superuser app rolü.

    Migration'lar ayrıcalıklı rolle uygulanır; uygulama RLS'ye tabi `tenderiq_app`
    rolüyle bağlanır (bkz. ADR-0003). Süper-kullanıcı RLS'yi baypas ederdi.
    """
    postgres_container = pytest.importorskip("testcontainers.postgres").PostgresContainer
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from tenderiq_core.config import get_settings

    with postgres_container(
        "pgvector/pgvector:pg16",
        username="tenderiq",
        password="tenderiq",
        dbname="tenderiq",
        driver="psycopg",
    ) as postgres:
        admin_url = postgres.get_connection_url()
        os.environ["DATABASE_ADMIN_URL"] = admin_url
        os.environ["DATABASE_URL"] = admin_url
        get_settings.cache_clear()

        cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
        command.upgrade(cfg, "head")

        admin_engine = create_engine(admin_url)
        with admin_engine.begin() as conn:
            conn.execute(text(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'"))
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
            conn.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    f"ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
                )
            )
        admin_engine.dispose()

        host = postgres.get_container_host_ip()
        port = postgres.get_exposed_port(5432)
        app_url = f"postgresql+psycopg://{APP_ROLE}:{APP_PASSWORD}@{host}:{port}/tenderiq"
        try:
            yield app_url
        finally:
            for key in ("DATABASE_URL", "DATABASE_ADMIN_URL"):
                os.environ.pop(key, None)
            get_settings.cache_clear()


@pytest.fixture
def api_client(app_database_url: str) -> Iterator[TestClient]:
    """Uygulamayı (RLS'ye tabi app rolüyle) bir TestClient olarak sunar."""
    from tenderiq_core.config import get_settings

    os.environ["DATABASE_URL"] = app_database_url
    os.environ["AUTH_SECRET"] = TEST_AUTH_SECRET
    os.environ["OBJECT_STORAGE_BUCKET"] = "tenderiq-test"
    os.environ["OBJECT_STORAGE_ENDPOINT_URL"] = "http://localhost:9000"
    os.environ["OBJECT_STORAGE_ACCESS_KEY_ID"] = "test-key"
    os.environ["OBJECT_STORAGE_SECRET_ACCESS_KEY"] = "test-secret"
    get_settings.cache_clear()

    # Oran sınırlama (rl:*) ve refresh token'lar (rt:* / rtfam:*) GERÇEK Redis'e
    # yazılır ve TTL'lidir: önceki test koşularından kalan anahtarlar kayıt/giriş
    # uçlarını 429'a düşürebilir veya token durumunu kirletebilir. Her api_client
    # kurulumunda yalnız bu ön-ekler temizlenir (başka veri silinmez).
    import redis as redis_sync

    try:
        redis_client = redis_sync.Redis.from_url(get_settings().redis_url)
        stale_keys = [
            key
            for pattern in ("rl:*", "rt:*", "rtfam:*")
            for key in redis_client.scan_iter(pattern)
        ]
        if stale_keys:
            redis_client.delete(*stale_keys)
        redis_client.close()
    except redis_sync.RedisError:
        pass  # Redis yoksa app zaten ilk oran-sınırlı uçta hata verir

    from tenderiq_api.main import create_app

    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()
