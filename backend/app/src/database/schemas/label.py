from typing import Any

from pydantic import BaseModel, ConfigDict

from app.src.database.models.label import LabelSource, LabelType


class LabelCreate(BaseModel):
    dataset_id: str
    data_row_id: str
    import_id: str | None = None
    ai_suggestion_id: str | None = None
    type: LabelType
    name: str | None = None
    value: dict[str, Any]
    source: LabelSource = LabelSource.human
    original_column_name: str | None = None


class LabelUpdate(BaseModel):
    type: LabelType | None = None
    name: str | None = None
    value: dict[str, Any] | None = None
    source: LabelSource | None = None
    original_column_name: str | None = None


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    data_row_id: str
    import_id: str | None
    ai_suggestion_id: str | None
    type: LabelType
    name: str | None
    value: dict[str, Any]
    source: LabelSource
    original_column_name: str | None
