from typing import Any

from pydantic import BaseModel, ConfigDict

from app.src.database.models.data import DataSourceType


class DataCreate(BaseModel):
    dataset_id: str
    import_id: str | None = None
    row_index: int = 0
    source_type: DataSourceType
    text_content: str | None = None
    storage_bucket: str | None = None
    storage_path: str | None = None
    page_number: int | None = None
    row_metadata: dict[str, Any] = {}


class DataUpdate(BaseModel):
    row_index: int | None = None
    source_type: DataSourceType | None = None
    text_content: str | None = None
    storage_bucket: str | None = None
    storage_path: str | None = None
    page_number: int | None = None
    row_metadata: dict[str, Any] | None = None


class DataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    import_id: str | None
    row_index: int
    source_type: DataSourceType
    text_content: str | None
    storage_bucket: str | None
    storage_path: str | None
    page_number: int | None
    row_metadata: dict[str, Any]
