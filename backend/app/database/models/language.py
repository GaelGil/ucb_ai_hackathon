from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.database.models.data import Data


class Language(SQLModel, table=True):
    __tablename__ = "languages"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    # One language has many data records.
    data: list["Data"] = Relationship(
        back_populates="language",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
