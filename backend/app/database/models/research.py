from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.database.models.language import Language


class Research(SQLModel, table=True):
    __tablename__ = "research"

    id: int | None = Field(default=None, primary_key=True)
    type: str = Field(index=True)
    # Notes can be long, so store as TEXT rather than a length-limited VARCHAR.
    notes: str | None = Field(default=None, sa_column=Column(Text))

    # Optionally belongs to a language.
    language_id: int | None = Field(default=None, foreign_key="languages.id", index=True)
    language: Optional["Language"] = Relationship(back_populates="research")
