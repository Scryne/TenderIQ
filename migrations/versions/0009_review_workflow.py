"""İnsan-döngüde inceleme: bulgu inceleme kolonları + finding_comment + RLS (Sprint 3.2, §4.3)

Beş bulgu tablosuna ``review_status`` (PENDING varsayılan) + ``reviewed_by`` +
``reviewed_at`` eklenir; yorumlar için polimorfik ``finding_comment`` tablosu
(finding_kind + finding_id — gerçek FK yok, worker yeniden çıkarımda yorumları
temizler) açılır. ``audit_log.resource_id`` indekslenir: bulgu başına düzenleme
geçmişi bu kolon üzerinden sorgulanır.

Revision ID: 0009_review_workflow
Revises: 0008_risk_timeline_compliance
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_review_workflow"
down_revision: str | None = "0008_risk_timeline_compliance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# İnceleme kolonlarının ekleneceği beş bulgu tablosu.
_FINDING_TABLES = (
    "requirement",
    "deliverable",
    "risk_flag",
    "timeline_event",
    "compliance_result",
)


def upgrade() -> None:
    for table in _FINDING_TABLES:
        op.add_column(
            table,
            sa.Column(
                "review_status",
                sa.Enum(
                    "PENDING",
                    "APPROVED",
                    "EDITED",
                    "REJECTED",
                    name="reviewstatus",
                    native_enum=False,
                    length=20,
                ),
                nullable=False,
                server_default="PENDING",
            ),
        )
        op.add_column(table, sa.Column("reviewed_by", sa.Uuid(), nullable=True))
        op.add_column(table, sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_reviewed_by_user_account"),
            table,
            "user_account",
            ["reviewed_by"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "finding_comment",
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column(
            "finding_kind",
            sa.Enum(
                "REQUIREMENT",
                "DELIVERABLE",
                "RISK",
                "TIMELINE",
                "COMPLIANCE",
                name="findingkind",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tender_id"],
            ["tender.id"],
            name=op.f("fk_finding_comment_tender_id_tender"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["user_account.id"],
            name=op.f("fk_finding_comment_author_user_id_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organization.id"],
            name=op.f("fk_finding_comment_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_finding_comment")),
    )
    op.create_index(
        op.f("ix_finding_comment_tender_id"), "finding_comment", ["tender_id"], unique=False
    )
    op.create_index(
        op.f("ix_finding_comment_finding_id"), "finding_comment", ["finding_id"], unique=False
    )
    op.create_index(
        op.f("ix_finding_comment_tenant_id"), "finding_comment", ["tenant_id"], unique=False
    )

    # --- RLS: kiracı izolasyonu (bkz. ADR-0003) ---
    op.execute("ALTER TABLE finding_comment ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE finding_comment FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY finding_comment_tenant_isolation ON finding_comment "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )

    # Bulgu başına geçmiş sorgusu: WHERE resource_type = :kind AND resource_id = :id
    op.create_index(op.f("ix_audit_log_resource_id"), "audit_log", ["resource_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_resource_id"), table_name="audit_log")

    op.execute("DROP POLICY IF EXISTS finding_comment_tenant_isolation ON finding_comment")
    op.drop_index(op.f("ix_finding_comment_tenant_id"), table_name="finding_comment")
    op.drop_index(op.f("ix_finding_comment_finding_id"), table_name="finding_comment")
    op.drop_index(op.f("ix_finding_comment_tender_id"), table_name="finding_comment")
    op.drop_table("finding_comment")

    for table in reversed(_FINDING_TABLES):
        op.drop_constraint(op.f(f"fk_{table}_reviewed_by_user_account"), table, type_="foreignkey")
        op.drop_column(table, "reviewed_at")
        op.drop_column(table, "reviewed_by")
        op.drop_column(table, "review_status")
