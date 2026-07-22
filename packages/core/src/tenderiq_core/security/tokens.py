"""JWT erişim token'ları (HS256)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pydantic import BaseModel, ValidationError

ALGORITHM = "HS256"
DEFAULT_EXPIRE_MINUTES = 60  # kısa ömür (J.2): oturum refresh token ile sürdürülür


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
    expires_in_minutes: int = DEFAULT_EXPIRE_MINUTES,
) -> str:
    """İmzalı bir JWT erişim token'ı üretir (kısa ömürlü; bkz. DEFAULT_EXPIRE_MINUTES)."""
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=expires_in_minutes)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> TokenPayload:
    """JWT'yi doğrular ve içeriğini döndürür (geçersizse ``jwt`` istisnası).

    İmzası geçerli ama şeması beklenenden farklı token'lar da (ör. eksik
    ``tenant_id``) ``jwt.InvalidTokenError``'a eşlenir; çağıran tek tip
    ``PyJWTError`` yakalayarak 401 dönebilir.
    """
    data = jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["exp"]})
    try:
        return TokenPayload.model_validate(data)
    except ValidationError as exc:
        raise jwt.InvalidTokenError("Token içeriği beklenen şemaya uymuyor.") from exc
