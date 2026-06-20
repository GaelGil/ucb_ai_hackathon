from __future__ import annotations

from app.src.jobs import JobRunner
from app.src.models import (
    ImportRecord,
    Job,
    SourceType,
    Suggestion,
    SuggestionType,
    TextItem,
    UploadedAsset,
)
from app.src.parsing import parse_text_items
from app.src.providers import OCRProvider
from app.src.repositories import InMemoryRepository


class DataService:
    def __init__(self, repository: InMemoryRepository, ocr_provider: OCRProvider, jobs: JobRunner) -> None:
        self.repository = repository
        self.ocr_provider = ocr_provider
        self.jobs = jobs

    def import_text(
        self,
        dataset_id: str,
        *,
        text: str,
        source_type: SourceType,
        filename: str | None = None,
    ) -> tuple[ImportRecord, Job, list[TextItem]]:
        dataset = self.repository.get_dataset(dataset_id)
        record = self.repository.add_import(ImportRecord(dataset_id=dataset.id, source_type=source_type, filename=filename))
        created_items: list[TextItem] = []

        def callback(job: Job) -> dict:
            del job
            values = parse_text_items(text, source_type)
            created_items.extend(
                TextItem(dataset_id=dataset.id, import_id=record.id, text=value, source_type=source_type) for value in values
            )
            self.repository.add_items(created_items)
            updated = record.model_copy(update={"item_count": len(created_items), "status": "ready"})
            self.repository.update_import(updated)
            return {"dataset_id": dataset.id, "import_id": record.id, "item_count": len(created_items)}

        job = self.jobs.run("import", callback)
        return self.repository.get_import(record.id), job, created_items

    def import_asset(
        self,
        dataset_id: str,
        *,
        data: bytes,
        source_type: SourceType,
        filename: str,
        content_type: str | None,
    ) -> tuple[ImportRecord, Job]:
        dataset = self.repository.get_dataset(dataset_id)
        record = self.repository.add_import(
            ImportRecord(dataset_id=dataset.id, source_type=source_type, filename=filename, asset_count=1)
        )

        def callback(job: Job) -> dict:
            del job
            self.repository.add_asset(
                UploadedAsset(
                    dataset_id=dataset.id,
                    import_id=record.id,
                    source_type=source_type,
                    filename=filename,
                    content_type=content_type,
                    data=data,
                )
            )
            return {"dataset_id": dataset.id, "import_id": record.id, "asset_count": 1}

        job = self.jobs.run("import_asset", callback)
        return self.repository.get_import(record.id), job

    def create_ocr_suggestions(self, dataset_id: str, import_id: str | None = None) -> tuple[list[Suggestion], Job]:
        dataset = self.repository.get_dataset(dataset_id)
        created: list[Suggestion] = []

        def callback(job: Job) -> dict:
            del job
            imports = [self.repository.get_import(import_id)] if import_id else self.repository.list_imports(dataset.id)
            assets = []
            for record in imports:
                assets.extend(self.repository.list_assets_for_import(record.id))
            for asset in assets:
                text, confidence, rationale = self.ocr_provider.extract(asset)
                created.append(
                    self.repository.add_suggestion(
                        Suggestion(
                            dataset_id=dataset.id,
                            import_id=asset.import_id,
                            type=SuggestionType.OCR,
                            original_text=asset.filename,
                            suggested_text=text,
                            confidence=confidence,
                            rationale=rationale,
                        )
                    )
                )
            return {"dataset_id": dataset.id, "created_count": len(created)}

        job = self.jobs.run("ocr", callback)
        return created, job
