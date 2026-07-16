"""Sprint 1.1/1.2 uçtan uca akış: doküman kaydı → tamamlama → işleme hattı → parse verisi.

Nesne depolama sahte (in-memory) servisle, kuyruklama stub ile, hibrit parser
sahte parser'la değiştirilir (Docling gerektirmez); worker pipeline'ı Celery
broker'sız, senkron çağrılarak aynı test DB'sinde koşar.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

import tenderiq_worker.db as worker_db
import tenderiq_worker.parsing as worker_parsing
from tenderiq_core.models import Document, Job, JobStatus
from tenderiq_core.models import ParsedElement as ParsedElementRow
from tenderiq_core.parsing import (
    BoundingBox,
    ElementKind,
    ParsedDocument,
    ParsedElement,
    ParseSource,
)
from tenderiq_core.storage import ObjectInfo
from tenderiq_worker.tasks import documents as document_tasks
from tenderiq_worker.tasks.documents import _run_pipeline, cleanup_stale_uploads

pytestmark = pytest.mark.integration

PDF_BYTES = b"%PDF-1.7\n%TenderIQ test\n"

# Sahte parser çıktısı: 2 sayfa, sayfa+bbox'lı öğeler (izlenebilirlik sözleşmesi).
FAKE_PARSED = ParsedDocument(
    elements=[
        ParsedElement(
            text="1. KAPSAM",
            page=1,
            kind=ElementKind.HEADING,
            bbox=BoundingBox(x0=72.0, y0=90.0, x1=200.0, y1=110.0),
        ),
        ParsedElement(
            text="Yüklenici tüm maddeleri karşılamak zorundadır.",
            page=2,
            kind=ElementKind.PARAGRAPH,
            bbox=BoundingBox(x0=72.0, y0=120.0, x1=480.0, y1=150.0),
            section="1. KAPSAM",
        ),
    ],
    page_count=2,
    source=ParseSource.DIGITAL,
)


class FakeStorage:
    """StorageService arayüzünün in-memory eşleniği."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def presigned_put_url(self, key: str, *, content_type: str, expires_in: int = 3600) -> str:
        return f"https://fake-storage.local/{key}?put"

    def presigned_get_url(self, key: str, *, expires_in: int = 3600) -> str:
        return f"https://fake-storage.local/{key}?get"

    def head_object(self, key: str) -> ObjectInfo | None:
        data = self.objects.get(key)
        if data is None:
            return None
        return ObjectInfo(size_bytes=len(data), content_type="")

    def read_prefix(self, key: str, *, length: int) -> bytes:
        return self.objects[key][:length]

    def download_file(self, key: str, destination: Path) -> None:
        destination.write_bytes(self.objects[key])

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)
        self.deleted.append(key)


class FakeDocumentParser:
    """Hibrit parser'ın sabit sonuçlu eşleniği (parse fazının DB yazımını test eder)."""

    def __init__(self) -> None:
        self.paths: list[Path] = []

    def parse(self, path: Path) -> ParsedDocument:
        self.paths.append(path)
        return FAKE_PARSED


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


@pytest.fixture
def pipeline_client(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, FakeStorage, list[tuple]]:
    """api_client + sahte depolama/parser + kuyruklama kaydedici; worker fabrikası sıfırlanır."""
    fake_storage = FakeStorage()
    enqueued: list[tuple] = []
    api_client.app.state.storage = fake_storage  # type: ignore[attr-defined]
    api_client.app.state.enqueue_document_job = (  # type: ignore[attr-defined]
        lambda job_id, tenant_id: enqueued.append((job_id, tenant_id))
    )
    # Parse fazı sahte depolama + sahte parser kullanır (Docling/R2 gerektirmez).
    monkeypatch.setattr(worker_parsing, "_storage", fake_storage)
    monkeypatch.setattr(worker_parsing, "_parser", FakeDocumentParser())
    # Worker sync engine, bu fixture'ın DATABASE_URL'ini görsün diye sıfırlanır.
    worker_db._engine = None
    worker_db._factory = None
    return api_client, fake_storage, enqueued


def test_yukleme_tamamlama_ve_pipeline(
    pipeline_client: tuple[TestClient, FakeStorage, list[tuple]],
) -> None:
    client, storage, enqueued = pipeline_client
    tenant_id, token = _register_and_login(client, slug="org-flow", email="flow@org.com")

    tender = client.post("/api/v1/tenders", json={"title": "Akış İhalesi"}, headers=_auth(token))
    assert tender.status_code == 201
    tender_id = tender.json()["id"]

    # Allowlist: izinsiz içerik türü kayıt aşamasında reddedilir.
    bad_type = client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": "zarar.html", "content_type": "text/html"},
        headers=_auth(token),
    )
    assert bad_type.status_code == 400
    assert bad_type.json()["error"]["code"] == "validation_error"

    # Idempotency-Key: aynı anahtar ikinci kez yeni kayıt açmaz.
    headers = {**_auth(token), "Idempotency-Key": "yukleme-1"}
    first = client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": "şartname.pdf", "content_type": "application/pdf"},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    document = first.json()["document"]
    storage_key = first.json()["storage_key"]
    replay = client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": "şartname.pdf", "content_type": "application/pdf"},
        headers=headers,
    )
    assert replay.json()["document"]["id"] == document["id"]

    # Nesne henüz yüklenmemişken tamamlama → 409.
    too_early = client.post(f"/api/v1/documents/{document['id']}/complete", headers=_auth(token))
    assert too_early.status_code == 409

    # "Yükleme" yapılır ve tamamlama doğrulamadan geçer.
    storage.objects[storage_key] = PDF_BYTES
    complete = client.post(f"/api/v1/documents/{document['id']}/complete", headers=_auth(token))
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["document"]["status"] == "uploaded"
    assert body["document"]["size_bytes"] == len(PDF_BYTES)
    job_id = body["job"]["id"]
    assert body["job"]["status"] == "queued"
    assert enqueued == [(uuid.UUID(job_id), uuid.UUID(tenant_id))]

    # Tamamlama idempotent: ikinci çağrı aynı işi döndürür, YENİ iş yaratmaz.
    # Hâlâ queued olan iş yeniden yayınlanır (ilk yayın broker kesintisinde
    # kaybolmuş olabilir; task idempotent olduğundan mükerrer teslim güvenlidir).
    again = client.post(f"/api/v1/documents/{document['id']}/complete", headers=_auth(token))
    assert again.status_code == 200
    assert again.json()["job"]["id"] == job_id
    assert enqueued == [(uuid.UUID(job_id), uuid.UUID(tenant_id))] * 2

    # İş durumu sorgulanır.
    job = client.get(f"/api/v1/jobs/{job_id}", headers=_auth(token))
    assert job.status_code == 200
    assert job.json()["status"] == "queued"

    # Worker pipeline'ı senkron koşulur (Celery broker'sız).
    result = _run_pipeline(uuid.UUID(job_id), uuid.UUID(tenant_id))
    assert result == "review_ready"
    # İkinci koşum idempotent no-op'tur.
    assert _run_pipeline(uuid.UUID(job_id), uuid.UUID(tenant_id)) == "already_terminal"

    job_after = client.get(f"/api/v1/jobs/{job_id}", headers=_auth(token)).json()
    assert job_after["status"] == "review_ready"
    assert job_after["attempts"] == 1
    assert job_after["finished_at"] is not None

    # İş nihai duruma ulaştıktan sonra complete artık yeniden yayınlamaz.
    terminal = client.post(f"/api/v1/documents/{document['id']}/complete", headers=_auth(token))
    assert terminal.status_code == 200
    assert terminal.json()["job"]["status"] == "review_ready"
    assert len(enqueued) == 2
    tender_after = client.get(f"/api/v1/tenders/{tender_id}", headers=_auth(token)).json()
    assert tender_after["status"] == "review_ready"

    # Parse fazı izlenebilirlik verisini yazdı: her öğe sayfa + bbox + kaynak taşır.
    document_uuid = uuid.UUID(document["id"])
    tenant_uuid = uuid.UUID(tenant_id)
    with worker_db.tenant_session(tenant_uuid) as session:
        rows = list(
            session.scalars(
                select(ParsedElementRow)
                .where(ParsedElementRow.document_id == document_uuid)
                .order_by(ParsedElementRow.seq)
            )
        )
        assert [(row.seq, row.page) for row in rows] == [(0, 1), (1, 2)]
        assert rows[0].kind is ElementKind.HEADING
        assert rows[0].source is ParseSource.DIGITAL
        assert rows[0].bbox_x0 is not None
        assert rows[1].section == "1. KAPSAM"
        doc_row = session.get(Document, document_uuid)
        assert doc_row is not None
        assert doc_row.page_count == 2

    # Parse fazı idempotent: yeniden koşum öğeleri çoğaltmaz (delete+insert).
    worker_parsing.run_parsing_phase(uuid.UUID(job_id), tenant_uuid)
    with worker_db.tenant_session(tenant_uuid) as session:
        count = len(
            list(
                session.scalars(
                    select(ParsedElementRow.id).where(ParsedElementRow.document_id == document_uuid)
                )
            )
        )
        assert count == 2

    # SSE: ilk status event'i anlık görüntüyü taşır. Akış, max_ticks ile sunucu
    # tarafından kapatılır; test istemci iptaline (TestClient'ta güvenilmez) dayanmaz.
    with client.stream(
        "GET", f"/api/v1/tenders/{tender_id}/stream?max_ticks=2", headers=_auth(token)
    ) as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        event_lines = [line for line in stream.iter_lines() if line]
        assert "event: status" in event_lines
        payload = json.loads(next(x for x in event_lines if x.startswith("data:"))[len("data:") :])
        assert payload["tender"]["status"] == "review_ready"
        assert payload["documents"][0]["job"]["status"] == "review_ready"

    # Kiracılar arası sızıntı: B, A'nın işini göremez (RLS → 404).
    _tenant_b, token_b = _register_and_login(client, slug="org-flow-b", email="b@flowb.com")
    cross = client.get(f"/api/v1/jobs/{job_id}", headers=_auth(token_b))
    assert cross.status_code == 404


def test_magic_bytes_sahteciligi_reddedilir(
    pipeline_client: tuple[TestClient, FakeStorage, list[tuple]],
) -> None:
    client, storage, enqueued = pipeline_client
    _tenant_id, token = _register_and_login(client, slug="org-magic", email="magic@org.com")
    tender_id = client.post(
        "/api/v1/tenders", json={"title": "Magic"}, headers=_auth(token)
    ).json()["id"]

    created = client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": "sahte.pdf", "content_type": "application/pdf"},
        headers=_auth(token),
    ).json()
    storage_key = created["storage_key"]
    document_id = created["document"]["id"]

    # PDF beyan edilmiş ama içerik ZIP → reddedilir, nesne silinir, doküman failed.
    storage.objects[storage_key] = b"PK\x03\x04zip-icerik"
    rejected = client.post(f"/api/v1/documents/{document_id}/complete", headers=_auth(token))
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "validation_error"
    assert storage_key in storage.deleted
    assert enqueued == []

    docs = client.get(f"/api/v1/tenders/{tender_id}/documents", headers=_auth(token)).json()
    assert docs[0]["status"] == "failed"

    # failed durumdan tekrar tamamlama denenirse 409.
    conflict = client.post(f"/api/v1/documents/{document_id}/complete", headers=_auth(token))
    assert conflict.status_code == 409


def test_pipeline_ara_durumdan_devam_eder(
    pipeline_client: tuple[TestClient, FakeStorage, list[tuple]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, storage, _enqueued = pipeline_client
    tenant_id, token = _register_and_login(client, slug="org-resume", email="resume@org.com")
    tender_id = client.post(
        "/api/v1/tenders", json={"title": "Devam"}, headers=_auth(token)
    ).json()["id"]
    created = client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": "devam.pdf", "content_type": "application/pdf"},
        headers=_auth(token),
    ).json()
    storage.objects[created["storage_key"]] = PDF_BYTES
    job_id = client.post(
        f"/api/v1/documents/{created['document']['id']}/complete", headers=_auth(token)
    ).json()["job"]["id"]

    # Parsing fazı ilk koşumda patlar → iş ara durumda (parsing) kalır.
    def _patlayan_faz(job: uuid.UUID, tenant: uuid.UUID) -> None:
        raise RuntimeError("parse patladı")

    monkeypatch.setitem(
        document_tasks._PHASE_HANDLERS, document_tasks.JobStatus.PARSING, _patlayan_faz
    )
    with pytest.raises(RuntimeError, match="parse patladı"):
        _run_pipeline(uuid.UUID(job_id), uuid.UUID(tenant_id))

    mid = client.get(f"/api/v1/jobs/{job_id}", headers=_auth(token)).json()
    assert mid["status"] == "parsing"
    assert mid["attempts"] == 1

    # Faz düzelir; ikinci koşum baştan değil, kaldığı fazdan devam eder.
    monkeypatch.setitem(
        document_tasks._PHASE_HANDLERS,
        document_tasks.JobStatus.PARSING,
        lambda job, tenant: None,
    )
    assert _run_pipeline(uuid.UUID(job_id), uuid.UUID(tenant_id)) == "review_ready"
    final = client.get(f"/api/v1/jobs/{job_id}", headers=_auth(token)).json()
    assert final["attempts"] == 2


def test_failed_is_yeniden_kuyruklanir(
    pipeline_client: tuple[TestClient, FakeStorage, list[tuple]],
) -> None:
    """failed → queued yeniden kuyruklama ucu: durum sıfırlanır, iş yeniden yayınlanır."""
    client, storage, enqueued = pipeline_client
    tenant_id, token = _register_and_login(client, slug="org-retry", email="retry@org.com")
    tender_id = client.post(
        "/api/v1/tenders", json={"title": "Retry"}, headers=_auth(token)
    ).json()["id"]
    created = client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": "retry.pdf", "content_type": "application/pdf"},
        headers=_auth(token),
    ).json()
    storage.objects[created["storage_key"]] = PDF_BYTES
    job_id = client.post(
        f"/api/v1/documents/{created['document']['id']}/complete", headers=_auth(token)
    ).json()["job"]["id"]
    assert len(enqueued) == 1

    # queued (failed olmayan) işte retry reddedilir.
    premature = client.post(f"/api/v1/jobs/{job_id}/retry", headers=_auth(token))
    assert premature.status_code == 409

    # İşi kalıcı hataya düşmüş gibi işaretle (deneme tükenmiş worker senaryosu).
    with worker_db.tenant_session(uuid.UUID(tenant_id)) as session:
        job = session.get(Job, uuid.UUID(job_id))
        assert job is not None
        job.transition_to(JobStatus.FAILED)
        job.error_message = "RuntimeError: parse patladı"

    retried = client.post(f"/api/v1/jobs/{job_id}/retry", headers=_auth(token))
    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["status"] == "queued"
    assert body["error_message"] is None
    assert enqueued[-1] == (uuid.UUID(job_id), uuid.UUID(tenant_id))
    assert len(enqueued) == 2

    # Yeniden kuyruklanan iş hattı uçtan uca tamamlayabilir.
    assert _run_pipeline(uuid.UUID(job_id), uuid.UUID(tenant_id)) == "review_ready"

    # Kiracılar arası sızıntı: B, A'nın işini yeniden kuyruklayamaz (RLS → 404).
    _tenant_b, token_b = _register_and_login(client, slug="org-retry-b", email="b@retryb.com")
    cross = client.post(f"/api/v1/jobs/{job_id}/retry", headers=_auth(token_b))
    assert cross.status_code == 404


def test_yarim_yuklemeler_supurulur(
    pipeline_client: tuple[TestClient, FakeStorage, list[tuple]],
) -> None:
    client, storage, _enqueued = pipeline_client
    tenant_id, token = _register_and_login(client, slug="org-stale", email="stale@org.com")
    tender_id = client.post(
        "/api/v1/tenders", json={"title": "Süpürge"}, headers=_auth(token)
    ).json()["id"]
    created = client.post(
        f"/api/v1/tenders/{tender_id}/documents",
        json={"filename": "unutulan.pdf", "content_type": "application/pdf"},
        headers=_auth(token),
    ).json()
    document_id = created["document"]["id"]
    # Dosya depoya kondu ama complete hiç çağrılmadı (yarım yükleme senaryosu).
    storage.objects[created["storage_key"]] = PDF_BYTES

    # Kaydı 48 saat önceye çek (pending_upload TTL'i 24 saat).
    with worker_db.tenant_session(uuid.UUID(tenant_id)) as session:
        session.execute(
            text("UPDATE document SET created_at = now() - interval '48 hours' WHERE id = :id"),
            {"id": document_id},
        )

    assert cleanup_stale_uploads() >= 1
    docs = client.get(f"/api/v1/tenders/{tender_id}/documents", headers=_auth(token)).json()
    assert docs[0]["status"] == "failed"
    # Depodaki yetim nesne de temizlendi.
    assert created["storage_key"] in storage.deleted
