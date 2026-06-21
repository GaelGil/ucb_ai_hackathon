from pydantic import BaseModel, ConfigDict


class DatasetCreate(BaseModel):
    language_id: str
    name: str
    description: str | None = None


class DatasetUpdate(BaseModel):
    language_id: str | None = None
    name: str | None = None
    description: str | None = None


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    language_id: str
    name: str
    description: str | None
