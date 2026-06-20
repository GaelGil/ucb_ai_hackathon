from pydantic import BaseModel, ConfigDict


class LabelCreate(BaseModel):
    name: str
    type: str
    value: str
    data_id: int


class LabelUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    value: str | None = None
    data_id: int | None = None


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    value: str
    data_id: int
