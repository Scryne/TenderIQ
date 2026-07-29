"""e-posta bastirma listesi (kalici bounce / sikayet)

Kalici bounce alan bir adrese gondermeye devam etmek, gonderen alan adinin
itibarini dusurur ve bir sure sonra MESRU e-postalar da spam'e duser. Bu tablo
teslimat oranini koruyan bir yatirimdir.

Kiraciya ait DEGILDIR: bir adres hangi kiraci icin gonderildiginden bagimsiz
olarak teslim edilemezdir. RLS'ye tabi degildir.

Revision ID: 0017_email_suppression
Revises: 0016_waitlist_entry
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_email_suppression"
down_revision: str | None = "0016_waitlist_entry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_suppression",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "hard_bounce",
                "complaint",
                "manual",
                name="suppressionreason",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_suppression")),
        sa.UniqueConstraint("email", name=op.f("uq_email_suppression_email")),
    )
    op.create_index(
        op.f("ix_email_suppression_email"), "email_suppression", ["email"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_suppression_email"), table_name="email_suppression")
    op.drop_table("email_suppression")
