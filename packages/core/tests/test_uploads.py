"""Yükleme doğrulama birim testleri: allowlist + magic-bytes."""

from __future__ import annotations

import pytest

from tenderiq_core.uploads import (
    is_allowed_content_type,
    matches_magic_bytes,
    normalize_content_type,
)

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.parametrize(
    "content_type",
    ["application/pdf", "APPLICATION/PDF", "application/pdf; charset=utf-8", DOCX, XLSX],
)
def test_izinli_turler(content_type: str) -> None:
    assert is_allowed_content_type(content_type)


@pytest.mark.parametrize(
    "content_type",
    ["text/html", "application/zip", "image/png", "application/x-msdownload", ""],
)
def test_izinsiz_turler(content_type: str) -> None:
    assert not is_allowed_content_type(content_type)


def test_normalize_parametreleri_atar() -> None:
    assert normalize_content_type(" Application/PDF ; charset=x") == "application/pdf"


@pytest.mark.parametrize(
    ("content_type", "head", "expected"),
    [
        ("application/pdf", b"%PDF-1.7\n", True),
        ("application/pdf", b"PK\x03\x04...", False),  # tür sahteciliği: zip'i pdf diye beyan
        (DOCX, b"PK\x03\x04abcd", True),
        (XLSX, b"PK\x03\x04abcd", True),
        (DOCX, b"%PDF-1.7\n", False),
        ("application/pdf", b"", False),
        ("text/html", b"<html>", False),  # allowlist dışı tür asla eşleşmez
    ],
)
def test_magic_bytes(content_type: str, head: bytes, expected: bool) -> None:
    assert matches_magic_bytes(content_type, head) is expected
