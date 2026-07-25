"""``GET /api/v1/panel`` toplu özeti: sayımlar, kota, son tarih sıralaması, maruziyet.

Bulgular DB'ye doğrudan tohumlanır (pipeline sahteleri gerekmez): sınanan şey
panel sözleşmesidir — durum sayımları, yalnız ``review_ready`` ihalelerin
bulgularının sayılması, reddedilenlerin dışlanması, tarihe göre sıralama ve
kiracı izolasyonu.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import tenderiq_worker.db as worker_db
from tenderiq_core.findings import (
    ComplianceStatus,
    GroundingResolution,
    ReviewStatus,
    RiskCategory,
    RiskSeverity,
    TimelineKind,
)
from tenderiq_core.models import (
    ComplianceResult,
    Document,
    DocumentKind,
    DocumentStatus,
    RiskFlag,
    Tender,
    TenderStatus,
    TimelineEvent,
)
from tenderiq_core.models import ParsedElement as ParsedElementRow
from tenderiq_core.parsing.types import ElementKind, ParseSource

pytestmark = pytest.mark.integration

QUOTE = "Teklifler son teklif verme tarihine kadar sunulur."


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient, *, slug: str, email: str) -> tuple[str, str]:
    register = client.post(
        "/api/v1/auth/register",
        json={"org_name": slug, "org_slug": slug, "email": email, "password": "sifre-12345"},
    )
    assert register.status_code == 201, register.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "sifre-12345"})
    assert login.status_code == 200
    return register.json()["tenant_id"], login.json()["access_token"]


class PanelEnv:
    """İki ihale tohumlar: biri ``review_ready`` (bulgulu), biri ``analyzing``."""

    def __init__(self, client: TestClient) -> None:
        suffix = uuid.uuid4().hex[:8]
        self.client = client
        self.tenant_id, self.token = _register_and_login(
            client, slug=f"org-pnl-{suffix}", email=f"pnl-{suffix}@org.com"
        )

        ready = client.post(
            "/api/v1/tenders", json={"title": "Hazır İhale"}, headers=_auth(self.token)
        )
        assert ready.status_code == 201
        self.ready_id = ready.json()["id"]

        busy = client.post(
            "/api/v1/tenders", json={"title": "Analizdeki İhale"}, headers=_auth(self.token)
        )
        assert busy.status_code == 201
        self.busy_id = busy.json()["id"]

        tenant_uuid = uuid.UUID(self.tenant_id)
        ready_uuid = uuid.UUID(self.ready_id)
        document_id = uuid.uuid4()
        element_id = uuid.uuid4()
        self.near_deadline_id = uuid.uuid4()
        self.far_deadline_id = uuid.uuid4()
        self.unparsable_deadline_id = uuid.uuid4()
        self.rejected_deadline_id = uuid.uuid4()
        self.risk_id = uuid.uuid4()
        self.low_risk_id = uuid.uuid4()
        self.unmet_id = uuid.uuid4()
        self.met_id = uuid.uuid4()

        worker_db._engine = None
        worker_db._factory = None
        with worker_db.tenant_session(tenant_uuid) as session:
            # İki ihalenin durumunu panelin beklediği duruma çek.
            for tender_id, status in (
                (ready_uuid, TenderStatus.REVIEW_READY),
                (uuid.UUID(self.busy_id), TenderStatus.ANALYZING),
            ):
                tender = session.get(Tender, tender_id)
                assert tender is not None
                tender.status = status

            session.add(
                Document(
                    id=document_id,
                    tenant_id=tenant_uuid,
                    tender_id=ready_uuid,
                    filename="şartname.pdf",
                    content_type="application/pdf",
                    storage_key=f"{self.tenant_id}/{self.ready_id}/{document_id}/sartname.pdf",
                    kind=DocumentKind.ADMINISTRATIVE,
                    status=DocumentStatus.UPLOADED,
                    size_bytes=1234,
                )
            )
            session.add(
                ParsedElementRow(
                    id=element_id,
                    tenant_id=tenant_uuid,
                    document_id=document_id,
                    seq=0,
                    page=4,
                    kind=ElementKind.PARAGRAPH,
                    source=ParseSource.DIGITAL,
                    text=QUOTE,
                    section="Madde 7.2",
                    bbox_x0=72.0,
                    bbox_y0=120.0,
                    bbox_x1=480.0,
                    bbox_y1=150.0,
                )
            )
            # Bulgular doküman ve kaynak öğeye FK ile bağlı; onlar yazılmadan
            # eklenirse flush sırası FK ihlaline düşebilir.
            session.flush()

            common = {
                "tenant_id": tenant_uuid,
                "tender_id": ready_uuid,
                "document_id": document_id,
                "source_element_id": element_id,
                "grounding_resolution": GroundingResolution.ELEMENT,
                "source_quote": QUOTE,
            }

            # Takvim: seq sırası bilinçli olarak tarih sırasının TERSİ — sıralamanın
            # metin/seq değil, ayrıştırılmış tarihe göre yapıldığını kanıtlar.
            session.add(
                TimelineEvent(
                    id=self.far_deadline_id,
                    seq=0,
                    label="Sözleşme imza tarihi",
                    kind=TimelineKind.OTHER,
                    value_text="20 Aralık 2026",
                    **common,
                )
            )
            session.add(
                TimelineEvent(
                    id=self.near_deadline_id,
                    seq=1,
                    label="Son teklif verme tarihi",
                    kind=TimelineKind.BID_DEADLINE,
                    value_text="15.08.2026",
                    **common,
                )
            )
            session.add(
                TimelineEvent(
                    id=self.unparsable_deadline_id,
                    seq=2,
                    label="Teslim süresi",
                    kind=TimelineKind.OTHER,
                    value_text="sözleşmeden itibaren 90 gün",
                    **common,
                )
            )
            session.add(
                TimelineEvent(
                    id=self.rejected_deadline_id,
                    seq=3,
                    label="Yanlış çıkarılmış tarih",
                    kind=TimelineKind.OTHER,
                    value_text="01.01.2026",
                    review_status=ReviewStatus.REJECTED,
                    **common,
                )
            )

            session.add(
                RiskFlag(
                    id=self.risk_id,
                    seq=0,
                    text="Gecikme cezası oranı yüksektir.",
                    severity=RiskSeverity.HIGH,
                    category=RiskCategory.PENALTY,
                    **common,
                )
            )
            session.add(
                RiskFlag(
                    id=self.low_risk_id,
                    seq=1,
                    text="Teslim adresi net değil.",
                    severity=RiskSeverity.LOW,
                    category=RiskCategory.OTHER,
                    **common,
                )
            )
            session.add(
                ComplianceResult(
                    id=self.unmet_id,
                    seq=0,
                    requirement_text="ISO 27001 belgesi zorunludur.",
                    status=ComplianceStatus.UNMET,
                    rationale="Profilde bu belge yok.",
                    **common,
                )
            )
            session.add(
                ComplianceResult(
                    id=self.met_id,
                    seq=1,
                    requirement_text="Vergi borcu bulunmamalıdır.",
                    status=ComplianceStatus.MET,
                    rationale="Profil karşılıyor.",
                    **common,
                )
            )


@pytest.fixture
def panel_env(api_client: TestClient) -> PanelEnv:
    return PanelEnv(api_client)


def test_panel_sayimlari_ve_kotayi_dondurur(panel_env: PanelEnv) -> None:
    response = panel_env.client.get("/api/v1/panel", headers=_auth(panel_env.token))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["tenders"] == {
        "total": 2,
        "draft": 0,
        "analyzing": 1,
        "review_ready": 1,
        "archived": 0,
    }
    # Yeni kiracı → varsayılan FREE plan; kullanım henüz yok.
    assert body["plan"] == "free"
    assert body["documents"]["used"] == 0
    assert body["documents"]["limit"] == 5
    assert body["pages"]["limit"] == 150
    assert body["period_end"] is not None

    # Analizdeki ihale "işleniyor" listesinde, hazır olan değil.
    assert [item["id"] for item in body["in_progress"]] == [panel_env.busy_id]


def test_son_tarihler_tarihe_gore_siralanir_reddedilen_haric(panel_env: PanelEnv) -> None:
    response = panel_env.client.get("/api/v1/panel", headers=_auth(panel_env.token))
    assert response.status_code == 200
    deadlines = response.json()["deadlines"]

    # Reddedilen (01.01.2026 — en yakın tarih) listede OLMAMALI; olsaydı başa gelirdi.
    ids = [item["id"] for item in deadlines]
    assert str(panel_env.rejected_deadline_id) not in ids

    # Sıra: yakın tarih → uzak tarih → ayrıştırılamayan (seq sırası bunun tersiydi).
    assert ids == [
        str(panel_env.near_deadline_id),
        str(panel_env.far_deadline_id),
        str(panel_env.unparsable_deadline_id),
    ]

    near = deadlines[0]
    assert near["due_date"] == "2026-08-15"
    assert near["value_text"] == "15.08.2026"  # ham metin kaynağa sadık kalır
    assert near["tender_title"] == "Hazır İhale"
    assert near["page"] == 4
    assert near["section"] == "Madde 7.2"

    # Ayrıştırılamayan değer bulguyu yok etmez; tarihsiz olarak sonda durur.
    assert deadlines[-1]["due_date"] is None
    assert deadlines[-1]["value_text"] == "sözleşmeden itibaren 90 gün"


def test_maruziyet_yalniz_yuksek_risk_ve_karsilanmayan_gereksinim(panel_env: PanelEnv) -> None:
    response = panel_env.client.get("/api/v1/panel", headers=_auth(panel_env.token))
    assert response.status_code == 200
    exposures = response.json()["exposures"]

    ids = [item["id"] for item in exposures]
    assert str(panel_env.low_risk_id) not in ids  # düşük risk eleme sebebi değil
    assert str(panel_env.met_id) not in ids  # karşılanan gereksinim maruziyet değil

    # Karşılanmayan gereksinim, sözleşme riskinden ÖNCE gelir.
    assert ids == [str(panel_env.unmet_id), str(panel_env.risk_id)]
    assert exposures[0]["source"] == "compliance"
    assert exposures[0]["text"] == "ISO 27001 belgesi zorunludur."
    assert exposures[1]["source"] == "risk"


def test_limit_parametresi_uygulanir(panel_env: PanelEnv) -> None:
    response = panel_env.client.get("/api/v1/panel?limit=1", headers=_auth(panel_env.token))
    assert response.status_code == 200
    body = response.json()
    assert len(body["deadlines"]) == 1
    assert len(body["exposures"]) == 1
    # Limit sıralamadan SONRA uygulanır: kalan, en yakın tarihli olmalı.
    assert body["deadlines"][0]["id"] == str(panel_env.near_deadline_id)


def test_panel_kiracilar_arasi_sizdirmaz(panel_env: PanelEnv, api_client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    _other_tenant, other_token = _register_and_login(
        api_client, slug=f"org-oth-{suffix}", email=f"oth-{suffix}@org.com"
    )
    response = api_client.get("/api/v1/panel", headers=_auth(other_token))
    assert response.status_code == 200
    body = response.json()

    assert body["tenders"]["total"] == 0
    assert body["deadlines"] == []
    assert body["exposures"] == []
    assert body["in_progress"] == []
