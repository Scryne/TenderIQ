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


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("parola-123456")
    assert hashed != "parola-123456"
    assert verify_password("parola-123456", hashed)
    assert not verify_password("yanlis-parola", hashed)


def test_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="admin", secret="s3cret")
    payload = decode_access_token(token, "s3cret")
    assert payload.sub == str(user_id)
    assert payload.tenant_id == str(tenant_id)
    assert payload.role == "admin"


def test_token_rejects_wrong_secret() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role="member", secret="dogru"
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, "yanlis")
