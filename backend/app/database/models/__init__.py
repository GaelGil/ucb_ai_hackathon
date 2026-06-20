"""SQLModel table definitions.

Importing every model here ensures they are all registered on
``SQLModel.metadata`` so Alembic autogenerate can see them.
"""

from app.database.models.language import Language
from app.database.models.data import Data, DataType
from app.database.models.label import Label

__all__ = ["Language", "Data", "DataType", "Label"]
