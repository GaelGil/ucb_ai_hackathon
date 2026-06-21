import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, JSON, Text
from sqlmodel import Field, Relationship, SQLModel

from app.database.models.label import LabelType
from app.database.models.language import new_id, now_utc

if TYPE_CHECKING:
    from app.database.models.data_row import DataRow
    from app.database.models.dataset import Dataset
    from app.database.models.label import Label
    from app.database.models.research import Research


class SuggestionStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    denied = "denied"
    updated = "updated"


class AiSuggestion(SQLModel, table=True):
    __tablename__ = "ai_suggestions"

    id: str = Field(default_factory=lambda: new_id("sug"), primary_key=True)
    dataset_id: str = Field(foreign_key="datasets.id", index=True)
    data_row_id: str = Field(foreign_key="data_rows.id", index=True)
    research_id: str | None = Field(default=None, foreign_key="research.id", index=True)
    label_type: LabelType = Field(index=True)
    status: SuggestionStatus = Field(default=SuggestionStatus.pending, index=True)
    original_value: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    human_value: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    confidence: float = Field(default=0.0, ge=0, le=1)
    rationale: str = Field(default="", sa_column=Column(Text, nullable=False))
    model_name: str | None = Field(default=None, max_length=160)
    provider: str | None = Field(default=None, max_length=80)
    created_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
    reviewed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    dataset: "Dataset" = Relationship(back_populates="ai_suggestions")
    data_row: "DataRow" = Relationship(back_populates="ai_suggestions")
    research: "Research" = Relationship(back_populates="ai_suggestions")
    labels: list["Label"] = Relationship(back_populates="ai_suggestion")
