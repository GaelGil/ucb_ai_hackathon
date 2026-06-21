from typing import Any

from pydantic import BaseModel, ConfigDict

from app.src.database.models.data import DataSourceType
from app.src.database.models.import_record import ImportStatus


class ImportCreate(BaseModel):
    dataset_id: str
    source_type: DataSourceType
    status: ImportStatus = ImportStatus.pending
    filename: str | None = None
    content_type: str | None = None
    storage_bucket: str | None = None
    storage_path: str | None = None
    column_mapping: dict[str, Any] = {}


class ImportUpdate(BaseModel):
    status: ImportStatus | None = None
    filename: str | None = None
    content_type: str | None = None
    storage_bucket: str | None = None
    storage_path: str | None = None
    column_mapping: dict[str, Any] | None = None
    row_count: int | None = None
    label_count: int | None = None
    error: str | None = None


class ImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    source_type: DataSourceType
    status: ImportStatus
    filename: str | None
    content_type: str | None
    storage_bucket: str | None
    storage_path: str | None
    column_mapping: dict[str, Any]
    row_count: int
    label_count: int
    error: str | None
