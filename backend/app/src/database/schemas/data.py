from pydantic import BaseModel, ConfigDict

from app.src.database.models.data import DataType


class DataCreate(BaseModel):
    name: str
    type: DataType
    language_id: int
    dataset_id: int | None = None


class DataUpdate(BaseModel):
    name: str | None = None
    type: DataType | None = None
    language_id: int | None = None
    dataset_id: int | None = None


class DataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: DataType
    language_id: int
    dataset_id: int | None
