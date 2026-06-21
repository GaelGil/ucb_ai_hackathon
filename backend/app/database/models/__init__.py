"""SQLModel table definitions.

Importing every model here ensures they are all registered on
``SQLModel.metadata`` so Alembic autogenerate can see them.
"""

from app.database.models.data import Data, DataRow, DataSourceType, DataType
from app.database.models.dataset import Dataset
from app.database.models.import_record import ImportRecord, ImportStatus
from app.database.models.job import Job, JobStatus
from app.database.models.label import Label, LabelSource, LabelType
from app.database.models.language import Language
from app.database.models.research import Research, ResearchType
from app.database.models.suggestion import AiSuggestion, SuggestionStatus

__all__ = [
    "Language",
    "Dataset",
    "Data",
    "DataRow",
    "DataSourceType",
    "DataType",
    "ImportRecord",
    "ImportStatus",
    "Job",
    "JobStatus",
    "Label",
    "LabelSource",
    "LabelType",
    "Research",
    "ResearchType",
    "AiSuggestion",
    "SuggestionStatus",
]
