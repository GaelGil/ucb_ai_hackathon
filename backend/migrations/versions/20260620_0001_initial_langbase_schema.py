"""Initial LangBase Supabase/Postgres schema.

Revision ID: 20260620_0001
Revises:
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "20260620_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


data_source_type = postgresql.ENUM(
    "text",
    "csv",
    "txt",
    "pdf",
    "image",
    name="datasourcetype",
    create_type=False,
)
import_status = postgresql.ENUM(
    "pending",
    "processing",
    "ready",
    "failed",
    name="importstatus",
    create_type=False,
)
label_type = postgresql.ENUM(
    "pos",
    "ocr",
    "translation",
    "emotion",
    "intention",
    "text",
    "custom",
    name="labeltype",
    create_type=False,
)
label_source = postgresql.ENUM(
    "csv_import",
    "human",
    "ai_accepted",
    "ai_updated",
    name="labelsource",
    create_type=False,
)
suggestion_status = postgresql.ENUM(
    "pending",
    "accepted",
    "denied",
    "updated",
    name="suggestionstatus",
    create_type=False,
)
research_type = postgresql.ENUM(
    "ocr",
    "pos",
    "translation",
    "grammar",
    "custom",
    name="researchtype",
    create_type=False,
)
job_status = postgresql.ENUM(
    "queued",
    "running",
    "succeeded",
    "failed",
    name="jobstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (
        data_source_type,
        import_status,
        label_type,
        label_source,
        suggestion_status,
        research_type,
        job_status,
    ):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "languages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_languages_code"), "languages", ["code"], unique=True)
    op.create_index(op.f("ix_languages_name"), "languages", ["name"], unique=False)

    op.create_table(
        "datasets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("language_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_datasets_language_id"), "datasets", ["language_id"], unique=False)
    op.create_index(op.f("ix_datasets_name"), "datasets", ["name"], unique=False)

    op.create_table(
        "imports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("dataset_id", sa.String(), nullable=False),
        sa.Column("source_type", data_source_type, nullable=False),
        sa.Column("status", import_status, nullable=False),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("content_type", sa.String(length=160), nullable=True),
        sa.Column("storage_bucket", sa.String(length=160), nullable=True),
        sa.Column("storage_path", sa.String(), nullable=True),
        sa.Column("column_mapping", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("label_count", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_imports_dataset_id"), "imports", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_imports_filename"), "imports", ["filename"], unique=False)
    op.create_index(op.f("ix_imports_source_type"), "imports", ["source_type"], unique=False)
    op.create_index(op.f("ix_imports_status"), "imports", ["status"], unique=False)
    op.create_index(op.f("ix_imports_storage_path"), "imports", ["storage_path"], unique=False)

    op.create_table(
        "data_rows",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("dataset_id", sa.String(), nullable=False),
        sa.Column("import_id", sa.String(), nullable=True),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("source_type", data_source_type, nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("storage_bucket", sa.String(length=160), nullable=True),
        sa.Column("storage_path", sa.String(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("row_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["import_id"], ["imports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_data_rows_dataset_id"), "data_rows", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_data_rows_import_id"), "data_rows", ["import_id"], unique=False)
    op.create_index(op.f("ix_data_rows_row_index"), "data_rows", ["row_index"], unique=False)
    op.create_index(op.f("ix_data_rows_source_type"), "data_rows", ["source_type"], unique=False)
    op.create_index(op.f("ix_data_rows_storage_path"), "data_rows", ["storage_path"], unique=False)

    op.create_table(
        "research",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("language_id", sa.String(), nullable=False),
        sa.Column("type", research_type, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_research_language_id"), "research", ["language_id"], unique=False)
    op.create_index(op.f("ix_research_type"), "research", ["type"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("type", sa.String(length=120), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_index(op.f("ix_jobs_type"), "jobs", ["type"], unique=False)

    op.create_table(
        "ai_suggestions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("dataset_id", sa.String(), nullable=False),
        sa.Column("data_row_id", sa.String(), nullable=False),
        sa.Column("research_id", sa.String(), nullable=True),
        sa.Column("label_type", label_type, nullable=False),
        sa.Column("status", suggestion_status, nullable=False),
        sa.Column("original_value", sa.JSON(), nullable=False),
        sa.Column("human_value", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["data_row_id"], ["data_rows.id"]),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["research_id"], ["research.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_suggestions_data_row_id"), "ai_suggestions", ["data_row_id"], unique=False)
    op.create_index(op.f("ix_ai_suggestions_dataset_id"), "ai_suggestions", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_ai_suggestions_label_type"), "ai_suggestions", ["label_type"], unique=False)
    op.create_index(op.f("ix_ai_suggestions_research_id"), "ai_suggestions", ["research_id"], unique=False)
    op.create_index(op.f("ix_ai_suggestions_status"), "ai_suggestions", ["status"], unique=False)

    op.create_table(
        "labels",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("dataset_id", sa.String(), nullable=False),
        sa.Column("data_row_id", sa.String(), nullable=False),
        sa.Column("import_id", sa.String(), nullable=True),
        sa.Column("ai_suggestion_id", sa.String(), nullable=True),
        sa.Column("type", label_type, nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("source", label_source, nullable=False),
        sa.Column("original_column_name", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ai_suggestion_id"], ["ai_suggestions.id"]),
        sa.ForeignKeyConstraint(["data_row_id"], ["data_rows.id"]),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"]),
        sa.ForeignKeyConstraint(["import_id"], ["imports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_labels_ai_suggestion_id"), "labels", ["ai_suggestion_id"], unique=False)
    op.create_index(op.f("ix_labels_data_row_id"), "labels", ["data_row_id"], unique=False)
    op.create_index(op.f("ix_labels_dataset_id"), "labels", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_labels_import_id"), "labels", ["import_id"], unique=False)
    op.create_index(op.f("ix_labels_name"), "labels", ["name"], unique=False)
    op.create_index(op.f("ix_labels_source"), "labels", ["source"], unique=False)
    op.create_index(op.f("ix_labels_type"), "labels", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_labels_type"), table_name="labels")
    op.drop_index(op.f("ix_labels_source"), table_name="labels")
    op.drop_index(op.f("ix_labels_name"), table_name="labels")
    op.drop_index(op.f("ix_labels_import_id"), table_name="labels")
    op.drop_index(op.f("ix_labels_dataset_id"), table_name="labels")
    op.drop_index(op.f("ix_labels_data_row_id"), table_name="labels")
    op.drop_index(op.f("ix_labels_ai_suggestion_id"), table_name="labels")
    op.drop_table("labels")
    op.drop_index(op.f("ix_ai_suggestions_status"), table_name="ai_suggestions")
    op.drop_index(op.f("ix_ai_suggestions_research_id"), table_name="ai_suggestions")
    op.drop_index(op.f("ix_ai_suggestions_label_type"), table_name="ai_suggestions")
    op.drop_index(op.f("ix_ai_suggestions_dataset_id"), table_name="ai_suggestions")
    op.drop_index(op.f("ix_ai_suggestions_data_row_id"), table_name="ai_suggestions")
    op.drop_table("ai_suggestions")
    op.drop_index(op.f("ix_jobs_type"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_research_type"), table_name="research")
    op.drop_index(op.f("ix_research_language_id"), table_name="research")
    op.drop_table("research")
    op.drop_index(op.f("ix_data_rows_storage_path"), table_name="data_rows")
    op.drop_index(op.f("ix_data_rows_source_type"), table_name="data_rows")
    op.drop_index(op.f("ix_data_rows_row_index"), table_name="data_rows")
    op.drop_index(op.f("ix_data_rows_import_id"), table_name="data_rows")
    op.drop_index(op.f("ix_data_rows_dataset_id"), table_name="data_rows")
    op.drop_table("data_rows")
    op.drop_index(op.f("ix_imports_storage_path"), table_name="imports")
    op.drop_index(op.f("ix_imports_status"), table_name="imports")
    op.drop_index(op.f("ix_imports_source_type"), table_name="imports")
    op.drop_index(op.f("ix_imports_filename"), table_name="imports")
    op.drop_index(op.f("ix_imports_dataset_id"), table_name="imports")
    op.drop_table("imports")
    op.drop_index(op.f("ix_datasets_name"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_language_id"), table_name="datasets")
    op.drop_table("datasets")
    op.drop_index(op.f("ix_languages_name"), table_name="languages")
    op.drop_index(op.f("ix_languages_code"), table_name="languages")
    op.drop_table("languages")

    bind = op.get_bind()
    for enum in (
        job_status,
        research_type,
        suggestion_status,
        label_source,
        label_type,
        import_status,
        data_source_type,
    ):
        enum.drop(bind, checkfirst=True)
