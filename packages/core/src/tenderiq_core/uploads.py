"""Yükleme doğrulama kuralları: içerik türü allowlist + magic-bytes kontrolü.

İçerik türü sahteciliğine karşı iki katman (Sprint 1.1 güvenlik):
kayıt anında allowlist, tamamlama anında nesnenin ilk baytları (magic bytes).
"""

from __future__ import annotations

# İzinli içerik türü → kabul edilen magic-bytes ön-ekleri.
# DOCX/XLSX birer ZIP konteyneridir (``PK\x03\x04``).
ALLOWED_CONTENT_TYPES: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF-",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK\x03\x04",),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (b"PK\x03\x04",),
}

# Magic-bytes kontrolü için nesnenin başından okunacak bayt sayısı.
MAGIC_PROBE_LENGTH = 8


def is_allowed_content_type(content_type: str) -> bool:
    """İçerik türü allowlist'te mi (parametreler — ``;charset=`` vb. — yok sayılır)."""
    return normalize_content_type(content_type) in ALLOWED_CONTENT_TYPES


def normalize_content_type(content_type: str) -> str:
    """``type/subtype`` kısmını küçük harfe indirger, parametreleri atar."""
    return content_type.split(";", 1)[0].strip().lower()


def matches_magic_bytes(content_type: str, head: bytes) -> bool:
    """Nesnenin ilk baytları, beyan edilen içerik türünün imzasıyla uyuşuyor mu."""
    signatures = ALLOWED_CONTENT_TYPES.get(normalize_content_type(content_type))
    if signatures is None:
        return False
    return any(head.startswith(signature) for signature in signatures)
