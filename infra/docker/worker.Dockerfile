# TenderIQ Celery worker imajı — uv tabanlı, katman önbellekli.
# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Taban imajın devraldığı Debian CVE'leri için güvenlik yaması (bkz. api.Dockerfile).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Bağımlılık manifestleri (önbellek).
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
# parsing+ocr+embedding grupları: hibrit hat (docling+pypdf), EasyOCR ve BGE-M3
# yalnızca worker imajına kurulur (ADR-0004/0011/0008); API imajı hafif kalır.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --no-dev --group parsing --group ocr --group embedding

# 2) Kaynak kod + kurulum.
COPY packages ./packages
COPY apps ./apps
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group parsing --group ocr --group embedding

ENV PATH="/app/.venv/bin:$PATH"

# Root olarak koşmama (trivy DS-0002, J.2 sertleştirme).
#
# API imajının aksine burada kullanıcının GERÇEK bir ev dizini olmalı: docling ve
# EasyOCR modelleri (ADR-0004/0011) çalışma anında indirilip ev dizini altındaki
# önbelleğe yazılır. Home'suz bir kullanıcıda ilk taranmış doküman OCR aşamasında
# yazma hatasıyla düşerdi. Önbellek yolları açıkça verilir ki kalıcı bir volume
# bağlamak istendiğinde tek dizin yeter (aksi hâlde her konteynerde yeniden iner —
# root ile de durum böyleydi, bu bir gerileme değil).
RUN groupadd --system --gid 1001 tenderiq \
    && useradd --system --uid 1001 --gid tenderiq --create-home --home-dir /home/tenderiq tenderiq \
    && mkdir -p /home/tenderiq/.cache/huggingface /home/tenderiq/.EasyOCR \
    && chown -R tenderiq:tenderiq /app /home/tenderiq
ENV HOME=/home/tenderiq \
    XDG_CACHE_HOME=/home/tenderiq/.cache \
    HF_HOME=/home/tenderiq/.cache/huggingface \
    EASYOCR_MODULE_PATH=/home/tenderiq/.EasyOCR
USER tenderiq

# -B: gömülü beat (zamanlanmış temizlik). Worker çoğaltılırsa beat ayrı servise alınmalı.
CMD ["celery", "-A", "tenderiq_worker.celery_app:celery_app", "worker", \
     "--loglevel=info", "--queues=tenderiq", "-B"]
