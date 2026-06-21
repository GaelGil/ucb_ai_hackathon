from typing import Any

from pydantic import BaseModel, ConfigDict


class LanguageCreate(BaseModel):
    code: str
    name: str
    details: dict[str, Any] = {}


class LanguageUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    details: dict[str, Any] | None = None


class LanguageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    details: dict[str, Any]
