from sqlmodel import Session, select

from app.database.models.dataset import Dataset


class DatasetRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, dataset: Dataset) -> Dataset:
        self.session.add(dataset)
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

    def get(self, dataset_id: int) -> Dataset | None:
        return self.session.get(Dataset, dataset_id)

    def list_by_language(self, language_id: int) -> list[Dataset]:
        statement = select(Dataset).where(Dataset.language_id == language_id)
        return list(self.session.exec(statement).all())

    def _list(self, offset: int = 0, limit: int = 100) -> list[Dataset]:
        statement = select(Dataset).offset(offset).limit(limit)
        return list(self.session.exec(statement).all())

    def delete(self, dataset: Dataset) -> None:
        self.session.delete(dataset)
        self.session.commit()
