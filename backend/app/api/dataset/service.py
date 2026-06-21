from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from app.api.mappers import dataset_to_api, import_to_api, job_to_api, research_to_api, suggestion_status_to_api
from app.database.models import AiSuggestion, DataRow, Dataset, ImportRecord, Job, Label, Language, Research
from app.database.models.data import DataSourceType
from app.database.models.job import JobStatus as DbJobStatus
from app.database.models.label import LabelSource, LabelType
from app.database.models.research import ResearchType
from app.models import Dashboard, DatasetCreate, Job as ApiJob
from app.models import Dataset as ApiDataset
from app.models import PosModelState, PosModelStatus
from app.repositories import NotFoundError


class DatasetService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_dataset(self, payload: DatasetCreate) -> ApiDataset:
        language = self.session.exec(select(Language).where(Language.code == payload.language_code)).first()
        if language is None:
            language = Language(code=payload.language_code, name=payload.language_name)
            self.session.add(language)
            self.session.flush()
        elif language.name != payload.language_name:
            language.name = payload.language_name

        dataset = Dataset(name=payload.name, language_id=language.id)
        self.session.add(dataset)
        self.session.commit()
        self.session.refresh(dataset)
        self.session.refresh(language)
        return dataset_to_api(dataset, language)

    def list_datasets(self) -> list[ApiDataset]:
        datasets = self.session.exec(select(Dataset).order_by(Dataset.created_at)).all()
        return [dataset_to_api(dataset) for dataset in datasets]

    def delete_dataset(self, dataset_id: str) -> None:
        dataset = self._get_dataset(dataset_id)
        jobs = self.session.exec(select(Job)).all()
        for job in jobs:
            if job.job_metadata.get("dataset_id") == dataset_id:
                self.session.delete(job)
        self.session.delete(dataset)
        self.session.commit()

    def get_dashboard(self, dataset_id: str) -> Dashboard:
        return self._with_operational_retry(lambda: self._get_dashboard(dataset_id))

    def _get_dashboard(self, dataset_id: str) -> Dashboard:
        dataset = self._get_dataset(dataset_id)
        imports = self.session.exec(
            select(ImportRecord).where(ImportRecord.dataset_id == dataset.id).order_by(ImportRecord.created_at.desc())
        ).all()
        item_count = self.session.exec(
            select(func.count()).select_from(DataRow).where(DataRow.dataset_id == dataset.id)
        ).one()
        research = self.session.exec(
            select(Research)
            .where(Research.language_id == dataset.language_id)
            .where(Research.type == ResearchType.pos)
            .order_by(Research.updated_at.desc())
        ).first()
        suggestion_counts = self.session.exec(
            select(AiSuggestion.label_type, AiSuggestion.status, func.count())
            .where(AiSuggestion.dataset_id == dataset.id)
            .group_by(AiSuggestion.label_type, AiSuggestion.status)
        ).all()
        counts = {
            f"{label_type.value}:{suggestion_status_to_api(status).value}": count
            for label_type, status, count in suggestion_counts
        }
        return Dashboard(
            dataset=dataset_to_api(dataset),
            imports=[import_to_api(record) for record in imports],
            research=research_to_api(dataset, dataset.language, research) if research else None,
            suggestion_counts=counts,
            item_count=item_count,
            pos_model=self._get_pos_model(dataset.id),
        )

    def get_job(self, job_id: str) -> ApiJob:
        job = self.session.get(Job, job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} was not found.")
        return job_to_api(job)

    def seed_demo_dataset(self) -> ApiDataset:
        existing = self.session.exec(select(Dataset).order_by(Dataset.created_at)).first()
        if existing is not None:
            return dataset_to_api(existing)

        language = Language(code="nah", name="Nahuatl")
        self.session.add(language)
        self.session.flush()
        dataset = Dataset(name="Nahuatl preservation demo", language_id=language.id)
        self.session.add(dataset)
        self.session.flush()
        record = ImportRecord(dataset_id=dataset.id, source_type=DataSourceType.text, row_count=5)
        self.session.add(record)
        self.session.flush()
        for index, text in enumerate(
            [
                "muchas flores son blancas",
                "la casa grande esta cerca",
                "el agua corre rapido",
                "mi familia habla nahuatl",
                "los ninos aprenden palabras",
            ]
        ):
            self.session.add(
                DataRow(
                    dataset_id=dataset.id,
                    import_id=record.id,
                    row_index=index,
                    source_type=DataSourceType.text,
                    text_content=text,
                )
            )
        self.session.commit()
        self.session.refresh(dataset)
        return dataset_to_api(dataset, language)

    def _get_dataset(self, dataset_id: str) -> Dataset:
        dataset = self.session.get(Dataset, dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset {dataset_id} was not found.")
        return dataset

    def _get_pos_model(self, dataset_id: str) -> PosModelState:
        accepted_count = self.session.exec(
            select(func.count())
            .select_from(Label)
            .where(Label.dataset_id == dataset_id)
            .where(Label.type == LabelType.pos)
            .where(
                Label.source.in_(
                    [
                        LabelSource.human,
                        LabelSource.ai_accepted,
                        LabelSource.ai_updated,
                        LabelSource.csv_import,
                    ]
                )
            )
        ).one()
        jobs = self.session.exec(
            select(Job)
            .where(Job.type == "pos_model_training")
            .where(Job.status == DbJobStatus.succeeded)
            .order_by(Job.updated_at.desc())
        ).all()
        for job in jobs:
            if job.job_metadata.get("dataset_id") == dataset_id and job.job_metadata.get("pos_model"):
                return PosModelState.model_validate(job.job_metadata["pos_model"])
        return PosModelState(
            dataset_id=dataset_id,
            status=PosModelStatus.NOT_STARTED,
            accepted_sentence_count=accepted_count,
            minimum_examples_met=accepted_count >= 20,
        )

    def _with_operational_retry(self, callback):
        try:
            return callback()
        except OperationalError:
            self.session.rollback()
            return callback()
