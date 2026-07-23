"""invitation tablosu — organizasyona uye daveti (Sprint 3.3-E-2)

``invitation`` RLS'siz bir KIMLIK tablosudur (``membership``/``user_account`` gibi):
accept akisi kimliksiz calisir ve token'la kiraci sinirini asar, bu yuzden RLS
politikasi YOKTUR; yonetici uclari aktif organizasyona elle filtreler. Token'in
yalniz SHA-256 ozeti (``token_hash``) saklanir; benzersizdir.

Revision ID: 0012_invitation
Revises: 0011_email_verified
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_invitation"
down_revision: str | None = "0011_email_verified"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitation",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "role",
            sa.Enum("ADMIN", "MEMBER", "VIEWER", name="role", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "ACCEPTED",
                "REVOKED",
                name="invitationstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_invitation_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["user_account.id"],
            name=op.f("fk_invitation_invited_by_user_id_user_account"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitation")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitation_token_hash")),
    )
    op.create_index(
        op.f("ix_invitation_organization_id"), "invitation", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_invitation_email"), "invitation", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invitation_email"), table_name="invitation")
    op.drop_index(op.f("ix_invitation_organization_id"), table_name="invitation")
    op.drop_table("invitation")
