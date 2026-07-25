"""organization icin yumusak silme (KVKK md. 7 hesap kapatma)

Organizasyon satiri KALICI olarak SILINMEZ; "mezar tasi" olarak birakilir.
Sebep: ``TenantMixin`` tum kiraci-ozel tablolari ``organization.id``'ye
ON DELETE CASCADE ile baglar — satiri silmek ``subscription``, ``usage_record``
ve ``audit_log`` kayitlarini da goturur. Bunlarin saklanmasi VUK (fatura/defter
10 yil) ve kurumsal denetim gerekligidir; KVKK silme hakki, kanuni saklama
yukumlulugu bulunan veriler icin istisnalidir.

Bu yuzden akis sudur: ``deleted_at`` isaretlenir → kiraci verisi (ihale, dokuman,
bulgu, dosya) saklama penceresi sonunda KALICI silinir → organizasyon adi/slug'i
anonimlestirilir → fatura ve denetim kayitlari kalir.

Revision ID: 0015_organization_soft_delete
Revises: 0014_soft_delete
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_organization_soft_delete"
down_revision: str | None = "0014_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_organization_deleted_at",
        "organization",
        ["deleted_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )
    # Anonimlestirme sonrasi slug benzersizligi korunmali: silinen org'un slug'i
    # serbest kalir ki ayni slug yeniden kullanilabilsin (mezar tasi
    # `deleted-<uuid>` alir). Ek kisit gerekmez, mevcut unique yeterlidir.


def downgrade() -> None:
    op.drop_index("ix_organization_deleted_at", table_name="organization")
    op.drop_column("organization", "deleted_at")
