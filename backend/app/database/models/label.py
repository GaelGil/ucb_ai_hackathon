from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.database.models.data import Data


class Label(SQLModel, table=True):
    __tablename__ = "labels"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: str
    value: str

    # Belongs to a data record.
    data_id: int = Field(foreign_key="data.id", index=True)
    data: "Data" = Relationship(back_populates="labels")
