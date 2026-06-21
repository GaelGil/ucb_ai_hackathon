"""Controller for the data resource.

This is where HTTP routes attach (e.g. a FastAPI router). It delegates to
DataService and returns DataRead schemas. Wire it into your web app once you
add a framework.

The `get_more_data` endpoint takes a language name, runs the data agent to
collect sentences in that language from the web, saves them, and returns the
created data records.
"""

from sqlmodel import Session

from app.api.data.service import DataService
from app.database.schemas.data import DataRead


class DataController:
    def __init__(self, session: Session):
        self.service = DataService(session)

    def get_more_data(self, language_name: str) -> list[DataRead]:
        """Collect sentences for a language and return the stored data rows."""
        rows = self.service.get_more_data(language_name)
        return [DataRead.model_validate(row) for row in rows]
