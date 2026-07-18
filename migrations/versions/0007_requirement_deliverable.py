"""requirement + deliverable tabloları + RLS (Sprint 2.2, §8.1/§8.2)

Zorunlu grounding (ADR-0006): ``source_element_id`` kaynak ``ParsedElement``e
N—1 bağdır; UNGROUNDED bulgularda NULL (API bu satırları döndürmez). Re-parse
öğeleri sildiğinde türetilmiş bulgular cascade ile gider — hat yeniden
koştuğunda extracting fazı delete+insert ile yeniden üretir.

Revision ID: 0007_requirement_deliverable
Revises: 0006_chunk_embedding
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_requirement_deliverable"
down_revision: str | None = "0006_chunk_embedding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _finding_columns() -> list[sa.Column[object]]:
    """İki bulgu tablosunun ortak kolonları (grounding + idempotency sözleşmesi)."""
    return [
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("source_element_id", sa.Uuid(), nullable=True),
        sa.Column(
            "grounding_resolution",
            sa.Enum(
                "ELEMENT",
                "CHUNK",
                "UNGROUNDED",
                name="groundingresolution",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("source_quote", sa.Text(), nullable=False),
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
    ]


def _finding_constraints(table: str) -> list[sa.schema.SchemaItem]:
    return [
        sa.ForeignKeyConstraint(
            ["tender_id"],
            ["tender.id"],
            name=op.f(f"fk_{table}_tender_id_tender"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f(f"fk_{table}_document_id_document"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_element_id"],
            ["parsed_element.id"],
            name=op.f(f"fk_{table}_source_element_id_parsed_element"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organization.id"],
            name=op.f(f"fk_{table}_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        sa.UniqueConstraint("document_id", "seq", name=f"uq_{table}_document_seq"),
    ]


def _finding_indexes(table: str) -> None:
    op.create_index(op.f(f"ix_{table}_tender_id"), table, ["tender_id"], unique=False)
    op.create_index(op.f(f"ix_{table}_document_id"), table, ["document_id"], unique=False)
    op.create_index(
        op.f(f"ix_{table}_source_element_id"), table, ["source_element_id"], unique=False
    )
    op.create_index(op.f(f"ix_{table}_tenant_id"), table, ["tenant_id"], unique=False)


def upgrade() -> None:
    op.create_table(
        "requirement",
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "TECHNICAL",
                "ADMINISTRATIVE",
                "FINANCIAL",
                name="requirementkind",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        *_finding_columns(),
        *_finding_constraints("requirement"),
    )
    _finding_indexes("requirement")

    op.create_table(
        "deliverable",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "DOCUMENT",
                "CERTIFICATE",
                "GUARANTEE",
                "OTHER",
                name="deliverablekind",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        *_finding_columns(),
        *_finding_constraints("deliverable"),
    )
    _finding_indexes("deliverable")

    # --- RLS: kiracı izolasyonu (bkz. ADR-0003) ---
    for table in ("requirement", "deliverable"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
        )


def downgrade() -> None:
    for table in ("deliverable", "requirement"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_index(op.f(f"ix_{table}_tenant_id"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_source_element_id"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_document_id"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_tender_id"), table_name=table)
        op.drop_table(table)
