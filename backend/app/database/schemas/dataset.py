from pydantic import BaseModel, ConfigDict


class DatasetCreate(BaseModel):
    language_id: int


class DatasetUpdate(BaseModel):
    language_id: int | None = None


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    language_id: int
