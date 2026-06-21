from sqlmodel import Session, select

from app.src.database.models.data import Data


class DataRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: Data) -> Data:
        self.session.add(data)
        self.session.commit()
        self.session.refresh(data)
        return data

    def get(self, data_row_id: str) -> Data | None:
        return self.session.get(Data, data_row_id)

    def list_by_dataset(self, dataset_id: str) -> list[Data]:
        statement = select(Data).where(Data.dataset_id == dataset_id)
        return list(self.session.exec(statement).all())

    def _list(self, offset: int = 0, limit: int = 100) -> list[Data]:
        statement = select(Data).offset(offset).limit(limit)
        return list(self.session.exec(statement).all())

    def delete(self, data: Data) -> None:
        self.session.delete(data)
        self.session.commit()
