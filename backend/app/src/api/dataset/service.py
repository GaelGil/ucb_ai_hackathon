from __future__ import annotations

from app.src.models import Dashboard, Dataset, DatasetCreate, Job
from app.src.repositories import InMemoryRepository


class DatasetService:
    def __init__(self, repository: InMemoryRepository) -> None:
        self.repository = repository

    def create_dataset(self, payload: DatasetCreate) -> Dataset:
        dataset = Dataset(**payload.model_dump())
        return self.repository.create_dataset(dataset)

    def list_datasets(self) -> list[Dataset]:
        return self.repository.list_datasets()

    def get_dashboard(self, dataset_id: str) -> Dashboard:
        return self.repository.dashboard(dataset_id)

    def get_job(self, job_id: str) -> Job:
        return self.repository.get_job(job_id)
