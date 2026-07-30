"""LLM kullanim/maliyet kaydi (J.6 madde 1)

Kiraci x model x islem bazinda token ve tutar. Kota sayimi `usage_record`
uzerinden dokuman/sayfa boyutunda yapiliyordu; bu tablo PARA boyutunu ekler.

RLS: `tenant_id = app_current_tenant()` (migration 0021'in tek tanim noktasi).
Ham `current_setting` YAZILMAZ — `test_rls_no_context.py`nin yapisal kapisi
sapmayi yakalar.

Revision ID: 0022_llm_usage
Revises: 0021_rls_null_safe_tenant
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_llm_usage"
down_revision: str | None = "0021_rls_null_safe_tenant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "llm_usage"
_POLICY = "llm_usage_tenant_isolation"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id", ondelete="SET NULL")),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        # BigInteger: aylik toplam mikro-TL int32'yi asabilir.
        sa.Column("cost_micros_try", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("pricing_status", sa.String(length=20), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(f"ix_{_TABLE}_tenant_id", _TABLE, ["tenant_id"])
    op.create_index(f"ix_{_TABLE}_job_id", _TABLE, ["job_id"])
    op.create_index(f"ix_{_TABLE}_model", _TABLE, ["model"])
    # Donem toplami sorgusu: kiraci + tarih araligi. Tavan HER cagri oncesi
    # okunacagi icin bu indeks sicak yoldadir.
    op.create_index(f"ix_{_TABLE}_tenant_recorded", _TABLE, ["tenant_id", "recorded_at"])

    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {_POLICY} ON {_TABLE} "
        "USING (tenant_id = app_current_tenant()) "
        "WITH CHECK (tenant_id = app_current_tenant())"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON {_TABLE}")
    op.drop_index(f"ix_{_TABLE}_tenant_recorded", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_model", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_job_id", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_tenant_id", table_name=_TABLE)
    op.drop_table(_TABLE)
