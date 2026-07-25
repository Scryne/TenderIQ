"""tender/document icin yumusak silme kolonu (KVKK kalici silme akisi, Faz 4)

``deleted_at`` NULL ise satir canlidir. Kullanicinin "sil" demesi veriyi aninda
yok etmez: satir isaretlenir, tum okuma yollarindan duser
(``tenderiq_core.db.soft_delete``) ve saklama penceresi (``DATA_RETENTION_DAYS``)
dolunca zamanlanmis is satiri ve nesne depolamadaki dosyayi KALICI olarak siler.

Indeks kismidir (``WHERE deleted_at IS NOT NULL``): supurme isi yalnizca
silinmis satirlari tarar ve bunlar toplam satirlarin cok kucuk bir yuzdesidir —
tam indeks her canli satir icin de yer ve yazma maliyeti getirirdi.

Revision ID: 0014_soft_delete
Revises: 0013_normalize_email
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_soft_delete"
down_revision: str | None = "0013_normalize_email"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("tender", "document")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            f"ix_{table}_deleted_at",
            table,
            ["deleted_at"],
            unique=False,
            postgresql_where=sa.text("deleted_at IS NOT NULL"),
        )

    # Dokuman ihalesiyle BIRLIKTE mi silindi, yoksa tek tek mi? Geri alma yalnizca
    # birlikte silinenleri geri acar; kullanicinin ayrica sildigi dosya silinmis
    # kalmalidir. Ayirt etmek icin zaman damgasi karsilastirmasi YETMEZ: iki silme
    # ayni saat tikine dusebilir (hizli ardisik istekler) ve o zaman tek tek
    # silinen dosya da dirilir. Bu yuzden ayri, acik bir bayrak tutulur.
    op.add_column(
        "document",
        sa.Column(
            "deleted_with_tender",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.execute("ALTER TABLE document DROP COLUMN IF EXISTS deleted_with_tender")
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_column(table, "deleted_at")
