"""Business logic for the data resource.

The headline behavior is :meth:`DataService.get_more_data`, which runs the data
agent (Claude + the Browserbase search tool) to collect sentences in a language,
then saves each sentence as a text ``Data`` row grouped under a new ``Dataset``.
"""

from sqlmodel import Session

from app.agents.data_agent import run_get_more_data
from app.database.models.data import Data, DataType
from app.database.models.dataset import Dataset
from app.database.models.language import Language
from app.database.repositories.data import DataRepository
from app.database.repositories.dataset import DatasetRepository
from app.database.repositories.language import LanguageRepository


class DataService:
    def __init__(self, session: Session):
        self.session = session
        self.data = DataRepository(session)
        self.datasets = DatasetRepository(session)
        self.languages = LanguageRepository(session)

    def _resolve_language(self, language_name: str) -> Language:
        """Find the language by name, creating it if it doesn't exist yet."""
        language = self.languages.get_by_name(language_name)
        if language is None:
            language = self.languages.create(Language(name=language_name))
        return language

    def get_more_data(self, language_name: str) -> list[Data]:
        """Gather sentences in a language and persist them as a new dataset.

        Returns the created ``Data`` rows (one per sentence).
        """
        # Run the agent FIRST. Only touch the database once it succeeds, so a
        # missing API key, a failed run, or an empty result never leaves a junk
        # language/dataset row.
        sentences = run_get_more_data(language_name)
        if not sentences:
            return []

        language = self._resolve_language(language_name)
        # Group this batch of sentences under a fresh dataset for the language.
        dataset = self.datasets.create(Dataset(language_id=language.id))

        created: list[Data] = []
        for sentence in sentences:
            row = Data(
                name=sentence,
                type=DataType.text,
                language_id=language.id,
                dataset_id=dataset.id,
            )
            created.append(self.data.create(row))
        return created
