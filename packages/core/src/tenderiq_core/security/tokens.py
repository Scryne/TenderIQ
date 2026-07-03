"""JWT erişim token'ları (HS256)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pydantic import BaseModel

ALGORITHM = "HS256"
DEFAULT_EXPIRE_HOURS = 12


class TokenPayload(BaseModel):
    """Erişim token'ının çözülmüş içeriği."""

    sub: str  # user id
    tenant_id: str  # aktif organizasyon (tenant) id
    role: str  # RBAC rolü
    exp: int  # sona erme (unix epoch)


def create_access_token(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    secret: str,
    expires_in_hours: int = DEFAULT_EXPIRE_HOURS,
) -> str:
    """İmzalı bir JWT erişim token'ı üretir."""
    now = datetime.now(UTC)
    exp = now + timedelta(hours=expires_in_hours)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> TokenPayload:
    """JWT'yi doğrular ve içeriğini döndürür (geçersizse ``jwt`` istisnası)."""
    data = jwt.decode(token, secret, algorithms=[ALGORITHM])
    return TokenPayload.model_validate(data)
