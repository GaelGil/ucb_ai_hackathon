from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class SourceType(StrEnum):
    TEXT = "text"
    CSV = "csv"
    TXT = "txt"
    PDF = "pdf"
    IMAGE = "image"


class ImportKind(StrEnum):
    GENERIC = "generic"
    TRANSLATION = "translation"
    POS = "pos"


class SuggestionType(StrEnum):
    POS = "pos"
    OCR = "ocr"
    TRANSLATION = "translation"
    EMOTION = "emotion"
    INTENTION = "intention"
    TEXT = "text"
    CUSTOM = "custom"


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DENIED = "denied"
    UPDATED = "updated"
    APPROVED = "approved"
    EDITED = "edited"


class LabelSource(StrEnum):
    CSV_IMPORT = "csv_import"
    HUMAN = "human"
    AI_ACCEPTED = "ai_accepted"
    AI_UPDATED = "ai_updated"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PosModelStatus(StrEnum):
    NOT_STARTED = "not_started"
    NEEDS_MORE_DATA = "needs_more_data"
    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"


UPOS_TAGS = {
    "ADJ",
    "ADP",
    "ADV",
    "AUX",
    "CCONJ",
    "DET",
    "INTJ",
    "NOUN",
    "NUM",
    "PART",
    "PRON",
    "PROPN",
    "PUNCT",
    "SCONJ",
    "SYM",
    "VERB",
    "X",
}


class Dataset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ds"))
    name: str
    language_code: str
    language_name: str
    created_at: datetime = Field(default_factory=now_utc)


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    language_code: str = Field(min_length=2, max_length=16)
    language_name: str = Field(min_length=1, max_length=80)


class ImportRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("imp"))
    dataset_id: str
    source_type: SourceType
    filename: str | None = None
    item_count: int = 0
    asset_count: int = 0
    label_count: int = 0
    status: str = "ready"
    column_mapping: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class TextItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("item"))
    dataset_id: str
    import_id: str
    text: str
    source_type: SourceType = SourceType.TEXT
    created_at: datetime = Field(default_factory=now_utc)


class UploadedAsset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("asset"))
    dataset_id: str
    import_id: str
    source_type: SourceType
    filename: str
    content_type: str | None = None
    data: bytes
    created_at: datetime = Field(default_factory=now_utc)


class Label(BaseModel):
    id: str = Field(default_factory=lambda: new_id("label"))
    dataset_id: str
    data_row_id: str
    data_text: str | None = None
    import_id: str | None = None
    ai_suggestion_id: str | None = None
    type: SuggestionType
    name: str | None = None
    value: dict[str, Any] = Field(default_factory=dict)
    source: LabelSource = LabelSource.HUMAN
    original_column_name: str | None = None
    created_at: datetime = Field(default_factory=now_utc)


class ResearchSource(BaseModel):
    title: str
    url: str
    excerpt: str = ""


class ResearchArtifact(BaseModel):
    id: str = Field(default_factory=lambda: new_id("research"))
    dataset_id: str
    language_code: str
    type: str = "pos"
    summary: str
    guidelines: list[str] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class TokenSuggestion(BaseModel):
    index: int
    token: str
    suggested_pos: str = Field(pattern="^(ADJ|ADP|ADV|AUX|CCONJ|DET|INTJ|NOUN|NUM|PART|PRON|PROPN|PUNCT|SCONJ|SYM|VERB|X)$")
    confidence: float = Field(ge=0, le=1)
    rationale: str


class Suggestion(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sug"))
    dataset_id: str
    item_id: str | None = None
    import_id: str | None = None
    research_id: str | None = None
    type: SuggestionType
    status: SuggestionStatus = SuggestionStatus.PENDING
    original_text: str
    suggested_text: str | None = None
    tokens: list[TokenSuggestion] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    rationale: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    reviewed_at: datetime | None = None


class SuggestionReview(BaseModel):
    action: SuggestionStatus
    edited_text: str | None = None
    edited_tokens: list[TokenSuggestion] | None = None


class Job(BaseModel):
    id: str = Field(default_factory=lambda: new_id("job"))
    type: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    message: str = ""
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class PosSuggestionRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=5)


class TranslationSuggestionRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)


class OcrRequest(BaseModel):
    import_id: str | None = None


class TranslationRequest(BaseModel):
    text: str = Field(min_length=1)
    direction: str = "spanish_to_nahuatl"


class TranslationResponse(BaseModel):
    input_text: str
    output_text: str
    provider: str
    model: str


class PosTrainingRequest(BaseModel):
    minimum_examples: int = Field(default=20, ge=1)
    demo_override: bool = True


class PosModelState(BaseModel):
    dataset_id: str
    status: PosModelStatus = PosModelStatus.NOT_STARTED
    accepted_sentence_count: int = 0
    minimum_examples: int = 20
    metrics: dict[str, float] = Field(default_factory=dict)
    model_name: str | None = None
    job_id: str | None = None
    updated_at: datetime = Field(default_factory=now_utc)


class Dashboard(BaseModel):
    dataset: Dataset
    imports: list[ImportRecord]
    research: ResearchArtifact | None
    suggestion_counts: dict[str, int]
    item_count: int
    pos_model: PosModelState


class ImportResponse(BaseModel):
    import_record: ImportRecord
    job: Job
    created_items: list[TextItem] = Field(default_factory=list)
    created_labels: list[Label] = Field(default_factory=list)


class JobResponse(BaseModel):
    job: Job


class SuggestionsResponse(BaseModel):
    suggestions: list[Suggestion]


class LabelsResponse(BaseModel):
    labels: list[Label]


class ResearchResponse(BaseModel):
    research: ResearchArtifact
    job: Job


class PosTrainingResponse(BaseModel):
    pos_model: PosModelState
    job: Job
