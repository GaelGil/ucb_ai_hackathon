"""Business logic for the research resource.

The headline behavior is :meth:`ResearchService.run_research`, which runs the
research agent (Claude + the Browserbase researcher tool), then persists the
resulting notes as a ``Research`` row linked to the language.
"""

from sqlmodel import Session

from app.agents.research_agent import run_research as run_research_agent
from app.database.models.language import Language
from app.database.models.research import Research
from app.database.repositories.language import LanguageRepository
from app.database.repositories.research import ResearchRepository


class ResearchService:
    def __init__(self, session: Session):
        self.repository = ResearchRepository(session)
        self.languages = LanguageRepository(session)

    def _resolve_language(self, language_name: str) -> Language:
        """Find the language by name, creating it if it doesn't exist yet."""
        language = self.languages.get_by_name(language_name)
        if language is None:
            language = self.languages.create(Language(name=language_name))
        return language

    def run_research(self, language_name: str, type: str) -> Research:
        """Run the research agent for a language + type and store the notes.

        Args:
            language_name: Name of the language (e.g. "Tigrinya").
            type: ``"pos"`` or ``"translate"``.
        """
        # Run the agent FIRST. Only touch the database once it succeeds, so a
        # missing API key or a failed run never leaves a junk language row.
        notes = run_research_agent(language_name, type)

        language = self._resolve_language(language_name)
        research = Research(type=type, notes=notes, language_id=language.id)
        return self.repository.create(research)

    def get_research(self, research_id: int) -> Research | None:
        return self.repository.get(research_id)
