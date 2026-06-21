import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, JSON, Text
from sqlmodel import Field, Relationship, SQLModel

from app.src.database.models.language import new_id, now_utc

if TYPE_CHECKING:
    from app.src.database.models.language import Language
    from app.src.database.models.suggestion import AiSuggestion


class ResearchType(str, enum.Enum):
    ocr = "ocr"
    pos = "pos"
    translation = "translation"
    grammar = "grammar"
    custom = "custom"


class Research(SQLModel, table=True):
    __tablename__ = "research"

    id: str = Field(default_factory=lambda: new_id("research"), primary_key=True)
    language_id: str = Field(foreign_key="languages.id", index=True)
    type: ResearchType = Field(index=True)
    notes: str | None = Field(default=None, sa_column=Column(Text))
    sources: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    research_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON, nullable=False))
    created_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))

    language: "Language" = Relationship(back_populates="research")
    ai_suggestions: list["AiSuggestion"] = Relationship(back_populates="research")
