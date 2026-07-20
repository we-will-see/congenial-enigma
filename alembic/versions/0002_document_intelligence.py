"""Add page-aware documents, chunks, and notebooks.

Revision ID: 0002_document_intelligence
Revises: 0001_initial_schema
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_document_intelligence"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("title", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("original_filename", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("mime_type", sa.String(length=100), nullable=True))
    op.add_column(
        "documents",
        sa.Column("source_type", sa.String(length=50), server_default="bse", nullable=False),
    )
    op.add_column("documents", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("rights_scope", sa.String(length=50), server_default="public", nullable=False),
    )
    op.add_column("documents", sa.Column("uploaded_by", sa.String(length=200), nullable=True))
    op.add_column("documents", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("content_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.execute("UPDATE documents SET source_url = bse_url WHERE source_url IS NULL")
    op.drop_column("documents", "bse_url")
    op.create_index("idx_documents_file_hash", "documents", ["file_hash"])
    op.create_index("idx_documents_source_type", "documents", ["source_type"])

    op.create_table(
        "document_pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("extraction_method", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=50), server_default="page-v1", nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_page_number"),
    )
    op.create_index("idx_document_pages_document", "document_pages", ["document_id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("speaker_name", sa.String(length=200), nullable=True),
        sa.Column("speaker_role", sa.String(length=50), nullable=True),
        sa.Column("section_type", sa.String(length=50), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("chunker_version", sa.String(length=50), server_default="page-v1", nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_chunk_document_ordinal"),
    )
    op.create_index("idx_chunks_document", "chunks", ["document_id"])
    op.create_index("idx_chunks_pages", "chunks", ["document_id", "page_start", "page_end"])
    op.execute("CREATE INDEX idx_chunks_fts ON chunks USING gin (to_tsvector('english', text))")
    op.execute("CREATE INDEX idx_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")

    op.create_table(
        "notebooks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("namespace_id", sa.String(length=100), server_default="default", nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("owner_id", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace_id", "name", name="uq_notebook_namespace_name"),
    )
    op.create_index("idx_notebooks_namespace", "notebooks", ["namespace_id"])

    op.create_table(
        "notebook_documents",
        sa.Column("notebook_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=100)), nullable=True),
        sa.Column("added_by", sa.String(length=200), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("notebook_id", "document_id"),
    )
    op.create_index("idx_notebook_documents_document", "notebook_documents", ["document_id"])

    # The legacy table contains derived vectors without reliable page citations.
    # Reprocessing documents repopulates the canonical page-aware chunks table.
    op.drop_index("embeddings_vector_idx", table_name="embeddings")
    op.drop_index("idx_embeddings_company", table_name="embeddings")
    op.drop_table("embeddings")


def downgrade() -> None:
    op.create_table(
        "embeddings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("turn_id", sa.BigInteger(), nullable=True),
        sa.Column("slide_id", sa.BigInteger(), nullable=True),
        sa.Column("section_id", sa.BigInteger(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("quarter", sa.String(length=10), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("speaker_role", sa.String(length=20), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["press_release_sections.id"]),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"]),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_embeddings_company", "embeddings", ["company_id"])
    op.create_index(
        "embeddings_vector_idx",
        "embeddings",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_index("idx_notebook_documents_document", table_name="notebook_documents")
    op.drop_table("notebook_documents")
    op.drop_index("idx_notebooks_namespace", table_name="notebooks")
    op.drop_table("notebooks")
    op.execute("DROP INDEX IF EXISTS idx_chunks_fts")
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_hnsw")
    op.drop_index("idx_chunks_pages", table_name="chunks")
    op.drop_index("idx_chunks_document", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("idx_document_pages_document", table_name="document_pages")
    op.drop_table("document_pages")
    op.drop_index("idx_documents_source_type", table_name="documents")
    op.drop_index("idx_documents_file_hash", table_name="documents")
    op.drop_column("documents", "content_version")
    op.drop_column("documents", "file_size_bytes")
    op.drop_column("documents", "uploaded_by")
    op.drop_column("documents", "rights_scope")
    op.add_column("documents", sa.Column("bse_url", sa.Text(), nullable=True))
    op.execute("UPDATE documents SET bse_url = source_url WHERE source_type = 'bse'")
    op.drop_column("documents", "source_url")
    op.drop_column("documents", "source_type")
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "original_filename")
    op.drop_column("documents", "title")
