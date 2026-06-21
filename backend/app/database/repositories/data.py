from sqlmodel import Session, select

from app.database.models.data import Data


class DataRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: Data) -> Data:
        self.session.add(data)
        self.session.commit()
        self.session.refresh(data)
        return data

    def get(self, data_id: int) -> Data | None:
        return self.session.get(Data, data_id)

    def list_by_language(self, language_id: int) -> list[Data]:
        statement = select(Data).where(Data.language_id == language_id)
        return list(self.session.exec(statement).all())

    def list(self, offset: int = 0, limit: int = 100) -> list[Data]:
        statement = select(Data).offset(offset).limit(limit)
        return list(self.session.exec(statement).all())

    def delete(self, data: Data) -> None:
        self.session.delete(data)
        self.session.commit()
