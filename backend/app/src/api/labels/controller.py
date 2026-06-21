from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.src.api.dependencies import AppServices, get_services
from app.src.api.dependencies import get_labels_service
from app.src.api.labels.service import LabelsService
from app.src.api.research.service import ResearchService
from app.src.jobs import JobRunner
from app.src.models import (
    AnnotationRowsResponse,
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


def _labels_service_for_background(services: AppServices, session: Session) -> LabelsService:
    jobs = JobRunner(session, services.tracer)
    research = ResearchService(
        session=session,
        research_provider=services.research_provider,
        jobs=jobs,
        tracer=services.tracer,
    )
    return LabelsService(
        session=session,
        pos_provider=services.pos_provider,
        translation_provider=services.translation_provider,
        research_service=research,
        jobs=jobs,
    )


def _run_pos_suggestions_background(
    services: AppServices,
    job_id: str,
    dataset_id: str,
    limit: int,
) -> None:
    with Session(services.db_engine) as session:
        _labels_service_for_background(services, session).complete_queued_pos_suggestions(
            job_id=job_id,
            dataset_id=dataset_id,
            limit=limit,
        )


def _run_translation_suggestions_background(
    services: AppServices,
    job_id: str,
    dataset_id: str,
    limit: int,
) -> None:
    with Session(services.db_engine) as session:
        _labels_service_for_background(services, session).complete_queued_translation_suggestions(
            job_id=job_id,
            dataset_id=dataset_id,
            limit=limit,
        )


@router.post("/datasets/{dataset_id}/pos-suggestions")
def create_pos_suggestions(
    dataset_id: str,
    payload: PosSuggestionRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    service: LabelsService = Depends(get_labels_service),
) -> dict:
    services = get_services(request)
    if not services.settings.agent_jobs_background:
        suggestions, job = service.create_pos_suggestions(dataset_id, limit=payload.limit)
        return {"suggestions": suggestions, "job": job}

    suggestions, job = service.queue_pos_suggestions(dataset_id, limit=payload.limit)
    if job.status.value == "running":
        background_tasks.add_task(
            _run_pos_suggestions_background,
            services,
            job.id,
            dataset_id,
            payload.limit,
        )
    return {"suggestions": suggestions, "job": job}


@router.post("/datasets/{dataset_id}/translation-suggestions")
def create_translation_suggestions(
    dataset_id: str,
    payload: TranslationSuggestionRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    service: LabelsService = Depends(get_labels_service),
) -> dict:
    services = get_services(request)
    if not services.settings.agent_jobs_background:
        suggestions, job = service.create_translation_suggestions(dataset_id, limit=payload.limit)
        return {"suggestions": suggestions, "job": job}

    suggestions, job = service.queue_translation_suggestions(dataset_id, limit=payload.limit)
    if job.status.value == "running":
        background_tasks.add_task(
            _run_translation_suggestions_background,
            services,
            job.id,
            dataset_id,
            payload.limit,
        )
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
    needs_review: bool = Query(default=False),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: LabelsService = Depends(get_labels_service),
) -> LabelsResponse:
    labels, total = service.list_labels(dataset_id, type, source, limit, offset, needs_review=needs_review)
    return LabelsResponse(labels=labels, total=total, limit=limit, offset=offset)


@router.get("/datasets/{dataset_id}/annotation-rows", response_model=AnnotationRowsResponse)
def list_annotation_rows(
    dataset_id: str,
    type: SuggestionType,
    needs_review: bool = Query(default=False),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: LabelsService = Depends(get_labels_service),
) -> AnnotationRowsResponse:
    if type != SuggestionType.POS:
        raise HTTPException(status_code=400, detail="Only POS annotation rows are supported.")
    rows, total = service.list_annotation_rows(dataset_id, type, limit, offset, needs_review=needs_review)
    return AnnotationRowsResponse(rows=rows, total=total, limit=limit, offset=offset)


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
