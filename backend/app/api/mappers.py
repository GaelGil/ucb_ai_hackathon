from __future__ import annotations

from typing import Any

from app import models as api
from app.database.models import (
    AiSuggestion,
    DataRow,
    DataSourceType,
    Dataset,
    ImportRecord,
    Job,
    Label,
    Language,
    Research,
)
from app.database.models.job import JobStatus as DbJobStatus
from app.database.models.label import LabelSource as DbLabelSource
from app.database.models.label import LabelType
from app.database.models.suggestion import SuggestionStatus as DbSuggestionStatus


def source_type_to_api(source_type: DataSourceType | str) -> api.SourceType:
    return api.SourceType(source_type.value if isinstance(source_type, DataSourceType) else source_type)


def source_type_to_db(source_type: api.SourceType | str) -> DataSourceType:
    return DataSourceType(source_type.value if isinstance(source_type, api.SourceType) else source_type)


def suggestion_type_to_api(label_type: LabelType | str) -> api.SuggestionType:
    return api.SuggestionType(label_type.value if isinstance(label_type, LabelType) else label_type)


def suggestion_type_to_db(suggestion_type: api.SuggestionType | str) -> LabelType:
    return LabelType(suggestion_type.value if isinstance(suggestion_type, api.SuggestionType) else suggestion_type)


def suggestion_status_to_api(status: DbSuggestionStatus | str) -> api.SuggestionStatus:
    value = status.value if isinstance(status, DbSuggestionStatus) else status
    return api.SuggestionStatus(value)


def suggestion_status_to_db(status: api.SuggestionStatus | str) -> DbSuggestionStatus:
    value = status.value if isinstance(status, api.SuggestionStatus) else status
    if value == api.SuggestionStatus.APPROVED.value:
        value = DbSuggestionStatus.accepted.value
    if value == api.SuggestionStatus.EDITED.value:
        value = DbSuggestionStatus.updated.value
    return DbSuggestionStatus(value)


def label_source_to_api(source: DbLabelSource | str) -> api.LabelSource:
    return api.LabelSource(source.value if isinstance(source, DbLabelSource) else source)


def dataset_to_api(dataset: Dataset, language: Language | None = None) -> api.Dataset:
    db_language = language or dataset.language
    return api.Dataset(
        id=dataset.id,
        name=dataset.name,
        language_code=db_language.code,
        language_name=db_language.name,
        created_at=dataset.created_at,
    )


def import_to_api(record: ImportRecord) -> api.ImportRecord:
    source_type = source_type_to_api(record.source_type)
    asset_count = record.row_count if source_type in {api.SourceType.PDF, api.SourceType.IMAGE} else 0
    return api.ImportRecord(
        id=record.id,
        dataset_id=record.dataset_id,
        source_type=source_type,
        filename=record.filename,
        item_count=record.row_count,
        asset_count=asset_count,
        label_count=record.label_count,
        status=record.status.value,
        column_mapping=record.column_mapping,
        created_at=record.created_at,
    )


def data_row_to_text_item(row: DataRow) -> api.TextItem:
    return api.TextItem(
        id=row.id,
        dataset_id=row.dataset_id,
        import_id=row.import_id or "",
        text=row.text_content or "",
        source_type=source_type_to_api(row.source_type),
        created_at=row.created_at,
    )


def label_to_api(label: Label, pending_suggestion: AiSuggestion | None = None) -> api.Label:
    data_row = getattr(label, "data_row", None)
    return api.Label(
        id=label.id,
        dataset_id=label.dataset_id,
        data_row_id=label.data_row_id,
        data_text=data_row.text_content if data_row is not None else None,
        import_id=label.import_id,
        ai_suggestion_id=label.ai_suggestion_id,
        type=suggestion_type_to_api(label.type),
        name=label.name,
        value=label.value,
        source=label_source_to_api(label.source),
        original_column_name=label.original_column_name,
        created_at=label.created_at,
        pending_suggestion=ai_suggestion_to_api(pending_suggestion) if pending_suggestion is not None else None,
    )


def job_to_api(job: Job) -> api.Job:
    return api.Job(
        id=job.id,
        type=job.type,
        status=api.JobStatus(job.status.value if isinstance(job.status, DbJobStatus) else job.status),
        progress=job.progress,
        message=job.message,
        error=job.error,
        metadata=job.job_metadata,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def research_to_api(dataset: Dataset, language: Language, research: Research) -> api.ResearchArtifact:
    warnings = research.research_metadata.get("warnings", [])
    return api.ResearchArtifact(
        id=research.id,
        dataset_id=dataset.id,
        language_code=language.code,
        type=research.type.value if hasattr(research.type, "value") else str(research.type),
        summary=research.notes or "",
        guidelines=[str(item) for item in research.research_metadata.get("guidelines", [])],
        sources=[_research_source(source) for source in research.sources],
        metadata=research.research_metadata,
        warnings=[api.ProviderWarning.model_validate(warning) for warning in warnings],
        created_at=research.created_at,
        updated_at=research.updated_at,
    )


def ai_suggestion_to_api(suggestion: AiSuggestion) -> api.Suggestion:
    original = suggestion.original_value or {}
    human = suggestion.human_value or {}
    value = human if suggestion.status == DbSuggestionStatus.updated and human else original
    tokens = [_token_suggestion(item) for item in value.get("tokens") or original.get("tokens") or []]
    suggested_text = value.get("text") if suggestion.label_type != LabelType.pos else None
    original_text = (
        original.get("source_text")
        if suggestion.label_type == LabelType.translation
        else original.get("text")
    )
    return api.Suggestion(
        id=suggestion.id,
        dataset_id=suggestion.dataset_id,
        item_id=suggestion.data_row_id,
        research_id=suggestion.research_id,
        type=suggestion_type_to_api(suggestion.label_type),
        status=suggestion_status_to_api(suggestion.status),
        original_text=str(original_text or suggestion.data_row.text_content or ""),
        suggested_text=str(suggested_text) if suggested_text is not None else None,
        tokens=tokens,
        confidence=suggestion.confidence,
        rationale=suggestion.rationale,
        created_at=suggestion.created_at,
        reviewed_at=suggestion.reviewed_at,
    )


def _research_source(source: dict[str, Any]) -> api.ResearchSource:
    return api.ResearchSource(
        title=str(source.get("title") or source.get("url") or "Source"),
        url=str(source.get("url") or ""),
        excerpt=str(source.get("excerpt") or ""),
    )


def _token_suggestion(value: dict[str, Any]) -> api.TokenSuggestion:
    return api.TokenSuggestion.model_validate(value)
