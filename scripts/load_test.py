"""Yük/dayanıklılık testi (J.4): eşzamanlı çok-kiracılı yükleme + işleme.

Plan senaryosu (Faz 4): *N kiracı × M doküman × P sayfa* aynı anda yüklenir ve
hepsi ``review_ready`` veya ``failed`` olana dek izlenir. Ölçülen büyüklükler
doğrudan J.4 SLO'larına bağlanır:

===========================  ==========================================
Ölçüm                        SLO
===========================  ==========================================
API p95 gecikmesi            < 500 ms (yükleme/kayıt uçları)
İşleme süresi p95            < 10 dk (100 sayfalık dijital doküman)
İşleme başarı oranı          ≥ %98
Kuyruk derinliği             tepe değeri raporlanır (tıkanma erken uyarısı)
===========================  ==========================================

**Gerçek yığına karşı koşar** (staging tercih edilir): API + worker + Postgres +
Redis + nesne depolama ayakta olmalıdır. Üretim verisi oluşturur (kiracı, ihale,
doküman) — bu yüzden production'a karşı koşulmamalıdır.

    uv run python scripts/load_test.py --base-url http://localhost:8000
    uv run python scripts/load_test.py --tenants 10 --docs 3 --pages 100 --plan pro

Kota notu: ücretsiz plan aylık **5 doküman / 150 sayfa**dır. Varsayılan senaryo
(1 doküman × 100 sayfa) bu sınıra sığar; daha büyük koşular için ``--plan pro``
verin (yığın ``BILLING_PROVIDER=manual`` ile koşuyorsa yükseltme anında etkinleşir).

Çıkış kodu: tüm SLO'lar tutuyorsa 0, en az biri ihlal edilmişse 1 — CI'dan
zamanlanmış bir dayanıklılık koşusu olarak çağrılabilir.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx

# SLO eşikleri ürünün kendi modülünden gelir: betiğin hedefleri ile çalışan
# sistemin hedefleri ayrışamasın (ikisi ayrı yerde tanımlansaydı, biri
# güncellenip diğeri unutulduğunda yük testi yanlış bir "GEÇTİ" üretirdi).
from tenderiq_core.ops import SLO_API_P95_MS, SLO_JOB_SUCCESS_RATE, SLO_JOB_TOTAL_P95_SECONDS

DEFAULT_BASE_URL = "http://localhost:8000"
PASSWORD = "yuk-testi-12345"  # noqa: S105  (kısa ömürlü test kiracıları)

_TERMINAL_STATUSES = frozenset({"review_ready", "failed"})


@dataclass
class Latencies:
    """Bir uç grubunun gecikme örnekleri (ms)."""

    samples: list[float] = field(default_factory=list)

    def record(self, seconds: float) -> None:
        self.samples.append(seconds * 1000)

    def percentile(self, quantile: float) -> float | None:
        if not self.samples:
            return None
        ordered = sorted(self.samples)
        index = min(len(ordered) - 1, int(quantile * len(ordered)))
        return ordered[index]


@dataclass
class Outcome:
    """Tek bir dokümanın uçtan uca sonucu."""

    status: str
    duration_seconds: float | None
    detail: str = ""


@dataclass
class Report:
    api: Latencies
    outcomes: list[Outcome]
    peak_queue_depth: int
    wall_seconds: float

    @property
    def succeeded(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.status == "review_ready")

    @property
    def success_rate(self) -> float | None:
        finished = [o for o in self.outcomes if o.status in _TERMINAL_STATUSES]
        return (
            len([o for o in finished if o.status == "review_ready"]) / len(finished)
            if finished
            else None
        )

    def processing_percentile(self, quantile: float) -> float | None:
        durations = sorted(
            outcome.duration_seconds
            for outcome in self.outcomes
            if outcome.status == "review_ready" and outcome.duration_seconds is not None
        )
        if not durations:
            return None
        return durations[min(len(durations) - 1, int(quantile * len(durations)))]


def _synthetic_pdf(pages: int, label: str) -> bytes:
    """``pages`` sayfalık, metin katmanlı (dijital yol) sentetik PDF üretir.

    Gerçek şartname metnine benzemesi gerekmez: ölçülen şey çıkarımın KALİTESİ
    değil, hattın kapasitesidir. Ama metin katmanı olmalıdır — aksi hâlde parse
    OCR yoluna düşer ve test, hedeflediğinden bambaşka bir yolu ölçer.
    """
    try:
        from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
        from reportlab.pdfgen import canvas  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("reportlab gerekli: `uv sync --group parsing` ile kurun.") from exc

    import io

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    for page in range(1, pages + 1):
        pdf.drawString(72, 800, f"{label} — Madde {page}")
        for line in range(20):
            pdf.drawString(
                72,
                770 - line * 18,
                f"{page}.{line + 1} Yüklenici, teknik şartnamenin ilgili maddesini karşılamalıdır.",
            )
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


class TenantRunner:
    """Tek bir kiracının senaryosu: kayıt → ihale → N doküman yükle → tamamla."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        report: Report,
        *,
        index: int,
        docs: int,
        payload: bytes,
        plan: str | None,
    ) -> None:
        self._client = client
        self._report = report
        self._index = index
        self._docs = docs
        self._payload = payload
        self._plan = plan
        self._token = ""
        self.job_ids: list[str] = []

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _timed(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        """İsteği atar ve gecikmesini API histogramına kaydeder."""
        started = time.perf_counter()
        response = await self._client.request(method, url, **kwargs)  # type: ignore[arg-type]
        self._report.api.record(time.perf_counter() - started)
        return response

    async def setup(self) -> None:
        slug = f"yuk-{self._index}-{uuid.uuid4().hex[:8]}"
        register = await self._timed(
            "POST",
            "/api/v1/auth/register",
            json={
                "org_name": slug,
                "org_slug": slug,
                "email": f"{slug}@yuk-testi.local",
                "password": PASSWORD,
            },
        )
        register.raise_for_status()
        login = await self._timed(
            "POST",
            "/api/v1/auth/login",
            json={"email": f"{slug}@yuk-testi.local", "password": PASSWORD},
        )
        login.raise_for_status()
        self._token = login.json()["access_token"]

        if self._plan:
            upgrade = await self._timed(
                "POST", "/api/v1/billing/checkout", json={"plan": self._plan}, headers=self._auth()
            )
            if upgrade.status_code != 200:
                print(
                    f"  ! kiracı {self._index}: plan yükseltme başarısız "
                    f"({upgrade.status_code}) — ücretsiz kota geçerli",
                    file=sys.stderr,
                )

    async def run(self) -> None:
        tender = await self._timed(
            "POST",
            "/api/v1/tenders",
            json={"title": f"Yük Testi İhalesi {self._index}"},
            headers=self._auth(),
        )
        tender.raise_for_status()
        tender_id = tender.json()["id"]

        for sequence in range(self._docs):
            await self._upload_one(tender_id, sequence)

    async def _upload_one(self, tender_id: str, sequence: int) -> None:
        created = await self._timed(
            "POST",
            f"/api/v1/tenders/{tender_id}/documents",
            json={"filename": f"sartname-{sequence}.pdf", "content_type": "application/pdf"},
            headers=self._auth(),
        )
        if created.status_code == 402:
            self._report.outcomes.append(Outcome("quota", None, "plan kotası doldu"))
            return
        created.raise_for_status()
        body = created.json()

        # Nesne depolamaya doğrudan (imzalı URL) yükleme: bu istek API'nin değil,
        # R2/MinIO'nun gecikmesidir — API histogramına KARIŞMAMALIDIR.
        upload = await self._client.put(
            body["upload_url"],
            content=self._payload,
            headers={"Content-Type": "application/pdf"},
        )
        upload.raise_for_status()

        completed = await self._timed(
            "POST",
            f"/api/v1/documents/{body['document']['id']}/complete",
            headers=self._auth(),
        )
        completed.raise_for_status()
        self.job_ids.append(completed.json()["job"]["id"])

    async def poll(self, job_id: str, *, timeout_seconds: float) -> Outcome:
        """İşi nihai duruma ulaşana dek yoklar; süreyi sunucunun damgalarından alır."""
        started = time.monotonic()
        backoff = 1.0
        while time.monotonic() - started < timeout_seconds:
            response = await self._client.get(f"/api/v1/jobs/{job_id}", headers=self._auth())
            response.raise_for_status()
            job = response.json()
            if job["status"] in _TERMINAL_STATUSES:
                return Outcome(
                    status=job["status"],
                    duration_seconds=_duration(job),
                    detail=job.get("error_message") or "",
                )
            await asyncio.sleep(backoff)
            backoff = min(10.0, backoff * 1.5)
        return Outcome("timeout", None, f"{timeout_seconds:.0f} sn içinde bitmedi")


def _duration(job: dict[str, object]) -> float | None:
    """İşin uçtan uca süresi — sunucunun ``started_at``/``finished_at`` damgaları."""
    from datetime import datetime

    started, finished = job.get("started_at"), job.get("finished_at")
    if not isinstance(started, str) or not isinstance(finished, str):
        return None
    return (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()


async def _sample_queue_depth(
    client: httpx.AsyncClient, token: str | None, report: Report, stop: asyncio.Event
) -> None:
    """Koşu boyunca kuyruk derinliğini örnekler (ops token'ı verilmişse)."""
    if not token:
        return
    while not stop.is_set():
        try:
            response = await client.get(
                "/ops/metrics", headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                depth = int(response.json()["queue_depth"])
                report.peak_queue_depth = max(report.peak_queue_depth, depth)
        except httpx.HTTPError:
            pass  # örnekleme, testin kendisini düşürmemeli
        await asyncio.sleep(2.0)


async def run_load_test(args: argparse.Namespace) -> Report:
    report = Report(api=Latencies(), outcomes=[], peak_queue_depth=0, wall_seconds=0.0)
    payload = _synthetic_pdf(args.pages, "TenderIQ Yük Testi")
    print(
        f"Senaryo: {args.tenants} kiracı × {args.docs} doküman × {args.pages} sayfa "
        f"({len(payload) / 1024:.0f} KB/doküman) → {args.base_url}"
    )

    started = time.monotonic()
    stop = asyncio.Event()
    limits = httpx.Limits(max_connections=args.tenants * 4)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=60.0, limits=limits) as client:
        sampler = asyncio.create_task(_sample_queue_depth(client, args.ops_token, report, stop))
        runners = [
            TenantRunner(
                client,
                report,
                index=index,
                docs=args.docs,
                payload=payload,
                plan=args.plan,
            )
            for index in range(args.tenants)
        ]
        # Kurulum (kayıt/giriş) sıralı DEĞİL ama yükleme dalgasından ayrıdır:
        # kayıt uçları oran-sınırlıdır ve asıl ölçmek istediğimiz dalga, tüm
        # kiracıların AYNI ANDA yüklemeye başlamasıdır.
        await asyncio.gather(*(runner.setup() for runner in runners))
        print(f"  kurulum tamam ({time.monotonic() - started:.1f} sn) — yükleme dalgası başlıyor")

        await asyncio.gather(*(runner.run() for runner in runners))
        uploaded = sum(len(runner.job_ids) for runner in runners)
        print(f"  {uploaded} doküman kuyruğa girdi; işleme bekleniyor…")

        polls = [
            runner.poll(job_id, timeout_seconds=args.timeout)
            for runner in runners
            for job_id in runner.job_ids
        ]
        report.outcomes.extend(await asyncio.gather(*polls))
        stop.set()
        await sampler

    report.wall_seconds = time.monotonic() - started
    return report


@dataclass(frozen=True)
class Check:
    """Tek bir SLO karşılaştırması. ``ratio`` → yüzde biçimi + 'en az' yönü."""

    name: str
    actual: float | None
    target: float
    unit: str
    ratio: bool = False

    @property
    def ok(self) -> bool | None:
        if self.actual is None:
            return None
        return self.actual >= self.target if self.ratio else self.actual <= self.target

    def render(self) -> str:
        if self.actual is None:
            return f"  {self.name:<14} veri yok"
        actual = f"%{self.actual * 100:.1f}" if self.ratio else f"{self.actual:.0f} {self.unit}"
        target = f"%{self.target * 100:.0f}" if self.ratio else f"{self.target:.0f} {self.unit}"
        return (
            f"  {self.name:<14} {actual:>12}   hedef {target:<10} {'GEÇTİ' if self.ok else 'KALDI'}"
        )


def _verdict_lines(report: Report) -> tuple[list[str], bool]:
    """SLO tablosu satırları + hepsinin tuttuğu bilgisi."""
    checks = [
        Check("API p95", report.api.percentile(0.95), SLO_API_P95_MS, "ms"),
        Check(
            "İşleme p95",
            report.processing_percentile(0.95),
            SLO_JOB_TOTAL_P95_SECONDS,
            "sn",
        ),
        Check("Başarı oranı", report.success_rate, SLO_JOB_SUCCESS_RATE, "oran", ratio=True),
    ]
    # Ölçülemeyen SLO ihlal sayılmaz; koşunun kendisi başarısızsa bunu zaten
    # doküman durumları tablosu söyler.
    healthy = all(check.ok is not False for check in checks)
    return [check.render() for check in checks], healthy


def _print_report(report: Report) -> bool:
    statuses: dict[str, int] = {}
    for outcome in report.outcomes:
        statuses[outcome.status] = statuses.get(outcome.status, 0) + 1

    print("\n── Sonuç " + "─" * 50)
    print(f"  Süre: {report.wall_seconds:.0f} sn · API isteği: {len(report.api.samples)}")
    print(f"  Doküman durumları: {statuses}")
    print(f"  Tepe kuyruk derinliği: {report.peak_queue_depth}")
    if report.api.samples:
        print(
            f"  API gecikme p50/p95/max: {report.api.percentile(0.50):.0f} / "
            f"{report.api.percentile(0.95):.0f} / {max(report.api.samples):.0f} ms"
        )
    durations = [
        outcome.duration_seconds
        for outcome in report.outcomes
        if outcome.duration_seconds is not None
    ]
    if durations:
        print(
            f"  İşleme süresi medyan/p95/max: {statistics.median(durations):.0f} / "
            f"{report.processing_percentile(0.95):.0f} / {max(durations):.0f} sn"
        )

    failures = [o for o in report.outcomes if o.status not in {"review_ready", "quota"}]
    if failures:
        print("\n  Başarısız işler (ilk 5):")
        for outcome in failures[:5]:
            print(f"    - {outcome.status}: {outcome.detail[:120]}")

    print("\n── SLO " + "─" * 52)
    lines, healthy = _verdict_lines(report)
    print("\n".join(lines))
    print()
    return healthy


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TenderIQ yük/dayanıklılık testi (J.4)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API tabanı")
    parser.add_argument("--tenants", type=int, default=10, help="eşzamanlı kiracı sayısı")
    parser.add_argument("--docs", type=int, default=1, help="kiracı başına doküman")
    parser.add_argument("--pages", type=int, default=100, help="doküman başına sayfa")
    parser.add_argument(
        "--plan",
        default=None,
        choices=["pro", "enterprise"],
        help="kiracıları bu plana yükselt (ücretsiz kotayı aşan koşular için)",
    )
    parser.add_argument(
        "--timeout", type=float, default=1800.0, help="iş başına bekleme tavanı (sn)"
    )
    parser.add_argument(
        "--ops-token",
        default=None,
        help="OPS_METRICS_TOKEN — verilirse kuyruk derinliği örneklenir",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    report = asyncio.run(run_load_test(args))
    return 0 if _print_report(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
