from sqlmodel import Session, select

from app.src.database.models.research import Research


class ResearchRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, research: Research) -> Research:
        self.session.add(research)
        self.session.commit()
        self.session.refresh(research)
        return research

    def get(self, research_id: str) -> Research | None:
        return self.session.get(Research, research_id)

    def _list(self, offset: int = 0, limit: int = 100) -> list[Research]:
        statement = select(Research).offset(offset).limit(limit)
        return list(self.session.exec(statement).all())

    def delete(self, research: Research) -> None:
        self.session.delete(research)
        self.session.commit()
