"""job + audit_log tabloları, document.idempotency_key + RLS

Revision ID: 0004_job_audit_log
Revises: 0003_document
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_job_audit_log"
down_revision: str | None = "0003_document"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "PARSING",
                "INDEXING",
                "EXTRACTING",
                "REVIEW_READY",
                "FAILED",
                name="jobstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            ["document_id"],
            ["document.id"],
            name=op.f("fk_job_document_id_document"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organization.id"],
            name=op.f("fk_job_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job")),
    )
    op.create_index(op.f("ix_job_document_id"), "job", ["document_id"], unique=False)
    op.create_index(op.f("ix_job_tenant_id"), "job", ["tenant_id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["user_account.id"],
            name=op.f("fk_audit_log_actor_user_id_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organization.id"],
            name=op.f("fk_audit_log_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_tenant_id"), "audit_log", ["tenant_id"], unique=False)

    op.add_column("document", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_document_tenant_idempotency", "document", ["tenant_id", "idempotency_key"]
    )

    # --- RLS: kiracı izolasyonu (bkz. ADR-0003) ---
    op.execute("ALTER TABLE job ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE job FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY job_tenant_isolation ON job "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )

    # audit_log append-only'dir: yalnızca SELECT ve INSERT politikası tanımlanır;
    # UPDATE/DELETE için politika olmadığından uygulama rolü kayıt değiştiremez/silemez.
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY audit_log_tenant_select ON audit_log FOR SELECT "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )
    op.execute(
        "CREATE POLICY audit_log_tenant_insert ON audit_log FOR INSERT "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_log_tenant_insert ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_log_tenant_select ON audit_log")
    op.execute("DROP POLICY IF EXISTS job_tenant_isolation ON job")
    op.drop_constraint("uq_document_tenant_idempotency", "document", type_="unique")
    op.drop_column("document", "idempotency_key")
    op.drop_index(op.f("ix_audit_log_tenant_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_action"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_job_tenant_id"), table_name="job")
    op.drop_index(op.f("ix_job_document_id"), table_name="job")
    op.drop_table("job")
