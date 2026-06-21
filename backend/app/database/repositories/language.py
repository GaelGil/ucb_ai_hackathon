from sqlmodel import Session, select

from app.database.models.language import Language


class LanguageRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, language: Language) -> Language:
        self.session.add(language)
        self.session.commit()
        self.session.refresh(language)
        return language

    def get(self, language_id: int) -> Language | None:
        return self.session.get(Language, language_id)

    def get_by_name(self, name: str) -> Language | None:
        statement = select(Language).where(Language.name == name)
        return self.session.exec(statement).first()

    def list(self, offset: int = 0, limit: int = 100) -> list[Language]:
        statement = select(Language).offset(offset).limit(limit)
        return list(self.session.exec(statement).all())

    def delete(self, language: Language) -> None:
        self.session.delete(language)
        self.session.commit()
