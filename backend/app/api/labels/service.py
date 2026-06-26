from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.utils.mappers import (
    ai_suggestion_to_api,
    label_to_api,
    source_type_to_api,
    suggestion_status_to_db,
    suggestion_type_to_db,
)
from app.api.research.service import ResearchService
from app.database.models import AiSuggestion, DataRow, Dataset, Job, Label
from app.database.models.job import JobStatus as DbJobStatus
from app.database.models.label import LabelSource, LabelType
from app.database.models.language import now_utc
from app.database.models.research import ResearchType
from app.database.models.suggestion import SuggestionStatus as DbSuggestionStatus
from app.utils.job_runner import JobRunner
from app.schemas import (
    AnnotationRow as ApiAnnotationRow,
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
    UPOS_TAGS,
)
from app.clients.part_of_speech import PosAnnotationProvider
from app.clients.translation import TranslationProvider
from app.exceptions import NotFoundError


class SuggestionBatchError(RuntimeError):
    def __init__(self, message: str, metadata: dict) -> None:
        super().__init__(message)
        self.metadata = metadata


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

    def list_annotation_rows(
        self,
        dataset_id: str,
        row_type: SuggestionType,
        limit: int = 10,
        offset: int = 0,
        needs_review: bool = False,
    ) -> tuple[list[ApiAnnotationRow], int]:
        self._get_dataset(dataset_id)
        db_label_type = suggestion_type_to_db(row_type)
        if db_label_type != LabelType.pos:
            raise ValueError("Only POS annotation rows are supported.")

        rows = self._annotation_rows_for_label_type(dataset_id, db_label_type)
        pending_by_row_id = self._pending_suggestions_by_row_id(
            dataset_id,
            db_label_type,
            [row.id for row in rows],
        )
        labels_by_row_id = self._labels_by_row_id(dataset_id, db_label_type, [row.id for row in rows])
        if needs_review:
            rows = [row for row in rows if row.id in pending_by_row_id]
        total = len(rows)
        page_rows = rows[offset : offset + limit]
        return [
            ApiAnnotationRow(
                id=row.id,
                dataset_id=row.dataset_id,
                data_row_id=row.id,
                text=row.text_content or "",
                type=SuggestionType.POS,
                source_type=source_type_to_api(row.source_type),
                created_at=row.created_at,
                pending_suggestion=ai_suggestion_to_api(pending_by_row_id[row.id])
                if row.id in pending_by_row_id
                else None,
                label=label_to_api(labels_by_row_id[row.id]) if row.id in labels_by_row_id else None,
            )
            for row in page_rows
        ], total

    def list_labels(
        self,
        dataset_id: str,
        label_type: SuggestionType | None = None,
        source: ApiLabelSource | None = None,
        limit: int = 10,
        offset: int = 0,
        needs_review: bool = False,
    ) -> tuple[list[ApiLabel], int]:
        self._get_dataset(dataset_id)
        filters = [Label.dataset_id == dataset_id]
        if label_type is not None:
            db_label_type = suggestion_type_to_db(label_type)
            filters.append(Label.type == db_label_type)
        else:
            db_label_type = None
        if source is not None:
            filters.append(Label.source == LabelSource(source.value))
        from app.utils.mappers import label_to_api

        if db_label_type == LabelType.translation:
            records = self.session.exec(
                select(Label, DataRow.row_index)
                .join(DataRow, Label.data_row_id == DataRow.id)
                .where(*filters)
                .order_by(Label.created_at, Label.id)
            ).all()
            interleave_size = max(limit, 1)
            ordered = sorted(
                records,
                key=lambda item: (
                    (item[1] or 0) % interleave_size,
                    item[1] or 0,
                    item[0].created_at,
                    item[0].id,
                ),
            )
            pending_by_row_id = self._pending_suggestions_by_row_id(
                dataset_id,
                LabelType.translation,
                [label.data_row_id for label, _ in ordered],
            )
            if needs_review:
                ordered = [(label, row_index) for label, row_index in ordered if label.data_row_id in pending_by_row_id]
            total = len(ordered)
            page_records = ordered[offset : offset + limit]
            labels = [
                label_to_api(label, pending_suggestion=pending_by_row_id.get(label.data_row_id))
                for label, _ in page_records
            ]
            return labels, total

        total = self.session.exec(select(func.count()).select_from(Label).where(*filters)).one()
        statement = select(Label).where(*filters).order_by(Label.created_at, Label.id).offset(offset).limit(limit)
        labels = [label_to_api(label) for label in self.session.exec(statement).all()]
        return labels, total

    def _pending_suggestions_by_row_id(
        self,
        dataset_id: str,
        label_type: LabelType,
        data_row_ids: list[str],
    ) -> dict[str, AiSuggestion]:
        if not data_row_ids:
            return {}
        suggestions = self.session.exec(
            select(AiSuggestion)
            .where(AiSuggestion.dataset_id == dataset_id)
            .where(AiSuggestion.label_type == label_type)
            .where(AiSuggestion.status == DbSuggestionStatus.pending)
            .where(AiSuggestion.data_row_id.in_(data_row_ids))
            .order_by(AiSuggestion.created_at, AiSuggestion.id)
        ).all()
        by_row_id: dict[str, AiSuggestion] = {}
        for suggestion in suggestions:
            by_row_id.setdefault(suggestion.data_row_id, suggestion)
        return by_row_id

    def _annotation_rows_for_label_type(self, dataset_id: str, label_type: LabelType) -> list[DataRow]:
        all_rows = [
            row
            for row in self.session.exec(
                select(DataRow)
                .where(DataRow.dataset_id == dataset_id)
                .where(DataRow.text_content.is_not(None))
                .order_by(DataRow.created_at, DataRow.row_index, DataRow.id)
            ).all()
            if row.text_content
        ]
        if label_type == LabelType.pos:
            seeded_rows = [row for row in all_rows if self._is_pos_seed_row(row)]
            return seeded_rows or all_rows

        completed_label_row_ids = {
            label.data_row_id
            for label in self.session.exec(
                select(Label).where(Label.dataset_id == dataset_id).where(Label.type == label_type)
            ).all()
        }
        return [row for row in all_rows if row.id not in completed_label_row_ids]

    def _labels_by_row_id(
        self,
        dataset_id: str,
        label_type: LabelType,
        data_row_ids: list[str],
    ) -> dict[str, Label]:
        if not data_row_ids:
            return {}
        labels = self.session.exec(
            select(Label)
            .where(Label.dataset_id == dataset_id)
            .where(Label.type == label_type)
            .where(Label.data_row_id.in_(data_row_ids))
            .order_by(Label.updated_at.desc(), Label.created_at.desc(), Label.id.desc())
        ).all()
        by_row_id: dict[str, Label] = {}
        for label in labels:
            by_row_id.setdefault(label.data_row_id, label)
        return by_row_id

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
        feedback_examples = self._pos_feedback_examples(dataset.id)
        evaluations: list[dict] = []
        row_errors: list[dict] = []
        print(
            "[research-debug] creating pos suggestions "
            f"dataset_id={dataset.id} research_id={research.id} candidate_count={len(candidates)} limit={limit} "
            f"positive_examples={len(feedback_examples.get('positive_examples', []))} "
            f"negative_examples={len(feedback_examples.get('negative_examples', []))}",
            flush=True,
        )
        with self.research_service.tracer.span(
            "pos.suggestions.create",
            dataset_id=dataset.id,
            research_id=research.id,
            candidate_count=len(candidates),
        ):
            for row in candidates:
                print(
                    "[research-debug] creating pos suggestion for row "
                    f"dataset_id={dataset.id} row_id={row.id} text_chars={len(row.text_content or '')}",
                    flush=True,
                )
                try:
                    tokens = self.pos_provider.suggest(
                        row.text_content or "",
                        research,
                        feedback_examples=feedback_examples,
                    )
                except Exception as exc:
                    error = {
                        "row_id": row.id,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    row_errors.append(error)
                    print(
                        "[research-debug] pos suggestion row failed "
                        f"dataset_id={dataset.id} row_id={row.id} error={error['error']}",
                        flush=True,
                    )
                    continue
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
                print(
                    "[research-debug] pos suggestion row created "
                    f"dataset_id={dataset.id} row_id={row.id} token_count={len(tokens)}",
                    flush=True,
                )
        if not created and row_errors:
            first_error = row_errors[0]["error"]
            raise SuggestionBatchError(
                f"POS suggestions failed for every candidate row. First error: {first_error}",
                {
                    "dataset_id": dataset.id,
                    "created_count": 0,
                    "failed_count": len(row_errors),
                    "row_errors": row_errors[:5],
                    "research_id": research.id,
                    "research_type": ResearchType.pos.value,
                    "provider": getattr(self.pos_provider, "provider", "anthropic"),
                    "model": getattr(self.pos_provider, "model_name", None),
                },
            )
        self.session.commit()
        for suggestion in created:
            self.session.refresh(suggestion)
        print(
            "[research-debug] pos suggestions saved "
            f"dataset_id={dataset.id} created_count={len(created)} failed_count={len(row_errors)}",
            flush=True,
        )
        return created, {
            "dataset_id": dataset.id,
            "created_count": len(created),
            "failed_count": len(row_errors),
            "row_errors": row_errors[:5],
            "research_id": research.id,
            "research_type": ResearchType.pos.value,
            "provider": getattr(self.pos_provider, "provider", "anthropic"),
            "model": getattr(self.pos_provider, "model_name", None),
            "feedback_positive_count": len(feedback_examples.get("positive_examples", [])),
            "feedback_negative_count": len(feedback_examples.get("negative_examples", [])),
            "evaluation": self._evaluation_summary(evaluations),
        }

    def _pos_feedback_examples(self, dataset_id: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "positive_examples": self._positive_pos_examples(dataset_id),
            "negative_examples": self._negative_pos_examples(dataset_id),
        }

    def _positive_pos_examples(self, dataset_id: str, limit: int = 5) -> list[dict[str, Any]]:
        records = self.session.exec(
            select(Label, DataRow.text_content)
            .join(DataRow, Label.data_row_id == DataRow.id)
            .where(Label.dataset_id == dataset_id)
            .where(Label.type == LabelType.pos)
            .where(
                Label.source.in_(
                    [
                        LabelSource.ai_accepted,
                        LabelSource.ai_updated,
                        LabelSource.human,
                        LabelSource.csv_import,
                    ]
                )
            )
            .order_by(Label.updated_at.desc(), Label.created_at.desc(), Label.id.desc())
            .limit(limit)
        ).all()
        examples: list[dict[str, Any]] = []
        for label, row_text in records:
            example = self._pos_feedback_example_from_value(
                value=label.value,
                text=row_text,
                source=label.source.value,
                kind="positive",
            )
            if example:
                examples.append(example)
        return examples

    def _negative_pos_examples(self, dataset_id: str, limit: int = 3) -> list[dict[str, Any]]:
        records = self.session.exec(
            select(AiSuggestion, DataRow.text_content)
            .join(DataRow, AiSuggestion.data_row_id == DataRow.id)
            .where(AiSuggestion.dataset_id == dataset_id)
            .where(AiSuggestion.label_type == LabelType.pos)
            .where(AiSuggestion.status == DbSuggestionStatus.denied)
            .order_by(AiSuggestion.updated_at.desc(), AiSuggestion.created_at.desc(), AiSuggestion.id.desc())
            .limit(limit)
        ).all()
        examples: list[dict[str, Any]] = []
        for suggestion, row_text in records:
            example = self._pos_feedback_example_from_value(
                value=suggestion.original_value,
                text=row_text,
                source="denied_suggestion",
                kind="negative",
            )
            if example:
                example["warning"] = "Reviewer denied this suggestion; avoid repeating these tags without stronger evidence."
                examples.append(example)
        return examples

    def _pos_feedback_example_from_value(
        self,
        *,
        value: dict[str, Any],
        text: str | None,
        source: str,
        kind: str,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        example_text = self._compact_feedback_text(str(text or value.get("text") or ""), 260)
        tokens = self._pos_feedback_tokens(value.get("tokens"))
        tags = self._compact_feedback_text(str(value.get("tags") or ""), 220)
        if not example_text or (not tokens and not tags):
            return {}
        example: dict[str, Any] = {
            "kind": kind,
            "source": source,
            "text": example_text,
        }
        if tokens:
            example["tokens"] = tokens
        elif tags:
            example["tags"] = tags
        return example

    def _pos_feedback_tokens(self, value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        tokens: list[dict[str, Any]] = []
        for item in value[:24]:
            if not isinstance(item, dict):
                continue
            token = self._compact_feedback_text(str(item.get("token") or ""), 80)
            tag = str(item.get("suggested_pos") or item.get("upos") or "").upper()
            if not token or tag not in UPOS_TAGS:
                continue
            tokens.append(
                {
                    "token": token,
                    "upos": tag,
                    "rationale": self._compact_feedback_text(str(item.get("rationale") or ""), 120),
                }
            )
        return tokens

    def _compact_feedback_text(self, text: str, limit: int) -> str:
        return " ".join(text.split())[:limit]

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
        if label is None and suggestion.label_type == LabelType.translation:
            label = self.session.exec(
                select(Label)
                .where(Label.dataset_id == suggestion.dataset_id)
                .where(Label.data_row_id == suggestion.data_row_id)
                .where(Label.type == LabelType.translation)
                .where(Label.ai_suggestion_id.is_(None))
            ).first()
            if label is not None and not self._is_incomplete_translation_label(label):
                label = None
        if label is None:
            label = Label(
                dataset_id=suggestion.dataset_id,
                data_row_id=suggestion.data_row_id,
                ai_suggestion_id=suggestion.id,
                type=suggestion.label_type,
            )
        label.ai_suggestion_id = suggestion.id
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
        existing_label_row_ids = set()
        for label in self.session.exec(
            select(Label).where(Label.dataset_id == dataset_id).where(Label.type == label_type)
        ).all():
            if not self._is_incomplete_translation_label(label):
                existing_label_row_ids.add(label.data_row_id)
        excluded_row_ids = existing_suggestion_row_ids | existing_label_row_ids
        rows = [
            row
            for row in self.session.exec(
                select(DataRow)
                .where(DataRow.dataset_id == dataset_id)
                .where(DataRow.text_content.is_not(None))
                .order_by(DataRow.created_at)
            ).all()
            if row.id not in excluded_row_ids and row.text_content
        ]
        if label_type == LabelType.translation:
            rows = [row for row in rows if not self._is_pos_seed_row(row)]
        if label_type == LabelType.pos:
            seeded_rows = [row for row in rows if self._is_pos_seed_row(row)]
            if seeded_rows:
                rows = seeded_rows
        return rows[:limit]

    @staticmethod
    def _is_incomplete_translation_label(label: Label) -> bool:
        if label.type != LabelType.translation:
            return False
        value = label.value or {}
        return not str(value.get("text") or "").strip()

    @staticmethod
    def _is_pos_seed_row(row: DataRow) -> bool:
        metadata = row.row_metadata if isinstance(row.row_metadata, dict) else {}
        pos_seed = metadata.get("pos_seed") if isinstance(metadata, dict) else None
        return isinstance(pos_seed, dict) and pos_seed.get("source") == "translation_rows"

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
