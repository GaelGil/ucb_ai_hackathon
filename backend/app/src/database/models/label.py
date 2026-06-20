from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

from app.src.database.models.language import new_id, now_utc

if TYPE_CHECKING:
    from app.src.database.models.data import DataRow
    from app.src.database.models.dataset import Dataset
    from app.src.database.models.import_record import ImportRecord


class LabelType(str, enum.Enum):
    pos = "pos"
    ocr = "ocr"
    translation = "translation"
    emotion = "emotion"
    intention = "intention"
    text = "text"
    custom = "custom"


class LabelSource(str, enum.Enum):
    csv_import = "csv_import"
    human = "human"
    ai_accepted = "ai_accepted"
    ai_updated = "ai_updated"


class Label(SQLModel, table=True):
    __tablename__ = "labels"

    id: str = Field(default_factory=lambda: new_id("label"), primary_key=True)
    dataset_id: str = Field(foreign_key="datasets.id", index=True)
    data_row_id: str = Field(foreign_key="data_rows.id", index=True)
    import_id: str | None = Field(default=None, foreign_key="imports.id", index=True)
    ai_suggestion_id: str | None = Field(default=None, foreign_key="ai_suggestions.id", index=True)
    type: LabelType = Field(index=True)
    name: str | None = Field(default=None, index=True, max_length=160)
    value: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    source: LabelSource = Field(default=LabelSource.human, index=True)
    original_column_name: str | None = Field(default=None, max_length=160)
    created_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))

    dataset: "Dataset" = Relationship(back_populates="labels")
    data_row: "DataRow" = Relationship(back_populates="labels")
    import_record: "ImportRecord | None" = Relationship(back_populates="labels")
