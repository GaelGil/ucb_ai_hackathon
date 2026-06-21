from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.src.api.dependencies import get_labels_service
from app.src.api.labels.service import LabelsService
from app.src.models import (
    LabelSource,
    LabelsResponse,
    PosSuggestionRequest,
    PosTrainingRequest,
    PosTrainingResponse,
    Suggestion,
    SuggestionReview,
    SuggestionStatus,
    SuggestionType,
    SuggestionsResponse,
    TranslationSuggestionRequest,
)


router = APIRouter()


@router.post("/datasets/{dataset_id}/pos-suggestions")
def create_pos_suggestions(
    dataset_id: str,
    payload: PosSuggestionRequest,
    service: LabelsService = Depends(get_labels_service),
) -> dict:
    suggestions, job = service.create_pos_suggestions(dataset_id, limit=payload.limit)
    return {"suggestions": suggestions, "job": job}


@router.post("/datasets/{dataset_id}/translation-suggestions")
def create_translation_suggestions(
    dataset_id: str,
    payload: TranslationSuggestionRequest,
    service: LabelsService = Depends(get_labels_service),
) -> dict:
    suggestions, job = service.create_translation_suggestions(dataset_id, limit=payload.limit)
    return {"suggestions": suggestions, "job": job}


@router.get("/datasets/{dataset_id}/suggestions", response_model=SuggestionsResponse)
def list_suggestions(
    dataset_id: str,
    type: SuggestionType | None = None,
    status: SuggestionStatus | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: LabelsService = Depends(get_labels_service),
) -> SuggestionsResponse:
    suggestions, total = service.list_suggestions(dataset_id, type, status, limit, offset)
    return SuggestionsResponse(suggestions=suggestions, total=total, limit=limit, offset=offset)


@router.get("/datasets/{dataset_id}/labels", response_model=LabelsResponse)
def list_labels(
    dataset_id: str,
    type: SuggestionType | None = None,
    source: LabelSource | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: LabelsService = Depends(get_labels_service),
) -> LabelsResponse:
    labels, total = service.list_labels(dataset_id, type, source, limit, offset)
    return LabelsResponse(labels=labels, total=total, limit=limit, offset=offset)


@router.patch("/suggestions/{suggestion_id}", response_model=Suggestion)
def review_suggestion(
    suggestion_id: str,
    payload: SuggestionReview,
    service: LabelsService = Depends(get_labels_service),
) -> Suggestion:
    if payload.action == SuggestionStatus.PENDING:
        raise HTTPException(status_code=400, detail="Review action must be accepted, denied, or updated.")
    return service.review_suggestion(suggestion_id, payload)


@router.post("/datasets/{dataset_id}/pos-model/train", response_model=PosTrainingResponse)
def train_pos_model(
    dataset_id: str,
    payload: PosTrainingRequest,
    service: LabelsService = Depends(get_labels_service),
) -> PosTrainingResponse:
    pos_model, job = service.train_pos_model(dataset_id, payload)
    return PosTrainingResponse(pos_model=pos_model, job=job)


@router.get("/datasets/{dataset_id}/pos-model")
def get_pos_model(dataset_id: str, service: LabelsService = Depends(get_labels_service)):
    return service.get_pos_model(dataset_id)
