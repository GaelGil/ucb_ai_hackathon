"""Controller for the research resource.

This is where HTTP routes attach (e.g. a FastAPI router). It delegates to
ResearchService and returns ResearchRead schemas. Wire it into your web app
once you add a framework.

The endpoint takes a language name and a type ("pos" or "translate"), runs the
research agent, and returns the stored research notes.
"""

from sqlmodel import Session

from app.api.research.service import ResearchService
from app.database.schemas.research import ResearchRead


class ResearchController:
    def __init__(self, session: Session):
        self.service = ResearchService(session)

    def research(self, language_name: str, type: str) -> ResearchRead:
        """Run research for a language + type and return the stored notes."""
        research = self.service.run_research(language_name, type)
        return ResearchRead.model_validate(research)

    def get(self, research_id: int) -> ResearchRead | None:
        research = self.service.get_research(research_id)
        return ResearchRead.model_validate(research) if research else None
