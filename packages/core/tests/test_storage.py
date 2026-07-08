"""Depolama yardımcıları birim testleri (ağ/DB gerektirmez)."""

from __future__ import annotations

from tenderiq_core.storage import safe_key_component


def test_safe_key_component_strips_path_segments() -> None:
    """İstemciden gelen yol ayraçları anahtara sızmaz (`a/../b.pdf` → `b.pdf`)."""
    assert safe_key_component("../../etc/passwd") == "passwd"
    assert safe_key_component("klasor\\alt\\sartname.pdf") == "sartname.pdf"


def test_safe_key_component_preserves_turkish_and_common_chars() -> None:
    assert safe_key_component("İdari Şartname v2 (son).pdf") == "İdari Şartname v2 (son).pdf"


def test_safe_key_component_replaces_specials_and_handles_empty() -> None:
    assert safe_key_component("a:b*c?.pdf") == "a_b_c_.pdf"
    assert safe_key_component("...") == "dosya"
    assert safe_key_component("") == "dosya"


def test_safe_key_component_truncates_long_names() -> None:
    assert len(safe_key_component("x" * 1000)) == 255
