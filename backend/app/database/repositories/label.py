from sqlmodel import Session, select

from app.database.models.label import Label


class LabelRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, label: Label) -> Label:
        self.session.add(label)
        self.session.commit()
        self.session.refresh(label)
        return label

    def get(self, label_id: int) -> Label | None:
        return self.session.get(Label, label_id)

    def list_by_data(self, data_id: int) -> list[Label]:
        statement = select(Label).where(Label.data_id == data_id)
        return list(self.session.exec(statement).all())

    def delete(self, label: Label) -> None:
        self.session.delete(label)
        self.session.commit()
