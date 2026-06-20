from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, JSON, Text
from sqlmodel import Field, Relationship, SQLModel

from app.src.database.models.data import DataSourceType
from app.src.database.models.language import new_id, now_utc

if TYPE_CHECKING:
    from app.src.database.models.data import DataRow
    from app.src.database.models.dataset import Dataset
    from app.src.database.models.label import Label


class ImportStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class ImportRecord(SQLModel, table=True):
    __tablename__ = "imports"

    id: str = Field(default_factory=lambda: new_id("imp"), primary_key=True)
    dataset_id: str = Field(foreign_key="datasets.id", index=True)
    source_type: DataSourceType = Field(index=True)
    status: ImportStatus = Field(default=ImportStatus.ready, index=True)
    filename: str | None = Field(default=None, index=True)
    content_type: str | None = Field(default=None, max_length=160)
    storage_bucket: str | None = Field(default=None, max_length=160)
    storage_path: str | None = Field(default=None, index=True)
    column_mapping: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    row_count: int = 0
    label_count: int = 0
    error: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))

    dataset: "Dataset" = Relationship(back_populates="imports")
    data_rows: list["DataRow"] = Relationship(back_populates="import_record")
    labels: list["Label"] = Relationship(back_populates="import_record")
