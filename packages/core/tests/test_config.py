"""Settings/config regresyon testleri."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tenderiq_core.config import Settings


def test_cors_origins_parses_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Virgülle ayrılmış `CORS_ORIGINS` env'den liste olarak okunur.

    Regresyon: pydantic-settings, `list[str]` alanını env'den önce JSON olarak
    çözmeye çalışıyordu; `.env`'deki `CORS_ORIGINS=http://localhost:3000` düz
    string'inde `get_settings()` çöküyordu. `NoDecode` + `_split_cors_origins`
    ile giderildi (config.py).
    """
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://app.tenderiq.co")
    settings = Settings(_env_file=None)  # gerçek .env'i yükleme, yalnızca env'i oku
    assert settings.cors_origins == ["http://localhost:3000", "https://app.tenderiq.co"]


def test_cors_origins_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env'de tanımlı değilse varsayılan tek-elemanlı liste kullanılır."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://localhost:3000"]


def test_parsing_ocr_languages_parses_comma_separated_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`PARSING_OCR_LANGUAGES=tr, en ,de` → ["tr", "en", "de"] (CSV, JSON değil)."""
    monkeypatch.setenv("PARSING_OCR_LANGUAGES", "tr, en ,de")
    settings = Settings(_env_file=None)
    assert settings.parsing_ocr_languages == ["tr", "en", "de"]


def test_parsing_ocr_languages_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PARSING_OCR_LANGUAGES", raising=False)
    settings = Settings(_env_file=None)
    assert settings.parsing_ocr_languages == ["tr", "en"]


def test_production_requires_strong_auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production, AUTH_SECRET eksik ya da kısayken açılışı reddeder (fail-fast)."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(ValidationError, match="AUTH_SECRET"):
        Settings(_env_file=None)

    monkeypatch.setenv("AUTH_SECRET", "kisa-sir")
    with pytest.raises(ValidationError, match="AUTH_SECRET"):
        Settings(_env_file=None)


def test_production_rejects_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production'da DEBUG=true açılışı engeller."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("DEBUG", "true")
    with pytest.raises(ValidationError, match="DEBUG"):
        Settings(_env_file=None)


def test_production_boots_with_hardened_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sertleştirilmiş ayarlarla production açılışı sorunsuz."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("DEBUG", "false")
    settings = Settings(_env_file=None)
    assert settings.is_production
