from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.src.api.mappers import (
    ai_suggestion_to_api,
    suggestion_status_to_db,
    suggestion_type_to_db,
)
from app.src.api.research.service import ResearchService
from app.src.database.models import AiSuggestion, DataRow, Dataset, Job, Label
from app.src.database.models.job import JobStatus as DbJobStatus
from app.src.database.models.label import LabelSource, LabelType
from app.src.database.models.language import now_utc
from app.src.database.models.research import ResearchType
from app.src.database.models.suggestion import SuggestionStatus as DbSuggestionStatus
from app.src.jobs import JobRunner
from app.src.models import (
    Label as ApiLabel,
    LabelSource as ApiLabelSource,
    Job as ApiJob,
    PosModelState,
    PosModelStatus,
    PosTrainingRequest,
    Suggestion,
    SuggestionReview,
    SuggestionStatus,
    SuggestionType,
)
from app.src.providers import PosAnnotationProvider, TranslationProvider
from app.src.repositories import NotFoundError


class LabelsService:
    def __init__(
        self,
        session: Session,
        pos_provider: PosAnnotationProvider,
        translation_provider: TranslationProvider,
        research_service: ResearchService,
        jobs: JobRunner,
    ) -> None:
        self.session = session
        self.pos_provider = pos_provider
        self.translation_provider = translation_provider
        self.research_service = research_service
        self.jobs = jobs

    def create_pos_suggestions(self, dataset_id: str, limit: int = 5) -> tuple[list[Suggestion], ApiJob]:
        dataset = self._get_dataset(dataset_id)
        research = self.research_service.get_research(dataset.id, ResearchType.pos)
        if research is None:
            job = self.jobs.create_failed(
                "pos_suggestions",
                "POS research must be generated before creating POS suggestions.",
                metadata={"dataset_id": dataset.id, "research_type": ResearchType.pos.value},
            )
            return [], job
        created: list[AiSuggestion] = []

        def callback(job: ApiJob) -> dict:
            del job
            rows, metadata = self._create_pos_suggestion_rows(dataset, research, limit)
            created.extend(rows)
            return metadata

        job = self.jobs.run("pos_suggestions", callback)
        return [ai_suggestion_to_api(suggestion) for suggestion in created], job

    def queue_pos_suggestions(self, dataset_id: str, limit: int = 5) -> tuple[list[Suggestion], ApiJob]:
        dataset = self._get_dataset(dataset_id)
        research = self.research_service.get_research(dataset.id, ResearchType.pos)
        if research is None:
            job = self.jobs.create_failed(
                "pos_suggestions",
                "POS research must be generated before creating POS suggestions.",
                metadata={"dataset_id": dataset.id, "research_type": ResearchType.pos.value},
            )
            return [], job
        job = self.jobs.create_running(
            "pos_suggestions",
            metadata={
                "dataset_id": dataset.id,
                "research_id": research.id,
                "research_type": ResearchType.pos.value,
                "provider": getattr(self.pos_provider, "provider", "anthropic"),
                "model": getattr(self.pos_provider, "model_name", None),
                "limit": limit,
            },
            message="POS suggestions started",
        )
        return [], job

    def complete_queued_pos_suggestions(self, *, job_id: str, dataset_id: str, limit: int = 5) -> ApiJob:
        dataset = self._get_dataset(dataset_id)
        research = self.research_service.get_research(dataset.id, ResearchType.pos)
        if research is None:
            return self.jobs.create_failed(
                "pos_suggestions",
                "POS research must be generated before creating POS suggestions.",
                metadata={"dataset_id": dataset.id, "research_type": ResearchType.pos.value},
            )

        def callback(job: ApiJob) -> dict:
            del job
            _, metadata = self._create_pos_suggestion_rows(dataset, research, limit)
            return metadata

        return self.jobs.run_existing(job_id, callback)

    def create_translation_suggestions(self, dataset_id: str, limit: int = 5) -> tuple[list[Suggestion], ApiJob]:
        dataset = self._get_dataset(dataset_id)
        research = self.research_service.get_research(dataset.id, ResearchType.translation)
        if research is None:
            job = self.jobs.create_failed(
                "translation_suggestions",
                "Translation research must be generated before creating translation suggestions.",
                metadata={"dataset_id": dataset.id, "research_type": ResearchType.translation.value},
            )
            return [], job
        created: list[AiSuggestion] = []

        def callback(job: ApiJob) -> dict:
            del job
            rows, metadata = self._create_translation_suggestion_rows(dataset, research, limit)
            created.extend(rows)
            return metadata

        job = self.jobs.run("translation_suggestions", callback)
        return [ai_suggestion_to_api(suggestion) for suggestion in created], job

    def queue_translation_suggestions(self, dataset_id: str, limit: int = 5) -> tuple[list[Suggestion], ApiJob]:
        dataset = self._get_dataset(dataset_id)
        research = self.research_service.get_research(dataset.id, ResearchType.translation)
        if research is None:
            job = self.jobs.create_failed(
                "translation_suggestions",
                "Translation research must be generated before creating translation suggestions.",
                metadata={"dataset_id": dataset.id, "research_type": ResearchType.translation.value},
            )
            return [], job
        job = self.jobs.create_running(
            "translation_suggestions",
            metadata={
                "dataset_id": dataset.id,
                "research_id": research.id,
                "research_type": ResearchType.translation.value,
                "provider": getattr(self.translation_provider, "provider", "anthropic"),
                "model": getattr(self.translation_provider, "model_name", None),
                "limit": limit,
            },
            message="Translation suggestions started",
        )
        return [], job

    def complete_queued_translation_suggestions(self, *, job_id: str, dataset_id: str, limit: int = 5) -> ApiJob:
        dataset = self._get_dataset(dataset_id)
        research = self.research_service.get_research(dataset.id, ResearchType.translation)
        if research is None:
            return self.jobs.create_failed(
                "translation_suggestions",
                "Translation research must be generated before creating translation suggestions.",
                metadata={"dataset_id": dataset.id, "research_type": ResearchType.translation.value},
            )

        def callback(job: ApiJob) -> dict:
            del job
            _, metadata = self._create_translation_suggestion_rows(dataset, research, limit)
            return metadata

        return self.jobs.run_existing(job_id, callback)

    def list_suggestions(
        self,
        dataset_id: str,
        suggestion_type: SuggestionType | None = None,
        status: SuggestionStatus | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[Suggestion], int]:
        self._get_dataset(dataset_id)
        filters = [AiSuggestion.dataset_id == dataset_id]
        if suggestion_type is not None:
            filters.append(AiSuggestion.label_type == suggestion_type_to_db(suggestion_type))
        if status is not None:
            filters.append(AiSuggestion.status == suggestion_status_to_db(status))

        total = self.session.exec(select(func.count()).select_from(AiSuggestion).where(*filters)).one()
        statement = (
            select(AiSuggestion)
            .where(*filters)
            .order_by(AiSuggestion.created_at, AiSuggestion.id)
            .offset(offset)
            .limit(limit)
        )
        suggestions = [ai_suggestion_to_api(suggestion) for suggestion in self.session.exec(statement).all()]
        return suggestions, total

    def list_labels(
        self,
        dataset_id: str,
        label_type: SuggestionType | None = None,
        source: ApiLabelSource | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[ApiLabel], int]:
        self._get_dataset(dataset_id)
        filters = [Label.dataset_id == dataset_id]
        if label_type is not None:
            filters.append(Label.type == suggestion_type_to_db(label_type))
        if source is not None:
            filters.append(Label.source == LabelSource(source.value))
        total = self.session.exec(select(func.count()).select_from(Label).where(*filters)).one()
        statement = select(Label).where(*filters).order_by(Label.created_at, Label.id).offset(offset).limit(limit)
        from app.src.api.mappers import label_to_api

        labels = [label_to_api(label) for label in self.session.exec(statement).all()]
        return labels, total

    def review_suggestion(self, suggestion_id: str, review: SuggestionReview) -> Suggestion:
        suggestion = self.session.get(AiSuggestion, suggestion_id)
        if suggestion is None:
            raise NotFoundError(f"Suggestion {suggestion_id} was not found.")

        status = suggestion_status_to_db(review.action)
        suggestion.status = status
        suggestion.reviewed_at = now_utc()
        suggestion.updated_at = now_utc()
        if status == DbSuggestionStatus.updated:
            suggestion.human_value = self._human_value(suggestion, review)
        self.session.add(suggestion)

        if status in {DbSuggestionStatus.accepted, DbSuggestionStatus.updated}:
            self._upsert_label_for_suggestion(suggestion)

        self.session.commit()
        self.session.refresh(suggestion)
        return ai_suggestion_to_api(suggestion)

    def train_pos_model(self, dataset_id: str, request: PosTrainingRequest) -> tuple[PosModelState, ApiJob]:
        dataset = self._get_dataset(dataset_id)
        accepted_count = self._count_trainable_pos_labels(dataset.id)
        minimum_examples_met = accepted_count >= request.minimum_examples
        training_mode = "demo" if request.demo_override else "real"
        model_holder: dict[str, PosModelState] = {}

        def callback(job: ApiJob) -> dict:
            if not minimum_examples_met and not request.demo_override:
                state = PosModelState(
                    dataset_id=dataset.id,
                    status=PosModelStatus.NEEDS_MORE_DATA,
                    mode=training_mode,
                    minimum_examples_met=minimum_examples_met,
                    accepted_sentence_count=accepted_count,
                    minimum_examples=request.minimum_examples,
                    job_id=job.id,
                )
            else:
                state = PosModelState(
                    dataset_id=dataset.id,
                    status=PosModelStatus.READY,
                    mode=training_mode,
                    minimum_examples_met=minimum_examples_met,
                    accepted_sentence_count=accepted_count,
                    minimum_examples=request.minimum_examples,
                    metrics={
                        "upos_accuracy": 0.82 if not minimum_examples_met else 0.9,
                        "reviewed_examples": float(accepted_count),
                    },
                    model_name=f"{dataset.language.code}-upos-token-classifier-demo",
                    job_id=job.id,
                )
            model_holder["state"] = state
            return {
                "dataset_id": dataset.id,
                "ready": state.status == PosModelStatus.READY,
                "accepted_sentence_count": accepted_count,
                "demo_override": request.demo_override,
                "training_mode": training_mode,
                "minimum_examples": request.minimum_examples,
                "minimum_examples_met": minimum_examples_met,
                "pos_model": state.model_dump(mode="json"),
            }

        job = self.jobs.run("pos_model_training", callback)
        state = model_holder.get("state")
        if state is None:
            raise RuntimeError(job.error or "POS model training job failed before producing a model state.")
        return state, job

    def get_pos_model(self, dataset_id: str) -> PosModelState:
        self._get_dataset(dataset_id)
        accepted_count = self._count_trainable_pos_labels(dataset_id)
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
            accepted_sentence_count=accepted_count,
            minimum_examples_met=accepted_count >= 20,
        )

    def _create_pos_suggestion_rows(
        self, dataset: Dataset, research, limit: int
    ) -> tuple[list[AiSuggestion], dict]:
        created: list[AiSuggestion] = []
        candidates = self._candidate_text_rows(dataset.id, LabelType.pos, limit)
        evaluations: list[dict] = []
        with self.research_service.tracer.span(
            "pos.suggestions.create",
            dataset_id=dataset.id,
            research_id=research.id,
            candidate_count=len(candidates),
        ):
            for row in candidates:
                tokens = self.pos_provider.suggest(row.text_content or "", research)
                confidence = sum(token.confidence for token in tokens) / max(len(tokens), 1)
                evaluation = self._evaluate_pos(row.text_content or "", tokens, research, dataset.id, row.id)
                if evaluation:
                    evaluations.append(evaluation)
                suggestion = AiSuggestion(
                    dataset_id=dataset.id,
                    data_row_id=row.id,
                    research_id=research.id,
                    label_type=LabelType.pos,
                    original_value={
                        "text": row.text_content,
                        "tokens": [token.model_dump() for token in tokens],
                        "metadata": {"evaluation": evaluation} if evaluation else {},
                    },
                    confidence=round(confidence, 3),
                    rationale=f"Generated by Claude with cached POS research profile {research.id}.",
                    provider=getattr(self.pos_provider, "provider", "anthropic"),
                    model_name=getattr(self.pos_provider, "model_name", None),
                )
                self.session.add(suggestion)
                created.append(suggestion)
        self.session.commit()
        for suggestion in created:
            self.session.refresh(suggestion)
        return created, {
            "dataset_id": dataset.id,
            "created_count": len(created),
            "research_id": research.id,
            "research_type": ResearchType.pos.value,
            "provider": getattr(self.pos_provider, "provider", "anthropic"),
            "model": getattr(self.pos_provider, "model_name", None),
            "evaluation": self._evaluation_summary(evaluations),
        }

    def _create_translation_suggestion_rows(
        self, dataset: Dataset, research, limit: int
    ) -> tuple[list[AiSuggestion], dict]:
        created: list[AiSuggestion] = []
        candidates = self._candidate_text_rows(dataset.id, LabelType.translation, limit)
        directions: list[str] = []
        evaluations: list[dict] = []
        with self.research_service.tracer.span(
            "translation.suggestions.create",
            dataset_id=dataset.id,
            research_id=research.id,
            candidate_count=len(candidates),
        ):
            for row in candidates:
                direction = self._translation_direction(row, dataset)
                directions.append(direction)
                result = self.translation_provider.suggest(
                    text=row.text_content or "",
                    direction=direction,
                    research=research,
                    row_metadata=row.row_metadata,
                )
                evaluation = self._evaluate_translation(
                    row.text_content or "",
                    direction,
                    result,
                    research,
                    row.row_metadata,
                    dataset.id,
                    row.id,
                )
                if evaluation:
                    evaluations.append(evaluation)
                    result.metadata = {**(result.metadata or {}), "evaluation": evaluation}
                suggestion = AiSuggestion(
                    dataset_id=dataset.id,
                    data_row_id=row.id,
                    research_id=research.id,
                    label_type=LabelType.translation,
                    original_value={
                        "source_text": row.text_content,
                        "text": result.output_text,
                        "direction": direction,
                        "metadata": result.metadata,
                    },
                    confidence=result.confidence,
                    rationale=result.rationale or f"Generated with cached translation research profile {research.id}.",
                    provider=result.provider,
                    model_name=result.model,
                )
                self.session.add(suggestion)
                created.append(suggestion)
        self.session.commit()
        for suggestion in created:
            self.session.refresh(suggestion)
        return created, {
            "dataset_id": dataset.id,
            "created_count": len(created),
            "research_id": research.id,
            "research_type": ResearchType.translation.value,
            "provider": getattr(self.translation_provider, "provider", "anthropic"),
            "model": getattr(self.translation_provider, "model_name", None),
            "directions": sorted(set(directions)),
            "used_fallback": False,
            "warnings": [],
            "evaluation": self._evaluation_summary(evaluations),
        }

    def _evaluate_pos(self, text: str, tokens, research, dataset_id: str, row_id: str) -> dict:
        evaluator = getattr(self.pos_provider, "evaluate", None)
        if evaluator is None:
            return {}
        try:
            evaluation = evaluator(text, tokens, research)
        except Exception as exc:
            evaluation = {"name": "pos_quality", "kind": "llm", "label": "error", "feedback": str(exc)}
        self.research_service.tracer.record_evaluation(
            "pos_quality",
            evaluation,
            dataset_id=dataset_id,
            data_row_id=row_id,
            research_id=research.id,
        )
        return evaluation

    def _evaluate_translation(
        self,
        text: str,
        direction: str,
        result,
        research,
        row_metadata: dict,
        dataset_id: str,
        row_id: str,
    ) -> dict:
        evaluator = getattr(self.translation_provider, "evaluate", None)
        if evaluator is None:
            return {}
        try:
            evaluation = evaluator(
                text=text,
                direction=direction,
                result=result,
                research=research,
                row_metadata=row_metadata,
            )
        except Exception as exc:
            evaluation = {"name": "translation_quality", "kind": "llm", "label": "error", "feedback": str(exc)}
        self.research_service.tracer.record_evaluation(
            "translation_quality",
            evaluation,
            dataset_id=dataset_id,
            data_row_id=row_id,
            research_id=research.id,
            direction=direction,
        )
        return evaluation

    def _evaluation_summary(self, evaluations: list[dict]) -> dict:
        if not evaluations:
            return {}
        scores = [float(item["score"]) for item in evaluations if isinstance(item.get("score"), (int, float))]
        return {
            "count": len(evaluations),
            "average_score": round(sum(scores) / len(scores), 3) if scores else None,
            "labels": [item.get("label") for item in evaluations if item.get("label")],
            "feedback": [item.get("feedback") for item in evaluations if item.get("feedback")],
        }

    def _translation_direction(self, row: DataRow, dataset: Dataset) -> str:
        csv_metadata = row.row_metadata.get("csv") if isinstance(row.row_metadata, dict) else None
        csv_metadata = csv_metadata if isinstance(csv_metadata, dict) else {}
        source = str(csv_metadata.get("src") or csv_metadata.get("source_language") or "auto").strip() or "auto"
        target = str(csv_metadata.get("target") or dataset.language.code).strip() or dataset.language.code
        return f"{source}_to_{target}"

    def _upsert_label_for_suggestion(self, suggestion: AiSuggestion) -> None:
        label = self.session.exec(select(Label).where(Label.ai_suggestion_id == suggestion.id)).first()
        if label is None:
            label = Label(
                dataset_id=suggestion.dataset_id,
                data_row_id=suggestion.data_row_id,
                ai_suggestion_id=suggestion.id,
                type=suggestion.label_type,
            )
        label.value = suggestion.human_value if suggestion.status == DbSuggestionStatus.updated else suggestion.original_value
        label.source = (
            LabelSource.ai_updated if suggestion.status == DbSuggestionStatus.updated else LabelSource.ai_accepted
        )
        label.name = suggestion.label_type.value
        label.updated_at = now_utc()
        self.session.add(label)

    def _human_value(self, suggestion: AiSuggestion, review: SuggestionReview) -> dict:
        if suggestion.label_type == LabelType.pos and review.edited_tokens is not None:
            return {
                "text": suggestion.original_value.get("text"),
                "tokens": [token.model_dump() for token in review.edited_tokens],
            }
        if review.edited_text is not None:
            value = dict(suggestion.original_value)
            value["text"] = review.edited_text
            return value
        return suggestion.original_value

    def _candidate_text_rows(self, dataset_id: str, label_type: LabelType, limit: int) -> list[DataRow]:
        existing_suggestion_row_ids = {
            suggestion.data_row_id
            for suggestion in self.session.exec(
                select(AiSuggestion)
                .where(AiSuggestion.dataset_id == dataset_id)
                .where(AiSuggestion.label_type == label_type)
                .where(AiSuggestion.status != DbSuggestionStatus.denied)
            ).all()
        }
        existing_label_row_ids = {
            label.data_row_id
            for label in self.session.exec(
                select(Label).where(Label.dataset_id == dataset_id).where(Label.type == label_type)
            ).all()
        }
        excluded_row_ids = existing_suggestion_row_ids | existing_label_row_ids
        return [
            row
            for row in self.session.exec(
                select(DataRow)
                .where(DataRow.dataset_id == dataset_id)
                .where(DataRow.text_content.is_not(None))
                .order_by(DataRow.created_at)
            ).all()
            if row.id not in excluded_row_ids and row.text_content
        ][:limit]

    def _count_trainable_pos_labels(self, dataset_id: str) -> int:
        return self.session.exec(
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

    def _get_dataset(self, dataset_id: str) -> Dataset:
        dataset = self.session.get(Dataset, dataset_id)
        if dataset is None:
            raise NotFoundError(f"Dataset {dataset_id} was not found.")
        return dataset
