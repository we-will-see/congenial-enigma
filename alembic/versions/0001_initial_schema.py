"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-03
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scrip_code", sa.String(length=10), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_aliases", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("sub_sector", sa.String(length=100), nullable=True),
        sa.Column("bse_id", sa.String(length=20), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scrip_code"),
    )
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_type", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("documents_processed", sa.Integer(), nullable=False),
        sa.Column("documents_failed", sa.Integer(), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("bse_filing_id", sa.String(length=50), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("quarter", sa.String(length=10), nullable=True),
        sa.Column("fy_year", sa.Integer(), nullable=True),
        sa.Column("filing_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bse_filing_id"),
    )
    op.create_index("idx_events_company_date", "events", ["company_id", sa.text("event_date DESC")])
    op.create_index("idx_events_quarter", "events", ["quarter"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("bse_url", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("pdf_type", sa.String(length=20), nullable=True),
        sa.Column("extraction_status", sa.String(length=20), nullable=False),
        sa.Column("extraction_method", sa.String(length=20), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("quality_flags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_documents_event", "documents", ["event_id"])
    op.create_index("idx_documents_status", "documents", ["extraction_status"])
    op.create_index("idx_documents_type", "documents", ["document_type"])
    op.create_table(
        "financials",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("period_type", sa.String(length=10), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=True),
        sa.Column("revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column("ebitda", sa.Numeric(12, 2), nullable=True),
        sa.Column("ebitda_margin", sa.Numeric(6, 4), nullable=True),
        sa.Column("da", sa.Numeric(12, 2), nullable=True),
        sa.Column("ebit", sa.Numeric(12, 2), nullable=True),
        sa.Column("finance_costs", sa.Numeric(12, 2), nullable=True),
        sa.Column("pbt", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax", sa.Numeric(12, 2), nullable=True),
        sa.Column("pat", sa.Numeric(12, 2), nullable=True),
        sa.Column("eps_basic", sa.Numeric(10, 2), nullable=True),
        sa.Column("eps_diluted", sa.Numeric(10, 2), nullable=True),
        sa.Column("shares_cr", sa.Numeric(10, 4), nullable=True),
        sa.Column("currency", sa.String(length=5), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("restated", sa.Boolean(), nullable=False),
        sa.Column("restatement_note", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.String(length=20), nullable=True),
        sa.Column("quality_flags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "period", "period_type"),
    )
    op.create_index("idx_financials_company_period", "financials", ["company_id", "period"])
    op.create_table(
        "management_changes",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("change_type", sa.String(length=30), nullable=False),
        sa.Column("person_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=False),
        sa.Column("role_category", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("din", sa.String(length=20), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "person_name", "change_type", "effective_date", name="uq_mgmt_change_identity"),
    )
    op.create_index("idx_mgmt_changes_company", "management_changes", ["company_id"])
    op.create_index("idx_mgmt_changes_date", "management_changes", [sa.text("filing_date DESC")])
    op.create_table(
        "press_release_sections",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("section_type", sa.String(length=50), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "slides",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("slide_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "slide_number"),
    )
    op.create_table(
        "turns",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("speaker_raw", sa.Text(), nullable=True),
        sa.Column("speaker_name", sa.String(length=200), nullable=True),
        sa.Column("speaker_role", sa.String(length=20), nullable=False),
        sa.Column("speaker_org", sa.String(length=200), nullable=True),
        sa.Column("speaker_title", sa.String(length=200), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "turn_index"),
    )
    op.create_index("idx_turns_document", "turns", ["document_id"])
    op.create_index("idx_turns_role", "turns", ["speaker_role"])
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
    op.create_table(
        "financials_history",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("financials_id", sa.BigInteger(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["financials_id"], ["financials.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("financials_history")
    op.drop_index("embeddings_vector_idx", table_name="embeddings")
    op.drop_index("idx_embeddings_company", table_name="embeddings")
    op.drop_table("embeddings")
    op.drop_index("idx_turns_role", table_name="turns")
    op.drop_index("idx_turns_document", table_name="turns")
    op.drop_table("turns")
    op.drop_table("slides")
    op.drop_table("press_release_sections")
    op.drop_index("idx_mgmt_changes_date", table_name="management_changes")
    op.drop_index("idx_mgmt_changes_company", table_name="management_changes")
    op.drop_table("management_changes")
    op.drop_index("idx_financials_company_period", table_name="financials")
    op.drop_table("financials")
    op.drop_index("idx_documents_type", table_name="documents")
    op.drop_index("idx_documents_status", table_name="documents")
    op.drop_index("idx_documents_event", table_name="documents")
    op.drop_table("documents")
    op.drop_index("idx_events_quarter", table_name="events")
    op.drop_index("idx_events_company_date", table_name="events")
    op.drop_table("events")
    op.drop_table("pipeline_runs")
    op.drop_table("companies")
