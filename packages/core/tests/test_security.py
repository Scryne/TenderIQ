"""Güvenlik yardımcıları birim testleri (DB gerektirmez)."""

from __future__ import annotations

import uuid

import jwt
import pytest

from tenderiq_core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# HS256 için ≥32 bayt (RFC 7518 §3.2) — kısa anahtar PyJWT uyarısı üretir.
_SECRET = "s3cret-test-anahtari-0123456789abcdef"
_WRONG_SECRET = "yanlis-test-anahtari-0123456789abcdef"


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("parola-123456")
    assert hashed != "parola-123456"
    assert verify_password("parola-123456", hashed)
    assert not verify_password("yanlis-parola", hashed)


def test_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="admin", secret=_SECRET)
    payload = decode_access_token(token, _SECRET)
    assert payload.sub == str(user_id)
    assert payload.tenant_id == str(tenant_id)
    assert payload.role == "admin"


def test_token_rejects_wrong_secret() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role="member", secret=_SECRET
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, _WRONG_SECRET)


def test_token_rejects_schema_mismatch() -> None:
    """İmzası geçerli ama şeması eksik token (ör. tenant_id yok) PyJWTError'a eşlenir.

    Regresyon: pydantic ValidationError sarılmazsa get_principal 401 yerine 500 dönerdi.
    """
    import time

    stray = jwt.encode({"sub": "x", "exp": int(time.time()) + 60}, _SECRET, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(stray, _SECRET)


def test_token_requires_exp_claim() -> None:
    """`exp` içermeyen token reddedilir (süresiz token yasak)."""
    eternal = jwt.encode(
        {"sub": "x", "tenant_id": "y", "role": "admin"}, _SECRET, algorithm="HS256"
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(eternal, _SECRET)


def test_access_token_kisa_omurlu() -> None:
    """Erişim token'ı dakika-tabanlı kısa ömürle üretilir (J.2 madde 4; ≤1 saat)."""
    import time

    token = create_access_token(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        role="admin",
        secret=_SECRET,
        expires_in_minutes=30,
    )
    payload = decode_access_token(token, _SECRET)
    remaining = payload.exp - int(time.time())
    # ~30 dk (üretim/çözme gecikmesi için ±60 sn tolerans).
    assert 30 * 60 - 60 <= remaining <= 30 * 60 + 60
