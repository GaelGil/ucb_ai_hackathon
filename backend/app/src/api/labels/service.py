from __future__ import annotations

from app.src.api.research.service import ResearchService
from app.src.jobs import JobRunner
from app.src.models import (
    Job,
    PosModelState,
    PosModelStatus,
    PosTrainingRequest,
    Suggestion,
    SuggestionReview,
    SuggestionStatus,
    SuggestionType,
    now_utc,
)
from app.src.providers import PosAnnotationProvider
from app.src.repositories import InMemoryRepository


class LabelsService:
    def __init__(
        self,
        repository: InMemoryRepository,
        pos_provider: PosAnnotationProvider,
        research_service: ResearchService,
        jobs: JobRunner,
    ) -> None:
        self.repository = repository
        self.pos_provider = pos_provider
        self.research_service = research_service
        self.jobs = jobs

    def create_pos_suggestions(self, dataset_id: str, limit: int = 5) -> tuple[list[Suggestion], Job]:
        dataset = self.repository.get_dataset(dataset_id)
        research, _ = self.research_service.ensure_research(dataset.id)
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

    def list_suggestions(
        self,
        dataset_id: str,
        suggestion_type: SuggestionType | None = None,
        status: SuggestionStatus | None = None,
        limit: int | None = None,
    ) -> list[Suggestion]:
        return self.repository.list_suggestions(dataset_id, suggestion_type, status, limit)

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

    def get_pos_model(self, dataset_id: str) -> PosModelState:
        return self.repository.get_pos_model(dataset_id)
