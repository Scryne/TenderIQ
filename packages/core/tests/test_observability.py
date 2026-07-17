"""Sentry entegrasyonu birim testleri — DSN kapısı + PII maskeleme (C.6)."""

from __future__ import annotations

from tenderiq_core.config import Settings
from tenderiq_core.observability import bind_sentry_tags, init_sentry, scrub_event


def test_dsn_yoksa_init_noop() -> None:
    assert init_sentry(Settings(sentry_dsn=None)) is False
    assert init_sentry(Settings(sentry_dsn="")) is False


def test_bind_tags_sentry_baslatilmamisken_guvenli() -> None:
    # İstemci yokken set_tag sessiz no-op'tur; istisna fırlamamalı.
    bind_sentry_tags(tenant_id="t-1", job_id=None)


def test_scrub_istek_pii_alanlarini_temizler() -> None:
    event = {
        "request": {
            "url": "https://api.tenderiq.app/api/v1/tenders?token=gizli",
            "method": "POST",
            "query_string": "token=gizli",
            "cookies": {"tiq_session": "jwt-degeri"},
            "data": {"password": "cok-gizli"},
            "env": {"REMOTE_ADDR": "1.2.3.4"},
            "headers": {
                "Authorization": "Bearer jwt-degeri",
                "Cookie": "tiq_session=jwt-degeri",
                "X-Forwarded-For": "1.2.3.4",
                "User-Agent": "test-agent",
                "Content-Type": "application/json",
            },
        }
    }
    scrubbed = scrub_event(event)
    request = scrubbed["request"]
    assert request["url"] == "https://api.tenderiq.app/api/v1/tenders"  # sorgu dizesi gitti
    for gone in ("cookies", "data", "env", "query_string"):
        assert gone not in request
    assert set(request["headers"]) == {"User-Agent", "Content-Type"}


def test_scrub_kullaniciyi_yalnizca_id_ile_birakir() -> None:
    event = {"user": {"id": "u-1", "email": "kisi@ornek.com", "ip_address": "1.2.3.4"}}
    assert scrub_event(event)["user"] == {"id": "u-1"}
    assert scrub_event({"user": {"email": "kisi@ornek.com"}})["user"] == {}


def test_scrub_istek_olmayan_olaya_dokunmaz() -> None:
    event = {"message": "bir hata", "level": "error"}
    assert scrub_event(event) == event
