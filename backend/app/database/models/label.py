import enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.database.models.data import Data
    from app.database.models.dataset import Dataset


class LabelType(str, enum.Enum):
    pos = "pos"
    ocr = "ocr"
    text = "text"


class Label(SQLModel, table=True):
    __tablename__ = "labels"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: LabelType
    value: str

    # Belongs to a data record.
    data_id: int = Field(foreign_key="data.id", index=True)
    data: "Data" = Relationship(back_populates="labels")

    # Optionally belongs to a dataset.
    dataset_id: int | None = Field(default=None, foreign_key="datasets.id", index=True)
    dataset: Optional["Dataset"] = Relationship(back_populates="labels")
