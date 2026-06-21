from sqlmodel import Session, select

from app.src.database.models.label import Label


class LabelRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, label: Label) -> Label:
        self.session.add(label)
        self.session.commit()
        self.session.refresh(label)
        return label

    def get(self, label_id: str) -> Label | None:
        return self.session.get(Label, label_id)

    def list_by_data(self, data_row_id: str) -> list[Label]:
        statement = select(Label).where(Label.data_row_id == data_row_id)
        return list(self.session.exec(statement).all())

    def delete(self, label: Label) -> None:
        self.session.delete(label)
        self.session.commit()
