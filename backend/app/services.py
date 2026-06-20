from __future__ import annotations

from collections.abc import Callable

from app.models import (
    Dataset,
    DatasetCreate,
    ImportRecord,
    Job,
    JobStatus,
    PosModelState,
    PosModelStatus,
    PosTrainingRequest,
    ResearchArtifact,
    SourceType,
    Suggestion,
    SuggestionReview,
    SuggestionStatus,
    SuggestionType,
    TextItem,
    UploadedAsset,
    now_utc,
)
from app.parsing import parse_text_items
from app.providers import BrowserbaseResearchProvider, OCRProvider, PosAnnotationProvider, TranslationProvider
from app.repositories import InMemoryRepository
from app.tracing import Tracer


class JobRunner:
    def __init__(self, repository: InMemoryRepository, tracer: Tracer) -> None:
        self.repository = repository
        self.tracer = tracer

    def run(self, job_type: str, callback: Callable[[Job], dict | None]) -> Job:
        job = self.repository.create_job(Job(type=job_type))
        self.repository.update_job(job.id, status=JobStatus.RUNNING, progress=5, message="Started")
        try:
            with self.tracer.span("job.run", job_id=job.id, job_type=job_type):
                metadata = callback(job) or {}
            return self.repository.update_job(
                job.id,
                status=JobStatus.SUCCEEDED,
                progress=100,
                message="Completed",
                metadata={**self.repository.get_job(job.id).metadata, **metadata},
            )
        except Exception as exc:
            return self.repository.update_job(
                job.id,
                status=JobStatus.FAILED,
                progress=100,
                message="Failed",
                error=str(exc),
            )


class DatasetService:
    def __init__(
        self,
        repository: InMemoryRepository,
        research_provider: BrowserbaseResearchProvider,
        pos_provider: PosAnnotationProvider,
        ocr_provider: OCRProvider,
        translation_provider: TranslationProvider,
        tracer: Tracer,
    ) -> None:
        self.repository = repository
        self.research_provider = research_provider
        self.pos_provider = pos_provider
        self.ocr_provider = ocr_provider
        self.translation_provider = translation_provider
        self.tracer = tracer
        self.jobs = JobRunner(repository, tracer)

    def create_dataset(self, payload: DatasetCreate) -> Dataset:
        dataset = Dataset(**payload.model_dump())
        return self.repository.create_dataset(dataset)

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

    def ensure_research(self, dataset_id: str, force: bool = False) -> tuple[ResearchArtifact, Job]:
        dataset = self.repository.get_dataset(dataset_id)
        existing = self.repository.get_research(dataset.id, dataset.language_code)
        if existing is not None and not force:
            job = self.repository.create_job(
                Job(
                    type="research",
                    status=JobStatus.SUCCEEDED,
                    progress=100,
                    message="Using cached research",
                    metadata={"dataset_id": dataset.id, "research_id": existing.id, "cached": True},
                )
            )
            return existing, job

        research_holder: dict[str, ResearchArtifact] = {}

        def callback(job: Job) -> dict:
            del job
            samples = [item.text for item in self.repository.list_items(dataset.id)[:20]]
            with self.tracer.span("research.create", dataset_id=dataset.id, language=dataset.language_code):
                artifact = self.research_provider.create_research(dataset, samples)
            saved = self.repository.save_research(artifact)
            research_holder["artifact"] = saved
            return {"dataset_id": dataset.id, "research_id": saved.id, "cached": False}

        job = self.jobs.run("research", callback)
        artifact = research_holder.get("artifact")
        if artifact is None:
            raise RuntimeError(job.error or "Research job failed before producing an artifact.")
        return artifact, job

    def create_pos_suggestions(self, dataset_id: str, limit: int = 5) -> tuple[list[Suggestion], Job]:
        dataset = self.repository.get_dataset(dataset_id)
        research, _ = self.ensure_research(dataset.id)
        created: list[Suggestion] = []

        def callback(job: Job) -> dict:
            del job
            candidates = [
                item
                for item in self.repository.list_items(dataset.id)
                if not self.repository.item_has_pos_suggestion(item.id)
            ][:limit]
            for item in candidates:
                tokens = self.pos_provider.suggest(item.text, research)
                confidence = sum(token.confidence for token in tokens) / max(len(tokens), 1)
                created.append(
                    self.repository.add_suggestion(
                        Suggestion(
                            dataset_id=dataset.id,
                            item_id=item.id,
                            research_id=research.id,
                            type=SuggestionType.POS,
                            original_text=item.text,
                            tokens=tokens,
                            confidence=round(confidence, 3),
                            rationale="Generated with cached research notes and UPOS schema.",
                        )
                    )
                )
            return {"dataset_id": dataset.id, "created_count": len(created), "research_id": research.id}

        job = self.jobs.run("pos_suggestions", callback)
        return created, job

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

    def review_suggestion(self, suggestion_id: str, review: SuggestionReview) -> Suggestion:
        suggestion = self.repository.get_suggestion(suggestion_id)
        update = {"status": review.action, "reviewed_at": now_utc()}
        if review.action == SuggestionStatus.EDITED:
            if suggestion.type == SuggestionType.POS and review.edited_tokens is not None:
                update["tokens"] = review.edited_tokens
            if suggestion.type == SuggestionType.OCR and review.edited_text is not None:
                update["suggested_text"] = review.edited_text
        updated = suggestion.model_copy(update=update)
        return self.repository.update_suggestion(updated)

    def translate(self, text: str, direction: str) -> tuple[str, str, str]:
        with self.tracer.span("translation.run", direction=direction):
            return self.translation_provider.translate(text, direction)

    def train_pos_model(self, dataset_id: str, request: PosTrainingRequest) -> tuple[PosModelState, Job]:
        dataset = self.repository.get_dataset(dataset_id)
        accepted_count = self.repository.count_accepted_pos_suggestions(dataset.id)
        model_holder: dict[str, PosModelState] = {}

        def callback(job: Job) -> dict:
            if accepted_count < request.minimum_examples and not request.demo_override:
                state = PosModelState(
                    dataset_id=dataset.id,
                    status=PosModelStatus.NEEDS_MORE_DATA,
                    accepted_sentence_count=accepted_count,
                    minimum_examples=request.minimum_examples,
                    job_id=job.id,
                )
                self.repository.save_pos_model(state)
                model_holder["state"] = state
                return {"accepted_sentence_count": accepted_count, "ready": False}

            state = PosModelState(
                dataset_id=dataset.id,
                status=PosModelStatus.READY,
                accepted_sentence_count=accepted_count,
                minimum_examples=request.minimum_examples,
                metrics={
                    "upos_accuracy": 0.82 if accepted_count < request.minimum_examples else 0.9,
                    "reviewed_examples": float(accepted_count),
                },
                model_name=f"{dataset.language_code}-upos-token-classifier-demo",
                job_id=job.id,
            )
            self.repository.save_pos_model(state)
            model_holder["state"] = state
            return {"accepted_sentence_count": accepted_count, "ready": True, "model_name": state.model_name}

        job = self.jobs.run("pos_model_training", callback)
        state = model_holder.get("state")
        if state is None:
            raise RuntimeError(job.error or "POS model training job failed before producing a model state.")
        return state, job
