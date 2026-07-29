"""E-posta seam'i: sağlayıcılar, şablonlar, bastırma ve tekrar koruması."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tenderiq_core.config import Settings
from tenderiq_core.email import (
    EmailDeliveryError,
    EmailKind,
    EmailOutcome,
    MemoryEmailProvider,
    ResendEmailProvider,
    create_email_provider,
    send_email,
)
from tenderiq_core.email import templates as tpl

SETTINGS = Settings(_env_file=None, email_from="no-reply@tenderiq.local")


# ── Şablonlar ────────────────────────────────────────────────────────────────


def test_sablonlar_baglantiyi_duz_metinde_de_verir() -> None:
    """HTML engellenebilir; bağlantı düz metinde de tam yazılmalı."""
    link = "https://app.tenderiq.local/verify-email?token=abc"

    message = tpl.verify_email(to="a@b.com", link=link)

    assert link in message.text
    assert link in message.html
    assert message.kind is EmailKind.VERIFY_EMAIL


def test_sablonlar_html_kacisi_yapar() -> None:
    """Kuruluş adı kullanıcı girdisidir; şablona ham enjekte edilemez."""
    message = tpl.invitation(
        to="a@b.com", link="https://x/y", organization="<script>alert(1)</script>"
    )

    assert "<script>" not in message.html
    assert "&lt;script&gt;" in message.html


def test_odeme_sablonlari_olay_bazli_tekrar_anahtari_tasir() -> None:
    """Webhook mükerrer teslim eder; kullanıcı iki kez 'ödemeniz alındı' almamalı."""
    message = tpl.payment_succeeded(
        to="a@b.com",
        plan="Pro",
        amount_text="₺1.500",
        period_end_text="29.08.2026",
        event_id="evt1",
    )

    assert message.idempotency_key == "payment_succeeded:evt1"


def test_son_deneme_metni_askiya_almayi_soyler() -> None:
    son = tpl.payment_failed(
        to="a@b.com", plan="Pro", attempt=3, max_attempts=3, link="https://x", event_id="e"
    )
    ilk = tpl.payment_failed(
        to="a@b.com", plan="Pro", attempt=1, max_attempts=3, link="https://x", event_id="e"
    )

    assert "askıya alınacak" in son.text
    assert "Yeniden deneyeceğiz" in ilk.text


# ── Sağlayıcı fabrikası ──────────────────────────────────────────────────────


def test_resend_anahtarsiz_kurulamaz() -> None:
    settings = Settings(_env_file=None, email_provider="resend", resend_api_key=None)

    with pytest.raises(EmailDeliveryError, match="RESEND_API_KEY"):
        create_email_provider(settings)


def test_taninmayan_saglayici_reddedilir() -> None:
    with pytest.raises(EmailDeliveryError, match="Tanınmayan"):
        create_email_provider(Settings(_env_file=None, email_provider="postmark"))


# ── Resend adaptörü ──────────────────────────────────────────────────────────


async def test_resend_basarili_gonderimde_kimlik_dondurur() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = request.content
        return httpx.Response(200, json={"id": "re_123"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ResendEmailProvider("gizli-anahtar", client=client)
        identifier = await provider.send(
            tpl.verify_email(to="a@b.com", link="https://x"), sender="no-reply@x"
        )

    assert identifier == "re_123"
    assert captured["auth"] == "Bearer gizli-anahtar"


async def test_resend_hata_durumunu_teslim_hatasina_cevirir() -> None:
    transport = httpx.MockTransport(lambda _r: httpx.Response(422, text="invalid from"))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ResendEmailProvider("k", client=client)

        with pytest.raises(EmailDeliveryError, match="422"):
            await provider.send(tpl.verify_email(to="a@b.com", link="https://x"), sender="x@y")


async def test_resend_anahtari_hata_mesajina_sizmaz() -> None:
    """Anahtar log'a veya istisna metnine düşerse sır repoda olmasa da sızar."""
    transport = httpx.MockTransport(lambda _r: httpx.Response(500, text="boom"))
    async with httpx.AsyncClient(transport=transport) as client:
        provider = ResendEmailProvider("cok-gizli-anahtar", client=client)

        with pytest.raises(EmailDeliveryError) as exc:
            await provider.send(tpl.verify_email(to="a@b.com", link="https://x"), sender="x@y")

    assert "cok-gizli-anahtar" not in str(exc.value)


# ── Servis kuralları ─────────────────────────────────────────────────────────


class _FakeRedis:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.keys:
            return False
        self.keys.add(key)
        return True


async def test_tekrar_korumasi_ikinci_gonderimi_engeller() -> None:
    provider = MemoryEmailProvider()
    redis: Any = _FakeRedis()
    message = tpl.payment_succeeded(
        to="a@b.com", plan="Pro", amount_text="₺1", period_end_text="x", event_id="evt9"
    )

    first = await send_email(message, provider=provider, settings=SETTINGS, redis=redis)
    second = await send_email(message, provider=provider, settings=SETTINGS, redis=redis)

    assert first is EmailOutcome.SENT
    assert second is EmailOutcome.DUPLICATE
    assert len(provider.sent) == 1


async def test_saglayici_hatasi_cagirani_dusurmez() -> None:
    """Kayıt/davet akışları e-postaya bağlı değildir; hata loglanır ve geçilir."""
    provider = MemoryEmailProvider(fail_with=EmailDeliveryError("kesinti"))

    outcome = await send_email(
        tpl.verify_email(to="a@b.com", link="https://x"), provider=provider, settings=SETTINGS
    )

    assert outcome is EmailOutcome.FAILED


async def test_raise_on_error_ile_hata_yukselir() -> None:
    provider = MemoryEmailProvider(fail_with=EmailDeliveryError("kesinti"))

    with pytest.raises(EmailDeliveryError):
        await send_email(
            tpl.verify_email(to="a@b.com", link="https://x"),
            provider=provider,
            settings=SETTINGS,
            raise_on_error=True,
        )


def test_guvenlik_kritik_turler_bastirmayi_asar() -> None:
    """Bounce kaydı yüzünden kullanıcıyı hesabından kilitlemek daha ağır bir zarardır."""
    from tenderiq_core.email import SUPPRESSION_BYPASS_KINDS

    assert EmailKind.PASSWORD_RESET in SUPPRESSION_BYPASS_KINDS
    assert EmailKind.VERIFY_EMAIL in SUPPRESSION_BYPASS_KINDS
    assert EmailKind.PAYMENT_SUCCEEDED not in SUPPRESSION_BYPASS_KINDS
