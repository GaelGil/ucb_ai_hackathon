from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

from app.database.models.language import new_id, now_utc

if TYPE_CHECKING:
    from app.database.models.data_row import DataRow
    from app.database.models.import_record import ImportRecord
    from app.database.models.label import Label
    from app.database.models.language import Language
    from app.database.models.suggestion import AiSuggestion


class Dataset(SQLModel, table=True):
    __tablename__ = "datasets"

    id: str = Field(default_factory=lambda: new_id("ds"), primary_key=True)
    language_id: str = Field(foreign_key="languages.id", index=True)
    name: str = Field(index=True, max_length=160)
    description: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))

    language: "Language" = Relationship(back_populates="datasets")
    imports: list["ImportRecord"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    data_rows: list["DataRow"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    labels: list["Label"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    ai_suggestions: list["AiSuggestion"] = Relationship(
        back_populates="dataset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
