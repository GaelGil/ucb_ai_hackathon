from __future__ import annotations

from collections import Counter
from threading import RLock

from app.models import (
    Dashboard,
    Dataset,
    ImportRecord,
    Job,
    JobStatus,
    PosModelState,
    ResearchArtifact,
    SourceType,
    Suggestion,
    SuggestionStatus,
    SuggestionType,
    TextItem,
    UploadedAsset,
    now_utc,
)


class NotFoundError(ValueError):
    pass


class InMemoryRepository:
    """Repository boundary used until the database models are ready."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.datasets: dict[str, Dataset] = {}
        self.imports: dict[str, ImportRecord] = {}
        self.items: dict[str, TextItem] = {}
        self.assets: dict[str, UploadedAsset] = {}
        self.research: dict[tuple[str, str], ResearchArtifact] = {}
        self.suggestions: dict[str, Suggestion] = {}
        self.jobs: dict[str, Job] = {}
        self.pos_models: dict[str, PosModelState] = {}

    def create_dataset(self, dataset: Dataset) -> Dataset:
        with self._lock:
            self.datasets[dataset.id] = dataset
            self.pos_models[dataset.id] = PosModelState(dataset_id=dataset.id)
            return dataset

    def list_datasets(self) -> list[Dataset]:
        with self._lock:
            return sorted(self.datasets.values(), key=lambda item: item.created_at)

    def get_dataset(self, dataset_id: str) -> Dataset:
        with self._lock:
            dataset = self.datasets.get(dataset_id)
            if dataset is None:
                raise NotFoundError(f"Dataset {dataset_id} was not found.")
            return dataset

    def add_import(self, record: ImportRecord) -> ImportRecord:
        with self._lock:
            self._ensure_dataset(record.dataset_id)
            self.imports[record.id] = record
            return record

    def update_import(self, record: ImportRecord) -> ImportRecord:
        with self._lock:
            self.imports[record.id] = record
            return record

    def get_import(self, import_id: str) -> ImportRecord:
        with self._lock:
            record = self.imports.get(import_id)
            if record is None:
                raise NotFoundError(f"Import {import_id} was not found.")
            return record

    def list_imports(self, dataset_id: str) -> list[ImportRecord]:
        with self._lock:
            return sorted(
                [record for record in self.imports.values() if record.dataset_id == dataset_id],
                key=lambda item: item.created_at,
                reverse=True,
            )

    def add_items(self, items: list[TextItem]) -> list[TextItem]:
        with self._lock:
            for item in items:
                self._ensure_dataset(item.dataset_id)
                self.items[item.id] = item
            return items

    def list_items(self, dataset_id: str) -> list[TextItem]:
        with self._lock:
            return sorted(
                [item for item in self.items.values() if item.dataset_id == dataset_id],
                key=lambda item: item.created_at,
            )

    def add_asset(self, asset: UploadedAsset) -> UploadedAsset:
        with self._lock:
            self._ensure_dataset(asset.dataset_id)
            self.assets[asset.id] = asset
            return asset

    def list_assets_for_import(self, import_id: str) -> list[UploadedAsset]:
        with self._lock:
            return [asset for asset in self.assets.values() if asset.import_id == import_id]

    def get_research(self, dataset_id: str, language_code: str) -> ResearchArtifact | None:
        with self._lock:
            return self.research.get((dataset_id, language_code))

    def save_research(self, artifact: ResearchArtifact) -> ResearchArtifact:
        with self._lock:
            artifact.updated_at = now_utc()
            self.research[(artifact.dataset_id, artifact.language_code)] = artifact
            return artifact

    def add_suggestion(self, suggestion: Suggestion) -> Suggestion:
        with self._lock:
            self.suggestions[suggestion.id] = suggestion
            return suggestion

    def get_suggestion(self, suggestion_id: str) -> Suggestion:
        with self._lock:
            suggestion = self.suggestions.get(suggestion_id)
            if suggestion is None:
                raise NotFoundError(f"Suggestion {suggestion_id} was not found.")
            return suggestion

    def update_suggestion(self, suggestion: Suggestion) -> Suggestion:
        with self._lock:
            self.suggestions[suggestion.id] = suggestion
            return suggestion

    def list_suggestions(
        self,
        dataset_id: str,
        suggestion_type: SuggestionType | None = None,
        status: SuggestionStatus | None = None,
        limit: int | None = None,
    ) -> list[Suggestion]:
        with self._lock:
            suggestions = [item for item in self.suggestions.values() if item.dataset_id == dataset_id]
            if suggestion_type is not None:
                suggestions = [item for item in suggestions if item.type == suggestion_type]
            if status is not None:
                suggestions = [item for item in suggestions if item.status == status]
            suggestions = sorted(suggestions, key=lambda item: item.created_at)
            return suggestions[:limit] if limit else suggestions

    def item_has_pos_suggestion(self, item_id: str) -> bool:
        with self._lock:
            return any(
                suggestion.item_id == item_id and suggestion.type == SuggestionType.POS
                for suggestion in self.suggestions.values()
            )

    def count_accepted_pos_suggestions(self, dataset_id: str) -> int:
        with self._lock:
            return sum(
                1
                for suggestion in self.suggestions.values()
                if suggestion.dataset_id == dataset_id
                and suggestion.type == SuggestionType.POS
                and suggestion.status in {SuggestionStatus.APPROVED, SuggestionStatus.EDITED}
            )

    def create_job(self, job: Job) -> Job:
        with self._lock:
            self.jobs[job.id] = job
            return job

    def get_job(self, job_id: str) -> Job:
        with self._lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise NotFoundError(f"Job {job_id} was not found.")
            return job

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress: int | None = None,
        message: str | None = None,
        error: str | None = None,
        metadata: dict | None = None,
    ) -> Job:
        with self._lock:
            job = self.get_job(job_id)
            updated = job.model_copy(
                update={
                    "status": status if status is not None else job.status,
                    "progress": progress if progress is not None else job.progress,
                    "message": message if message is not None else job.message,
                    "error": error,
                    "metadata": metadata if metadata is not None else job.metadata,
                    "updated_at": now_utc(),
                }
            )
            self.jobs[job_id] = updated
            return updated

    def get_pos_model(self, dataset_id: str) -> PosModelState:
        with self._lock:
            self._ensure_dataset(dataset_id)
            return self.pos_models.setdefault(dataset_id, PosModelState(dataset_id=dataset_id))

    def save_pos_model(self, model: PosModelState) -> PosModelState:
        with self._lock:
            model.updated_at = now_utc()
            self.pos_models[model.dataset_id] = model
            return model

    def dashboard(self, dataset_id: str) -> Dashboard:
        dataset = self.get_dataset(dataset_id)
        suggestions = self.list_suggestions(dataset_id)
        counts = Counter(f"{item.type}:{item.status}" for item in suggestions)
        return Dashboard(
            dataset=dataset,
            imports=self.list_imports(dataset_id),
            research=self.get_research(dataset.id, dataset.language_code),
            suggestion_counts=dict(counts),
            item_count=len(self.list_items(dataset_id)),
            pos_model=self.get_pos_model(dataset_id),
        )

    def seed_demo_dataset(self) -> Dataset:
        with self._lock:
            if self.datasets:
                return next(iter(self.datasets.values()))
            dataset = self.create_dataset(
                Dataset(name="Nahuatl preservation demo", language_code="nah", language_name="Nahuatl")
            )
            record = self.add_import(ImportRecord(dataset_id=dataset.id, source_type=SourceType.TEXT, item_count=5))
            self.add_items(
                [
                    TextItem(dataset_id=dataset.id, import_id=record.id, text="muchas flores son blancas"),
                    TextItem(dataset_id=dataset.id, import_id=record.id, text="la casa grande esta cerca"),
                    TextItem(dataset_id=dataset.id, import_id=record.id, text="el agua corre rapido"),
                    TextItem(dataset_id=dataset.id, import_id=record.id, text="mi familia habla nahuatl"),
                    TextItem(dataset_id=dataset.id, import_id=record.id, text="los ninos aprenden palabras"),
                ]
            )
            return dataset

    def _ensure_dataset(self, dataset_id: str) -> None:
        if dataset_id not in self.datasets:
            raise NotFoundError(f"Dataset {dataset_id} was not found.")
