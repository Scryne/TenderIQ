# TenderIQ Celery worker imajı — uv tabanlı, katman önbellekli.
# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Bağımlılık manifestleri (önbellek).
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
# parsing+ocr grupları: hibrit hat (docling+pypdf) ve EasyOCR yalnızca worker
# imajına kurulur (ADR-0004/0011); API imajı bu ağır yığını taşımaz.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --no-dev --group parsing --group ocr

# 2) Kaynak kod + kurulum.
COPY packages ./packages
COPY apps ./apps
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group parsing --group ocr

ENV PATH="/app/.venv/bin:$PATH"

# -B: gömülü beat (zamanlanmış temizlik). Worker çoğaltılırsa beat ayrı servise alınmalı.
CMD ["celery", "-A", "tenderiq_worker.celery_app:celery_app", "worker", \
     "--loglevel=info", "--queues=tenderiq", "-B"]
