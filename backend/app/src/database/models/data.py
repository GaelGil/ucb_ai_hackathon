from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, JSON, Text
from sqlmodel import Field, Relationship, SQLModel

from app.src.database.models.language import new_id, now_utc

if TYPE_CHECKING:
    from app.src.database.models.dataset import Dataset
    from app.src.database.models.import_record import ImportRecord
    from app.src.database.models.label import Label
    from app.src.database.models.suggestion import AiSuggestion


class DataSourceType(str, enum.Enum):
    text = "text"
    csv = "csv"
    pdf = "pdf"
    image = "image"


class DataRow(SQLModel, table=True):
    __tablename__ = "data_rows"

    id: str = Field(default_factory=lambda: new_id("row"), primary_key=True)
    dataset_id: str = Field(foreign_key="datasets.id", index=True)
    import_id: str | None = Field(default=None, foreign_key="imports.id", index=True)
    row_index: int = Field(default=0, index=True)
    source_type: DataSourceType = Field(index=True)
    text_content: str | None = Field(default=None, sa_column=Column(Text))
    storage_bucket: str | None = Field(default=None, max_length=160)
    storage_path: str | None = Field(default=None, index=True)
    page_number: int | None = Field(default=None)
    row_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))

    dataset: "Dataset" = Relationship(back_populates="data_rows")
    import_record: "ImportRecord | None" = Relationship(back_populates="data_rows")
    labels: list["Label"] = Relationship(
        back_populates="data_row",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    ai_suggestions: list["AiSuggestion"] = Relationship(
        back_populates="data_row",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


Data = DataRow
DataType = DataSourceType
