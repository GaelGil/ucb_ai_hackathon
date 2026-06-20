from pydantic import BaseModel, ConfigDict

from app.src.database.models.label import LabelType


class LabelCreate(BaseModel):
    name: str
    type: LabelType
    value: str
    data_id: int
    dataset_id: int | None = None


class LabelUpdate(BaseModel):
    name: str | None = None
    type: LabelType | None = None
    value: str | None = None
    data_id: int | None = None
    dataset_id: int | None = None


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: LabelType
    value: str
    data_id: int
    dataset_id: int | None
