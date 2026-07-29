"""abonelik yasam dongusu: iptal ve planlanmis plan degisimi

`/sartlar` 3. bolum uc kural taahhut eder: yukseltme ANINDA, dusurme DONEM
SONUNDA, iptal DONEM SONUNDA erisimi keser. Son ikisi bir GELECEK tarih ve o
tarihte uygulanacak bir hedef gerektirir; bu migration onu tutacak alanlari
ekler. Alanlar olmadan "donem sonunda" sozu tutulamaz: ne kullaniciya erisimin
ne zamana kadar surdugu soylenebilir, ne de degisim uygulanabilir.

`cancel_at_period_end` NOT NULL + server_default=false: mevcut satirlarin hicbiri
iptal edilmis degildir ve bu alanin NULL olmasi "bilinmiyor" anlamina gelirdi —
erisim kesme kararinda bilinmeyen bir deger tehlikelidir.

Revision ID: 0019_subscription_lifecycle
Revises: 0018_subscription_last_event
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_subscription_lifecycle"
down_revision: str | None = "0018_subscription_last_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscription",
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscription",
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "subscription",
        sa.Column(
            "pending_plan",
            # `plan` sutunuyla ayni DDL (bkz. 0010_billing): native_enum=False
            # oldugu icin fiziksel tip VARCHAR(20).
            sa.Enum("FREE", "PRO", "ENTERPRISE", name="plantier", native_enum=False, length=20),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("subscription", "pending_plan")
    op.drop_column("subscription", "cancel_at_period_end")
    op.drop_column("subscription", "current_period_end")
