"""abonelige son olay zaman damgasi (sirasiz webhook korumasi)

Webhook'lar sira garantisi VERMEZ: saglayicinin yeniden denemesi ya da kuyruk
gecikmesi yuzunden eski bir olay yenisinden SONRA gelebilir. Damga olmadan, gec
gelen bir "iptal edildi" olayi sonradan gelmis "yeniden etkinlesti"yi ezer ve
musterinin ODEDIGI erisimi kapatir.

Revision ID: 0018_subscription_last_event
Revises: 0017_email_suppression
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_subscription_last_event"
down_revision: str | None = "0017_email_suppression"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscription",
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscription", "last_event_at")
