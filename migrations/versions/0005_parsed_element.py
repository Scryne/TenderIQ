"""parsed_element tablosu + document.page_count + RLS

Revision ID: 0005_parsed_element
Revises: 0004_job_audit_log
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_parsed_element"
down_revision: str | None = "0004_job_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parsed_element",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "HEADING",
                "PARAGRAPH",
                "LIST_ITEM",
                "TABLE",
                "CAPTION",
                "OTHER",
                name="elementkind",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum("DIGITAL", "SCANNED", name="parsesource", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("bbox_x0", sa.Float(), nullable=True),
        sa.Column("bbox_y0", sa.Float(), nullable=True),
        sa.Column("bbox_x1", sa.Float(), nullable=True),
        sa.Column("bbox_y1", sa.Float(), nullable=True),
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
            name=op.f("fk_parsed_element_document_id_document"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organization.id"],
            name=op.f("fk_parsed_element_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parsed_element")),
        sa.UniqueConstraint("document_id", "seq", name="uq_parsed_element_document_seq"),
    )
    op.create_index(
        op.f("ix_parsed_element_document_id"), "parsed_element", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_parsed_element_tenant_id"), "parsed_element", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_parsed_element_document_page", "parsed_element", ["document_id", "page"], unique=False
    )

    op.add_column("document", sa.Column("page_count", sa.Integer(), nullable=True))

    # --- RLS: kiracı izolasyonu (bkz. ADR-0003) ---
    op.execute("ALTER TABLE parsed_element ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE parsed_element FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY parsed_element_tenant_isolation ON parsed_element "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS parsed_element_tenant_isolation ON parsed_element")
    op.drop_column("document", "page_count")
    op.drop_index("ix_parsed_element_document_page", table_name="parsed_element")
    op.drop_index(op.f("ix_parsed_element_tenant_id"), table_name="parsed_element")
    op.drop_index(op.f("ix_parsed_element_document_id"), table_name="parsed_element")
    op.drop_table("parsed_element")
