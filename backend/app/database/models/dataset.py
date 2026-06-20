from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.database.models.data import Data
    from app.database.models.label import Label
    from app.database.models.language import Language


class Dataset(SQLModel, table=True):
    __tablename__ = "datasets"

    id: int | None = Field(default=None, primary_key=True)

    # Belongs to a language.
    language_id: int = Field(foreign_key="languages.id", index=True)
    language: "Language" = Relationship(back_populates="datasets")

    # One dataset groups many data records and many labels.
    data: list["Data"] = Relationship(back_populates="dataset")
    labels: list["Label"] = Relationship(back_populates="dataset")
