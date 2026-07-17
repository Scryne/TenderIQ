"""chunk + embedding tabloları + RLS + HNSW vektör indeksi

Vektör boyutu (1024) BGE-M3 sözleşmesidir — ``tenderiq_core.models.embedding
.EMBEDDING_DIM`` ve ``EMBEDDING_DIM`` ayarı ile birlikte değişir (ADR-0008).

Tenant-scoped indeks stratejisi (§6.5): HNSW indeksi küreseldir; kiracı filtresi
RLS'ten gelir (kiracı-başına partial index kiracı sayısıyla ölçeklenmez).
Filtreli taramada recall düşerse pgvector ``hnsw.iterative_scan`` devreye alınır;
1M+ chunk eşiğinde Qdrant'a taşıma yolu ADR-0002'de tanımlıdır.

Revision ID: 0006_chunk_embedding
Revises: 0005_parsed_element
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0006_chunk_embedding"
down_revision: str | None = "0005_parsed_element"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.create_table(
        "chunk",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("element_seq_start", sa.Integer(), nullable=False),
        sa.Column("element_seq_end", sa.Integer(), nullable=False),
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
            name=op.f("fk_chunk_document_id_document"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organization.id"],
            name=op.f("fk_chunk_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunk")),
        sa.UniqueConstraint("document_id", "seq", name="uq_chunk_document_seq"),
    )
    op.create_index(op.f("ix_chunk_document_id"), "chunk", ["document_id"], unique=False)
    op.create_index(op.f("ix_chunk_tenant_id"), "chunk", ["tenant_id"], unique=False)

    op.create_table(
        "embedding",
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("vector", Vector(EMBEDDING_DIM), nullable=False),
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
            ["chunk_id"],
            ["chunk.id"],
            name=op.f("fk_embedding_chunk_id_chunk"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organization.id"],
            name=op.f("fk_embedding_tenant_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_embedding")),
        sa.UniqueConstraint("chunk_id", "model", name="uq_embedding_chunk_model"),
    )
    op.create_index(op.f("ix_embedding_chunk_id"), "embedding", ["chunk_id"], unique=False)
    op.create_index(op.f("ix_embedding_tenant_id"), "embedding", ["tenant_id"], unique=False)
    # ANN indeksi: cosine (vektörler L2-normalize yazılır). Parametreler pgvector
    # varsayılanları (m=16, ef_construction=64); büyüme planı J.1'de gözden geçirilir.
    op.create_index(
        "ix_embedding_vector_hnsw",
        "embedding",
        ["vector"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"vector": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )

    # --- RLS: kiracı izolasyonu (bkz. ADR-0003) ---
    for table in ("chunk", "embedding"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = current_setting('app.current_tenant', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)"
        )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS embedding_tenant_isolation ON embedding")
    op.drop_index("ix_embedding_vector_hnsw", table_name="embedding")
    op.drop_index(op.f("ix_embedding_tenant_id"), table_name="embedding")
    op.drop_index(op.f("ix_embedding_chunk_id"), table_name="embedding")
    op.drop_table("embedding")
    op.execute("DROP POLICY IF EXISTS chunk_tenant_isolation ON chunk")
    op.drop_index(op.f("ix_chunk_tenant_id"), table_name="chunk")
    op.drop_index(op.f("ix_chunk_document_id"), table_name="chunk")
    op.drop_table("chunk")
