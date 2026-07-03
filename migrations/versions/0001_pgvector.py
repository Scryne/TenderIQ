"""pgvector uzantısını etkinleştirir.

Temel şema tabloları (Organization, User, ...) Faz 0.2 migration'larında eklenir.
Bkz. ADR-0002 (pgvector).

Revision ID: 0001_pgvector
Revises:
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_pgvector"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
