from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.src.database.models.label import LabelType
from app.src.database.models.suggestion import SuggestionStatus


class AiSuggestionCreate(BaseModel):
    dataset_id: str
    data_row_id: str
    research_id: str | None = None
    label_type: LabelType
    original_value: dict[str, Any]
    human_value: dict[str, Any] | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    rationale: str = ""
    model_name: str | None = None
    provider: str | None = None


class AiSuggestionUpdate(BaseModel):
    status: SuggestionStatus | None = None
    human_value: dict[str, Any] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    rationale: str | None = None


class AiSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    data_row_id: str
    research_id: str | None
    label_type: LabelType
    status: SuggestionStatus
    original_value: dict[str, Any]
    human_value: dict[str, Any] | None
    confidence: float
    rationale: str
    model_name: str | None
    provider: str | None
