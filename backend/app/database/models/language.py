from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.database.models.data import Data
    from app.database.models.dataset import Dataset
    from app.database.models.research import Research


class Language(SQLModel, table=True):
    __tablename__ = "languages"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    # One language has many data records.
    data: list["Data"] = Relationship(
        back_populates="language",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # One language has many datasets and research entries.
    datasets: list["Dataset"] = Relationship(back_populates="language")
    research: list["Research"] = Relationship(back_populates="language")
