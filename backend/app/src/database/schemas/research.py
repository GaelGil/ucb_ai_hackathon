from typing import Any

from pydantic import BaseModel, ConfigDict

from app.src.database.models.research import ResearchType


class ResearchCreate(BaseModel):
    language_id: str
    type: ResearchType
    notes: str | None = None
    sources: list[dict[str, Any]] = []
    research_metadata: dict[str, Any] = {}


class ResearchUpdate(BaseModel):
    type: ResearchType | None = None
    notes: str | None = None
    sources: list[dict[str, Any]] | None = None
    research_metadata: dict[str, Any] | None = None


class ResearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    language_id: str
    type: ResearchType
    notes: str | None
    sources: list[dict[str, Any]]
    research_metadata: dict[str, Any]
