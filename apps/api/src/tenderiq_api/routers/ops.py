"""/ops/metrics — operatör metrik ucu (J.4 metrik panosu).

Kiracı API'sinin (``/api/v1``) parçası DEĞİLDİR: kiracı verisi döndürmez,
kiracı kimliğiyle erişilmez. Kurulum genelindeki toplam sayaçları (istek
hacmi, gecikme yüzdelikleri, kuyruk derinliği, işleme başarı oranı) ve bunların
SLO hedeflerine göre yargısını döndürür — basit bir pano/uyarıcı bu tek ucu
çekerek beslenir.

Erişim: ``Authorization: Bearer <OPS_METRICS_TOKEN>``. Token yapılandırılmamışsa
uç **404** döner; kapalı bir kurulumda ucun varlığı bile sızmaz. OpenAPI
sözleşmesine dâhil edilmez (``include_in_schema=False``) — frontend istemcisi
üretilirken operatör yüzeyi müşteri sözleşmesine karışmaz.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, Field

from tenderiq_api.errors import NotFoundError, UnauthorizedError
from tenderiq_core.config import get_settings
from tenderiq_core.ops import MAX_WINDOW_MINUTES, OpsSnapshot, collect_snapshot
from tenderiq_core.services import dead_letter as dead_letter_service

router = APIRouter(prefix="/ops", tags=["ops"], include_in_schema=False)

_BEARER_PREFIX = "bearer "


class ApiWindowResponse(BaseModel):
    """Pencere boyunca API isteklerinin özeti."""

    requests: int
    server_errors: int
    client_errors: int
    availability: float | None
    p50_ms: float | None
    p95_ms: float | None


class PhaseWindowResponse(BaseModel):
    """Bir işleme fazının pencere özeti."""

    phase: str
    completed: int
    failed: int
    success_rate: float | None
    p50_seconds: float | None
    p95_seconds: float | None


class SloVerdictResponse(BaseModel):
    """Tek bir SLO'nun durumu. ``ok=null`` → pencerede ölçecek veri yok."""

    key: str
    description: str
    target: str
    actual: str
    ok: bool | None


class OpsMetricsResponse(BaseModel):
    """Operasyon panosunun tek çağrılık görüntüsü."""

    generated_at: datetime
    window_minutes: int
    queue_depth: int = Field(description="Celery kuyruğunda bekleyen iş sayısı.")
    dead_letter_pending: int | None = Field(
        description=(
            "Uygulanamamış ödeme olayı sayısı (ölü mektup kuyruğu). SIFIRDAN "
            "FARKLIYSA insan bakmalı: her satır, karşılığı verilmemiş bir ödeme "
            "ya da uygulanmamış bir erişim değişikliği olabilir. ``null`` "
            "ÖLÇÜLEMEDİ demektir (sıfır DEĞİL) — sayaç okunamadığında 'kuyruk "
            "boş' demek, panoyu yanlışlıkla yeşile boyardı."
        )
    )
    api: ApiWindowResponse
    phases: list[PhaseWindowResponse]
    slos: list[SloVerdictResponse]
    healthy: bool = Field(description="Hiçbir SLO ihlal edilmiyor mu.")


def _require_ops_token(authorization: str | None) -> None:
    """Ops token'ını doğrular; yapılandırılmamışsa ucu yok sayar (404)."""
    configured = get_settings().ops_metrics_token
    if not configured:
        raise NotFoundError("Bulunamadı.")
    header = authorization or ""
    if not header.lower().startswith(_BEARER_PREFIX):
        raise UnauthorizedError("Ops token'ı gerekli.")
    presented = header[len(_BEARER_PREFIX) :].strip()
    # Sabit-zamanlı karşılaştırma: token uzunluğu/önekini zamanlama ile sızdırmaz.
    if not secrets.compare_digest(presented, configured):
        raise UnauthorizedError("Ops token'ı geçersiz.")


def _to_response(snapshot: OpsSnapshot, *, dead_letter_pending: int | None) -> OpsMetricsResponse:
    return OpsMetricsResponse(
        generated_at=snapshot.generated_at,
        window_minutes=snapshot.window_minutes,
        queue_depth=snapshot.queue_depth,
        dead_letter_pending=dead_letter_pending,
        api=ApiWindowResponse(
            requests=snapshot.api.requests,
            server_errors=snapshot.api.server_errors,
            client_errors=snapshot.api.client_errors,
            availability=snapshot.api.availability,
            p50_ms=snapshot.api.p50_ms,
            p95_ms=snapshot.api.p95_ms,
        ),
        phases=[
            PhaseWindowResponse(
                phase=phase.phase,
                completed=phase.completed,
                failed=phase.failed,
                success_rate=phase.success_rate,
                p50_seconds=phase.p50_seconds,
                p95_seconds=phase.p95_seconds,
            )
            for phase in snapshot.phases
        ],
        slos=[
            SloVerdictResponse(
                key=verdict.key,
                description=verdict.description,
                target=verdict.target,
                actual=verdict.actual,
                ok=verdict.ok,
            )
            for verdict in snapshot.slos
        ],
        healthy=not snapshot.breaching,
    )


@router.get("/metrics", response_model=OpsMetricsResponse)
async def ops_metrics(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    window: Annotated[int | None, Query(ge=1, le=MAX_WINDOW_MINUTES)] = None,
) -> OpsMetricsResponse:
    """Yuvarlanan penceredeki operasyon metrikleri + SLO yargısı."""
    _require_ops_token(authorization)
    settings = get_settings()
    snapshot = await collect_snapshot(
        request.app.state.redis,
        window_minutes=window or settings.ops_metrics_window_minutes,
    )
    # Kuyruk boyutu Redis kümesinden okunur, veritabanından DEĞİL: ops ucu
    # kiracı bağlamı kurmaz ve `webhook_dead_letter` SELECT'i RLS'ye tabidir,
    # yani DB'den yapılan bir sayım her zaman sıfır dönerdi — sessizce yanlış
    # bir 'her şey yolunda' metriği.
    dead_letter_pending = await dead_letter_service.pending_count(request.app.state.redis)
    return _to_response(snapshot, dead_letter_pending=dead_letter_pending)
