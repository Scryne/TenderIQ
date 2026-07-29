"""Ödeme webhook'unu yerel uca imzalayıp gönderir — savunmaları sınamak için.

**Neden var.** Webhook, yetkilendirmeyi değiştiren TEK mekanizmadır (ADR-0014):
imza doğrulaması, idempotency ve sırasız-olay koruması bu ucun üstünde durur ve
üçü de birim testlerinde "çalışıyor" görünüp gerçek bir HTTP isteğinde
çalışmayabilir (başlık adı, gövde baytları, JSON'un yeniden serileştirilmesi).
Bu betik o üçünü **uçtan uca, gerçek bir istekle** sınar.

**İmza biçimi buradan gelmez.** ``tenderiq_core.billing.signature.SCHEMES``ten
okunur — yani uç ile betik aynı hesabı yapar ve iyzico'nun biçimi gerçek bir
olayla doğrulandığında düzeltilecek yer tek kalır. (Biçim şu an doğrulanmamıştır;
betik bunu her koşuda uyarı olarak yazar.)

## Kullanım

    # Bir senaryo kümesini koştur (varsayılan: hepsi)
    uv run python scripts/replay_billing_webhook.py --tenant <UUID>

    # Kaydedilmiş gerçek bir olay gövdesini tekrar oynat
    uv run python scripts/replay_billing_webhook.py --body kayit.json --tenant <UUID>

    # Tek senaryo
    uv run python scripts/replay_billing_webhook.py --tenant <UUID> --only bozuk-imza

Sır ve uç adresi ortamdan gelir (``BILLING_WEBHOOK_SECRET``, ``BILLING_PROVIDER``);
``--url`` ile taban adres değiştirilebilir.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from tenderiq_core.billing.signature import WebhookSignatureScheme, get_scheme
from tenderiq_core.config import get_settings

DEFAULT_URL = "http://localhost:8000"
WEBHOOK_PATH = "/api/v1/billing/webhook"
OPS_METRICS_PATH = "/ops/metrics"
_TIMEOUT = 15.0

# Windows konsolu varsayılan olarak cp1254'tür; Türkçe metin ve işaretler
# `UnicodeEncodeError` ile betiği ÇÖKERTİR — yani sınama sonucu hiç görünmez.
# Çıktı kodlaması burada sabitlenir (bu betiğin koştuğu yer bir geliştirici
# makinesidir, CI değil).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class Outcome:
    """Bir senaryonun sonucu."""

    name: str
    expectation: str
    passed: bool
    detail: str


@dataclass
class Scenario:
    """Tek bir uçtan uca sınama.

    ``run`` bir ``Sender`` alır ve sonucu döndürür; her senaryo NE beklediğini
    ve NEDEN önemli olduğunu kendi metninde taşır — çıktıyı okuyanın koda
    bakması gerekmesin.
    """

    name: str
    why: str
    run: Callable[[Sender], Outcome]


class Sender:
    """İmzalayıp gönderen istemci.

    Gövde **bir kez** baytlara çevrilir ve imza O baytlar üzerinden hesaplanır;
    aynı sözlüğü iki kez ``json.dumps`` etmek (biri imza, biri gönderim için)
    anahtar sırası ya da boşluk farkında sessizce geçersiz imza üretir — bu,
    gerçek entegrasyonlarda en sık görülen webhook hatasıdır.
    """

    def __init__(self, *, base_url: str, secret: str, scheme: WebhookSignatureScheme) -> None:
        self._url = base_url.rstrip("/") + WEBHOOK_PATH
        self.ops_metrics_url = base_url.rstrip("/") + OPS_METRICS_PATH
        self._secret = secret
        self._scheme = scheme
        self.sent: list[tuple[bytes, dict[str, str]]] = []

    def post(self, payload: dict[str, Any], *, corrupt_signature: bool = False) -> httpx.Response:
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        signature = self._scheme.compute(secret=self._secret, raw_body=raw)
        if corrupt_signature:
            # Sırf son karakteri değiştirmek yeterli ve doğru testtir: imza
            # DOĞRU uzunlukta ve doğru alfabede olduğu hâlde eşleşmemelidir.
            # Tamamen çöp bir dize, uzunluk kontrolüne takılıp asıl karşılaştırmayı
            # hiç sınamayabilirdi.
            signature = signature[:-1] + ("0" if signature[-1] != "0" else "1")
        headers = {self._scheme.header: signature, "content-type": "application/json"}
        self.sent.append((raw, headers))
        return httpx.post(self._url, content=raw, headers=headers, timeout=_TIMEOUT)

    def post_raw(self, raw: bytes, headers: dict[str, str]) -> httpx.Response:
        """Baytları OLDUĞU GİBİ tekrar gönderir (gerçek bir yeniden teslim)."""
        return httpx.post(self._url, content=raw, headers=headers, timeout=_TIMEOUT)


# ── Olay gövdeleri ───────────────────────────────────────────────────────────


def _event(
    tenant: uuid.UUID,
    *,
    event_type: str = "subscription.activated",
    plan: str = "pro",
    status: str = "active",
    occurred_at: datetime | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Bir olay gövdesi üretir.

    ``event_id`` her çağrıda benzersizdir: dedup anahtarı Redis'te 90 gün
    kalıcıdır, sabit bir kimlik kullanılırsa ikinci koşu "duplicate" alır ve
    betik yanlış şeyi ölçtüğünü fark etmez.
    """
    body: dict[str, Any] = {
        "event_id": event_id or f"replay_{uuid.uuid4()}",
        "event_type": event_type,
        "tenant_id": str(tenant),
        "plan": plan,
        "status": status,
    }
    if occurred_at is not None:
        body["occurred_at"] = occurred_at.isoformat()
    return body


def _status_of(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code} (JSON değil)"
    return str(body.get("status") or body.get("error", {}).get("code") or body)


# ── Senaryolar ───────────────────────────────────────────────────────────────


def _scenario_valid(tenant: uuid.UUID) -> Scenario:
    def run(sender: Sender) -> Outcome:
        response = sender.post(_event(tenant, occurred_at=datetime.now(UTC)))
        ok = response.status_code == 200 and _status_of(response) == "applied"
        return Outcome(
            "gecerli-imza",
            "200 + applied",
            ok,
            f"HTTP {response.status_code} · {_status_of(response)}",
        )

    return Scenario(
        "gecerli-imza",
        "Taban çizgi: doğru imzalı yeni bir olay UYGULANMALI. Bu geçmezse "
        "diğer senaryoların 'reddedildi' sonucu hiçbir şey kanıtlamaz.",
        run,
    )


def _scenario_bad_signature(tenant: uuid.UUID) -> Scenario:
    def run(sender: Sender) -> Outcome:
        response = sender.post(_event(tenant), corrupt_signature=True)
        ok = response.status_code == 400
        return Outcome(
            "bozuk-imza",
            "400 (uygulanmamalı)",
            ok,
            f"HTTP {response.status_code} · {_status_of(response)}",
        )

    return Scenario(
        "bozuk-imza",
        "Tek karakteri değişmiş imza reddedilmeli. Geçerse, gövdeyi uyduran "
        "herkes istediği kiracıyı istediği plana yükseltebilir.",
        run,
    )


def _scenario_no_signature(tenant: uuid.UUID) -> Scenario:
    def run(sender: Sender) -> Outcome:
        raw = json.dumps(_event(tenant), separators=(",", ":")).encode()
        response = sender.post_raw(raw, {"content-type": "application/json"})
        ok = response.status_code == 400
        return Outcome(
            "imzasiz",
            "400 (uygulanmamalı)",
            ok,
            f"HTTP {response.status_code} · {_status_of(response)}",
        )

    return Scenario(
        "imzasiz",
        "İmza başlığı HİÇ yoksa da reddedilmeli — boş imza 'boş beklenen' ile eşleşip geçmemeli.",
        run,
    )


def _scenario_replay(tenant: uuid.UUID) -> Scenario:
    def run(sender: Sender) -> Outcome:
        payload = _event(tenant, occurred_at=datetime.now(UTC))
        first = sender.post(payload)
        raw, headers = sender.sent[-1]
        # AYNI baytlar, AYNI imza: sağlayıcının yeniden denemesinin birebir eşi.
        second = sender.post_raw(raw, headers)
        ok = _status_of(first) == "applied" and _status_of(second) == "duplicate"
        return Outcome(
            "tekrar-gonderim",
            "1. applied, 2. duplicate",
            ok,
            f"{_status_of(first)} → {_status_of(second)}",
        )

    return Scenario(
        "tekrar-gonderim",
        "Sağlayıcılar yanıtı alamadıklarında AYNI olayı tekrar gönderir. "
        "İkinci teslim durumu yeniden uygulamamalı (idempotency).",
        run,
    )


def _scenario_out_of_order(tenant: uuid.UUID) -> Scenario:
    def run(sender: Sender) -> Outcome:
        now = datetime.now(UTC)
        # Önce YENİ olay (yeniden etkinleşme), sonra ESKİ olay (iptal).
        fresh = sender.post(_event(tenant, event_type="subscription.activated", occurred_at=now))
        stale = sender.post(
            _event(
                tenant,
                event_type="subscription.canceled",
                occurred_at=now - timedelta(hours=6),
            )
        )
        ok = _status_of(fresh) == "applied" and _status_of(stale) == "stale"
        return Outcome(
            "sirasiz-damga",
            "yeni applied, eski stale",
            ok,
            f"{_status_of(fresh)} → {_status_of(stale)}",
        )

    return Scenario(
        "sirasiz-damga",
        "Webhook'lar sıra garantisi VERMEZ. Geç gelen eski bir 'iptal edildi', "
        "sonradan gelmiş 'yeniden etkinleşti'yi ezerse müşterinin ÖDEDİĞİ erişim "
        "sessizce kapanır. Eski olay yok sayılmalı.",
        run,
    )


def _scenario_unsigned_field_tamper(tenant: uuid.UUID) -> Scenario:
    def run(sender: Sender) -> Outcome:
        payload = _event(tenant, plan="pro", occurred_at=datetime.now(UTC))
        sender.post(payload)
        raw, headers = sender.sent[-1]
        # İmza aynı kalırken gövdedeki planı yükselt: klasik kurcalama.
        tampered = raw.replace(b'"plan":"pro"', b'"plan":"enterprise"')
        response = sender.post_raw(tampered, headers)
        ok = response.status_code == 400
        return Outcome(
            "govde-kurcalama",
            "400 (uygulanmamalı)",
            ok,
            f"HTTP {response.status_code} · {_status_of(response)}",
        )

    return Scenario(
        "govde-kurcalama",
        "Geçerli bir imza yakalanıp gövde değiştirilirse reddedilmeli — imza "
        "gövdenin TAMAMINI kapsamalı, yalnız bir kısmını değil.",
        run,
    )


def _scenario_unknown_tenant() -> Scenario:
    def run(sender: Sender) -> Outcome:
        response = sender.post(_event(uuid.uuid4(), occurred_at=datetime.now(UTC)))
        # Var olmayan kiracı: uç ya reddetmeli ya da o kiracıya yazmalı —
        # ASLA başka bir kiracıya değil. 5xx ise uç kendini savunamıyor demektir.
        ok = response.status_code < 500
        return Outcome(
            "bilinmeyen-kiraci",
            "5xx OLMAMALI",
            ok,
            f"HTTP {response.status_code} · {_status_of(response)}",
        )

    return Scenario(
        "bilinmeyen-kiraci",
        "İmzalı ama var olmayan bir kiracı taşıyan olay ucu çökertmemeli; "
        "500 dönen bir uç sağlayıcının yeniden deneme fırtınasını tetikler.",
        run,
    )


def _scenario_permanent_dead_letters(ops_token: str | None) -> Scenario:
    """Kalıcı hatanın GERÇEKTEN kuyruğa düştüğünü doğrular.

    Uç 400 dönebilir ve olay yine de kaybolmuş olabilir; ikisi ayrı şeylerdir ve
    yalnız yanıt koduna bakan bir sınama tam olarak bu farkı gözden kaçırır.

    Doğrulama **operatör metriğinden** yapılır, kiracı listesinden değil: kalıcı
    hataların çoğu (tanınmayan kiracı, ayrıştırılamayan gövde) tanımı gereği bir
    kiracıya ATFEDİLEMEZ ve hiçbir kiracının listesinde görünmez — atfedemediğimiz
    bir ödemeyi rastgele birine göstermek sızıntı olurdu.
    """

    def _pending(url: str) -> int | None:
        if ops_token is None:
            return None
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {ops_token}"},
            timeout=_TIMEOUT,
        )
        if response.status_code != 200:
            return None
        value = response.json().get("dead_letter_pending")
        return int(value) if isinstance(value, int) else None

    def run(sender: Sender) -> Outcome:
        before = _pending(sender.ops_metrics_url)
        response = sender.post(_event(uuid.uuid4(), occurred_at=datetime.now(UTC)))
        rejected = response.status_code == 400
        after = _pending(sender.ops_metrics_url)

        if before is None or after is None:
            return Outcome(
                "kalici-hata-kuyruga",
                "400 (kuyruk doğrulaması için --ops-token verin)",
                rejected,
                f"HTTP {response.status_code} · kuyruk KONTROL EDİLMEDİ",
            )
        grew = after > before
        return Outcome(
            "kalici-hata-kuyruga",
            "400 + kuyruk büyüdü",
            rejected and grew,
            f"HTTP {response.status_code} · kuyruk {before} → {after}",
        )

    return Scenario(
        "kalici-hata-kuyruga",
        "Kalıcı hata yalnız reddedilmemeli, KAYDEDİLMELİ. Reddedilip "
        "kaydedilmeyen olay sessizce kaybolur; müşteri ödemiştir ve elimizde "
        "yeniden uygulayacak hiçbir şey kalmaz.",
        run,
    )


def build_scenarios(tenant: uuid.UUID, ops_token: str | None = None) -> list[Scenario]:
    return [
        _scenario_valid(tenant),
        _scenario_bad_signature(tenant),
        _scenario_no_signature(tenant),
        _scenario_unsigned_field_tamper(tenant),
        _scenario_replay(tenant),
        _scenario_out_of_order(tenant),
        _scenario_unknown_tenant(),
        _scenario_permanent_dead_letters(ops_token),
    ]


# ── Kaydedilmiş gövde ────────────────────────────────────────────────────────


def replay_recorded(sender: Sender, path: Path) -> Outcome:
    """Kaydedilmiş bir olay gövdesini imzalayıp gönderir.

    Gerçek bir sağlayıcı olayı ele geçtiğinde kullanılacak yol budur: gövde
    dosyaya konur, buradan tekrar oynatılır ve ayrıştırıcının onu GERÇEKTEN
    anladığı görülür.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    response = sender.post(payload)
    ok = response.status_code == 200
    return Outcome(
        f"kayit:{path.name}",
        "200",
        ok,
        f"HTTP {response.status_code} · {_status_of(response)}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help=f"API tabanı (varsayılan {DEFAULT_URL})")
    parser.add_argument("--tenant", help="Olayların yazılacağı kiracı kimliği (UUID)")
    parser.add_argument("--body", type=Path, help="Kaydedilmiş olay gövdesi (JSON)")
    parser.add_argument("--only", help="Yalnız bu senaryoyu koştur")
    parser.add_argument(
        "--ops-token",
        help="OPS_METRICS_TOKEN — kalıcı hatanın kuyruğa düştüğünü doğrulamak için",
    )
    parser.add_argument("--provider", help="İmza biçimi (varsayılan: BILLING_PROVIDER)")
    parser.add_argument("--secret", help="Webhook sırrı (varsayılan: BILLING_WEBHOOK_SECRET)")
    args = parser.parse_args()

    settings = get_settings()
    provider = args.provider or settings.billing_provider
    secret = args.secret or settings.billing_webhook_secret
    if not secret:
        print("HATA: webhook sırrı yok (BILLING_WEBHOOK_SECRET ya da --secret).")
        return 2

    try:
        scheme = get_scheme(provider)
    except KeyError as exc:
        print(f"HATA: {exc}")
        return 2

    print(f"Uç       : {args.url}{WEBHOOK_PATH}")
    print(f"Sağlayıcı: {provider}")
    print(f"İmza     : {scheme.header} · {scheme.encoding}")
    if not scheme.verified:
        print(
            "  ⚠ Bu imza biçimi GERÇEK bir olaya karşı DOĞRULANMADI "
            "(dokümantasyondan). Gerçek olay geldiğinde "
            "packages/core/src/tenderiq_core/billing/signature.py düzeltilmeli."
        )
    print()

    sender = Sender(base_url=args.url, secret=secret, scheme=scheme)
    outcomes: list[Outcome] = []

    if args.body is not None:
        outcomes.append(replay_recorded(sender, args.body))
    else:
        if not args.tenant:
            print("HATA: --tenant zorunlu (ya da --body verin).")
            return 2
        tenant = uuid.UUID(args.tenant)
        scenarios = build_scenarios(tenant, args.ops_token)
        if args.only:
            scenarios = [s for s in scenarios if s.name == args.only]
            if not scenarios:
                print(f"HATA: '{args.only}' diye bir senaryo yok.")
                return 2
        for scenario in scenarios:
            outcome = scenario.run(sender)
            outcomes.append(outcome)
            mark = "✅" if outcome.passed else "❌"
            print(f"{mark} {outcome.name}")
            print(f"     beklenen: {outcome.expectation}")
            print(f"     gerçek  : {outcome.detail}")
            if not outcome.passed:
                print(f"     NEDEN ÖNEMLİ: {scenario.why}")
            print()

    failed = [o for o in outcomes if not o.passed]
    print(f"{'❌' if failed else '✅'} {len(outcomes)} senaryo · {len(failed)} başarısız")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
