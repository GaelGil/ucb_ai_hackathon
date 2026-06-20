from pydantic import BaseModel, ConfigDict


class LanguageCreate(BaseModel):
    name: str


class LanguageUpdate(BaseModel):
    name: str | None = None


class LanguageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
