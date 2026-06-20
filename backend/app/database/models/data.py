from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.database.models.label import Label
    from app.database.models.language import Language


class DataType(str, enum.Enum):
    text = "text"
    image = "image"
    audio = "audio"


class Data(SQLModel, table=True):
    __tablename__ = "data"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: DataType

    # Belongs to a language.
    language_id: int = Field(foreign_key="languages.id", index=True)
    language: "Language" = Relationship(back_populates="data")

    # One data record has many labels.
    labels: list["Label"] = Relationship(
        back_populates="data",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
