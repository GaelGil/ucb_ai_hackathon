"""Controller for the language resource.

This is where HTTP routes attach (e.g. a FastAPI router). It delegates to
LanguageService and returns LanguageRead schemas. Wire it into your web app
once you add a framework.
"""

from sqlmodel import Session

from app.api.language.service import LanguageService
from app.database.schemas.language import LanguageCreate, LanguageRead


class LanguageController:
    def __init__(self, session: Session):
        self.service = LanguageService(session)

    def create(self, payload: LanguageCreate) -> LanguageRead:
        language = self.service.create_language(payload)
        return LanguageRead.model_validate(language)

    def get(self, language_id: int) -> LanguageRead | None:
        language = self.service.get_language(language_id)
        return LanguageRead.model_validate(language) if language else None

    def list(self) -> list[LanguageRead]:
        return [LanguageRead.model_validate(lang) for lang in self.service.list_languages()]
