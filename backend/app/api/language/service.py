from sqlmodel import Session

from app.database.models.language import Language
from app.database.repositories.language import LanguageRepository
from app.database.schemas.language import LanguageCreate


class LanguageService:
    """Business logic for languages, sitting on top of the repository."""

    def __init__(self, session: Session):
        self.repository = LanguageRepository(session)

    def create_language(self, payload: LanguageCreate) -> Language:
        language = Language(name=payload.name)
        return self.repository.create(language)

    def get_language(self, language_id: int) -> Language | None:
        return self.repository.get(language_id)

    def list_languages(self) -> list[Language]:
        return self.repository.list()
