# TenderIQ API imajı — uv tabanlı, katman önbellekli.
# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Taban imajın Debian paketlerini güvenlik yamalarına çek (trivy imaj kapısı,
# J.2 #7). Upstream imaj her CVE'de yeniden derlenmediğinden openssl/krb5/gnutls
# gibi paketler yamalı sürümün gerisinde kalıyor; bunlar bizim eklediğimiz değil,
# devraldığımız açıklar. `upgrade` yeni paket KURMAZ, yalnız mevcutları tazeler.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Yalnızca bağımlılık manifestleri — bağımlılık katmanını önbelleğe al.
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --no-dev

# 2) Kaynak kod + workspace paketlerinin kurulumu.
COPY packages ./packages
COPY apps ./apps
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Root olarak koşmama (trivy DS-0002, J.2 sertleştirme): konteyner kaçışı
# durumunda saldırgan host'ta root yetkisiyle başlamasın. Kurulum adımlarından
# SONRA geçilir — uv sync'in /app'e yazması gerekir.
RUN groupadd --system --gid 1001 tenderiq \
    && useradd --system --uid 1001 --gid tenderiq --no-create-home tenderiq \
    && chown -R tenderiq:tenderiq /app
USER tenderiq

EXPOSE 8000
CMD ["uvicorn", "tenderiq_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
