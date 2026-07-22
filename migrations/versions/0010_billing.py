"""abonelik + kullanim kaydi tablolari + RLS (Sprint 3.3-A)

``subscription`` kiraci basina tek satir (plan kademesi + durum + odeme saglayici
alanlari); ``usage_record`` islenen dokuman basina kullanim (kota sayimi). Ikisi de
kiraci-ozeldir ve RLS ile korunur (bkz. ADR-0003). Limitler DB'de tutulmaz —
``tenderiq_core.billing.plans`` kademesinden okunur.

Revision ID: 0010_billing
Revises: 0009_review_workflow
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_billing"
down_revision: str | None = "0009_review_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscription",
        sa.Column(
            "plan",
            sa.Enum(
                "FREE",
                "PRO",
                "ENTERPRISE",
                name="plantier",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "PAST_DUE",
                "CANCELED",
                "TRIALING",
                name="subscriptionstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("provider_customer_id", sa.String(length=255), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
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
            ["tenant_id"],
            ["organization.id"],
            name=op.f("fk_subscription_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription")),
        sa.UniqueConstraint("tenant_id", name="uq_subscription_tenant_id"),
    )
    op.create_index(op.f("ix_subscription_tenant_id"), "subscription", ["tenant_id"], unique=False)

    op.create_table(
        "usage_record",
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("pages", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_usage_record_document_id_document"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organization.id"],
            name=op.f("fk_usage_record_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_record")),
    )
    op.create_index(
        op.f("ix_usage_record_document_id"), "usage_record", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_usage_record_recorded_at"), "usage_record", ["recorded_at"], unique=False
    )
    op.create_index(op.f("ix_usage_record_tenant_id"), "usage_record", ["tenant_id"], unique=False)

    # --- RLS: kiracı izolasyonu (bkz. ADR-0003) ---
    for table in ("subscription", "usage_record"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
        )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS usage_record_tenant_isolation ON usage_record")
    op.execute("DROP POLICY IF EXISTS subscription_tenant_isolation ON subscription")

    op.drop_index(op.f("ix_usage_record_tenant_id"), table_name="usage_record")
    op.drop_index(op.f("ix_usage_record_recorded_at"), table_name="usage_record")
    op.drop_index(op.f("ix_usage_record_document_id"), table_name="usage_record")
    op.drop_table("usage_record")

    op.drop_index(op.f("ix_subscription_tenant_id"), table_name="subscription")
    op.drop_table("subscription")
