"""bekleme listesi (SIGNUP_MODE=waitlist)

Kayitlarin kapali oldugu donemde alinan ilgi bildirimleri. Kiraciya ait
DEGILDIR (henuz kiraci yoktur), bu yuzden RLS'ye tabi degildir; `organization`
gibi kiraci-kok tablolarla ayni siniftadir.

E-posta benzersizdir: ayni adres iki kez siraya girmesin. Tekrar basvuru
"zaten listedesiniz" yanitini alir, yeni satir acmaz.

Revision ID: 0016_waitlist_entry
Revises: 0015_organization_soft_delete
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_waitlist_entry"
down_revision: str | None = "0015_organization_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waitlist_entry",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("organization_name", sa.String(length=255), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_waitlist_entry")),
        sa.UniqueConstraint("email", name=op.f("uq_waitlist_entry_email")),
    )
    op.create_index(
        op.f("ix_waitlist_entry_email"), "waitlist_entry", ["email"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_waitlist_entry_email"), table_name="waitlist_entry")
    op.drop_table("waitlist_entry")
