"""SQLModel table definitions.

Importing every model here ensures they are all registered on
``SQLModel.metadata`` so Alembic autogenerate can see them.
"""

from app.database.models.language import Language
from app.database.models.dataset import Dataset
from app.database.models.data import Data, DataType
from app.database.models.label import Label, LabelType
from app.database.models.research import Research

__all__ = [
    "Language",
    "Dataset",
    "Data",
    "DataType",
    "Label",
    "LabelType",
    "Research",
]
