"""e-posta adreslerini kanonik (kucuk harf) bicime tasir

Uygulama katmani artik e-postayi her zaman normalize ederek saklar/arar
(``services.auth.normalize_email``). Bu migration mevcut satirlari ayni bicime
getirir; aksi hâlde kayit sirasindaki ham deger ile arama sirasindaki normalize
deger eslesmez (parola sifirlama sessizce hiç calismazdi).

``uq_user_account_email`` kisiti buyuk/kucuk harfe DUYARLI oldugundan, veride
yalnizca harf durumuyla ayrisan iki hesap varsa (``A@x.com`` + ``a@x.com``)
normalize etmek kisiti ihlal ederdi. Bu durum otomatik cozulemez (hangi hesabin
kalacagi bir urun/veri karari); migration once tespit edip anlasilir bir hata
ile durur.

Revision ID: 0013_normalize_email
Revises: 0012_invitation
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_normalize_email"
down_revision: str | None = "0012_invitation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    collisions = connection.execute(
        sa.text(
            "SELECT lower(email) AS normalized, count(*) AS total "
            "FROM user_account GROUP BY lower(email) HAVING count(*) > 1"
        )
    ).all()
    if collisions:
        listed = ", ".join(f"{row.normalized} ({row.total} hesap)" for row in collisions)
        raise RuntimeError(
            "Yalnizca harf durumuyla ayrisan hesaplar var; normalize etmek "
            f"uq_user_account_email kisitini ihlal eder: {listed}. "
            "Bu hesaplari elle birlestirin/silin, sonra migration'i tekrar calistirin."
        )

    normalize = "SET email = lower(btrim(email)) WHERE email <> lower(btrim(email))"
    op.execute(f"UPDATE user_account {normalize}")
    # invitation.email zaten normalize yaziliyor; eski/elle girilmis satirlar icin savunmaci.
    op.execute(f"UPDATE invitation {normalize}")


def downgrade() -> None:
    # Orijinal harf durumu kaybolmustur; geri alinamaz (veri kaybi degil, bicim degisimi).
    pass
