from pydantic import BaseModel, ConfigDict


class ResearchCreate(BaseModel):
    type: str
    notes: str | None = None
    language_id: int | None = None


class ResearchUpdate(BaseModel):
    type: str | None = None
    notes: str | None = None
    language_id: int | None = None


class ResearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    notes: str | None
    language_id: int | None
