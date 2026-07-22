"""user_account.email_verified kolonu (Sprint 3.3-D — e-posta dogrulama)

Kayitta False; dogrulama baglantisiyla True olur. Giris bloke edilmez (yalniz
gosterim/isaret); mevcut hesaplar False baslar. user_account RLS'siz kimlik
tablosudur (politika gerekmez).

Revision ID: 0011_email_verified
Revises: 0010_billing
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_email_verified"
down_revision: str | None = "0010_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_account",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_account", "email_verified")
