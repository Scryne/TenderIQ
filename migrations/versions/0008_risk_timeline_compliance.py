"""risk_flag + timeline_event + compliance_result + capability_profile + RLS (Sprint 2.3, §8.2)

Üç yeni bulgu tablosu (risk/takvim/uygunluk) ``requirement``/``deliverable`` ile
aynı grounding + idempotency sözleşmesini paylaşır (ADR-0006): ``source_element_id``
kaynak ``ParsedElement``e N—1 bağdır (UNGROUNDED'da NULL), ``uq_*_document_seq``
idempotent yeniden-çıkarımı kilitler, re-parse cascade türetilmiş bulguları siler.

``capability_profile`` farklıdır: dokümandan çıkarılmaz, kullanıcı girer; kiracı
başına tekildir (compliance gap analizinin girdisi, §6.7).

Revision ID: 0008_risk_timeline_compliance
Revises: 0007_requirement_deliverable
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_risk_timeline_compliance"
down_revision: str | None = "0007_requirement_deliverable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# risk/takvim/uygunluk tablolarını oluşturma sırası (FK bağımlılığı yok, sıralı).
_FINDING_TABLES = ("risk_flag", "timeline_event", "compliance_result")
# RLS'nin uygulanacağı tüm Sprint 2.3 tabloları (capability_profile dahil).
_RLS_TABLES = (*_FINDING_TABLES, "capability_profile")


def _finding_columns() -> list[sa.Column[object]]:
    """Üç bulgu tablosunun ortak kolonları (grounding + idempotency sözleşmesi).

    ``requirement``/``deliverable``daki ``is_mandatory`` burada yoktur — risk/
    takvim/uygunluk öğeleri zorunluluk taşımaz; tipe özgü kolonlar çağrı yerinde
    eklenir.
    """
    return [
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
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


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "risk_flag",
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("LOW", "MEDIUM", "HIGH", name="riskseverity", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "PENALTY",
                "TERMINATION",
                "WARRANTY",
                "PAYMENT",
                "OTHER",
                name="riskcategory",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        *_finding_columns(),
        *_finding_constraints("risk_flag"),
    )
    _finding_indexes("risk_flag")

    op.create_table(
        "timeline_event",
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "TENDER_DATE",
                "BID_DEADLINE",
                "DELIVERY",
                "WARRANTY",
                "OTHER",
                name="timelinekind",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("value_text", sa.Text(), nullable=False),
        *_finding_columns(),
        *_finding_constraints("timeline_event"),
    )
    _finding_indexes("timeline_event")

    op.create_table(
        "compliance_result",
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "MET",
                "PARTIAL",
                "UNMET",
                name="compliancestatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("rationale", sa.Text(), nullable=False),
        *_finding_columns(),
        *_finding_constraints("compliance_result"),
    )
    _finding_indexes("compliance_result")

    # capability_profile: kullanıcı girdisi, kiracı-tekil (bulgu deseni değil).
    op.create_table(
        "capability_profile",
        sa.Column("content", sa.Text(), nullable=False),
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
            name=op.f("fk_capability_profile_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_capability_profile")),
        sa.UniqueConstraint("tenant_id", name="uq_capability_profile_tenant"),
    )
    op.create_index(
        op.f("ix_capability_profile_tenant_id"), "capability_profile", ["tenant_id"], unique=False
    )

    # --- RLS: kiracı izolasyonu (bkz. ADR-0003) ---
    for table in _RLS_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS capability_profile_tenant_isolation ON capability_profile")
    op.drop_index(op.f("ix_capability_profile_tenant_id"), table_name="capability_profile")
    op.drop_table("capability_profile")

    for table in reversed(_FINDING_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_index(op.f(f"ix_{table}_tenant_id"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_source_element_id"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_document_id"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_tender_id"), table_name=table)
        op.drop_table(table)
