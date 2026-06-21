from __future__ import annotations

import threading

from flask import Blueprint, request
from sqlmodel import Session

from app.api.dependencies import AppServices, get_labels_service, get_services
from app.api.labels.service import LabelsService
from app.api.research.service import ResearchService
from app.api.responses import json_abort, json_response
from app.jobs import JobRunner
from app.schemas import (
    LabelSource,
    LabelsResponse,
    PosSuggestionRequest,
    PosTrainingRequest,
    PosTrainingResponse,
    SuggestionReview,
    SuggestionStatus,
    SuggestionType,
    SuggestionsResponse,
    TranslationSuggestionRequest,
)


bp = Blueprint("labels", __name__)


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


def _run_pos_suggestions_background(services: AppServices, job_id: str, dataset_id: str, limit: int) -> None:
    with Session(services.db_engine) as session:
        _labels_service_for_background(services, session).complete_queued_pos_suggestions(
            job_id=job_id, dataset_id=dataset_id, limit=limit
        )


def _run_translation_suggestions_background(
    services: AppServices, job_id: str, dataset_id: str, limit: int
) -> None:
    with Session(services.db_engine) as session:
        _labels_service_for_background(services, session).complete_queued_translation_suggestions(
            job_id=job_id, dataset_id=dataset_id, limit=limit
        )


def _enum_arg(enum_cls, name):
    raw = request.args.get(name)
    if raw is None:
        return None
    try:
        return enum_cls(raw)
    except ValueError:
        json_abort(422, f"Invalid value for {name}: {raw}")


def _int_arg(name, default, low, high):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        json_abort(422, f"Invalid value for {name}: {raw}")
    if value < low or value > high:
        json_abort(422, f"{name} must be between {low} and {high}.")
    return value


def _bool_arg(name, default=False):
    raw = request.args.get(name, "").strip().lower()
    if raw == "":
        return default
    return raw in {"true", "1", "yes"}


@bp.post("/datasets/<dataset_id>/pos-suggestions")
def create_pos_suggestions(dataset_id: str):
    payload = PosSuggestionRequest.model_validate(request.get_json(silent=True) or {})
    services = get_services()
    if not services.settings.agent_jobs_background:
        suggestions, job = get_labels_service().create_pos_suggestions(dataset_id, limit=payload.limit)
        return json_response({"suggestions": suggestions, "job": job})
    service = get_labels_service()
    suggestions, job = service.queue_pos_suggestions(dataset_id, limit=payload.limit)
    if job.status.value == "running":
        threading.Thread(
            target=_run_pos_suggestions_background,
            args=(services, job.id, dataset_id, payload.limit),
            daemon=True,
        ).start()
    return json_response({"suggestions": suggestions, "job": job})


@bp.post("/datasets/<dataset_id>/translation-suggestions")
def create_translation_suggestions(dataset_id: str):
    payload = TranslationSuggestionRequest.model_validate(request.get_json(silent=True) or {})
    services = get_services()
    if not services.settings.agent_jobs_background:
        suggestions, job = get_labels_service().create_translation_suggestions(dataset_id, limit=payload.limit)
        return json_response({"suggestions": suggestions, "job": job})
    service = get_labels_service()
    suggestions, job = service.queue_translation_suggestions(dataset_id, limit=payload.limit)
    if job.status.value == "running":
        threading.Thread(
            target=_run_translation_suggestions_background,
            args=(services, job.id, dataset_id, payload.limit),
            daemon=True,
        ).start()
    return json_response({"suggestions": suggestions, "job": job})


@bp.get("/datasets/<dataset_id>/suggestions")
def list_suggestions(dataset_id: str):
    limit = _int_arg("limit", 10, 1, 100)
    offset = _int_arg("offset", 0, 0, 10**9)
    suggestions, total = get_labels_service().list_suggestions(
        dataset_id,
        _enum_arg(SuggestionType, "type"),
        _enum_arg(SuggestionStatus, "status"),
        limit,
        offset,
    )
    return json_response(SuggestionsResponse(suggestions=suggestions, total=total, limit=limit, offset=offset))


@bp.get("/datasets/<dataset_id>/labels")
def list_labels(dataset_id: str):
    limit = _int_arg("limit", 10, 1, 500)
    offset = _int_arg("offset", 0, 0, 10**9)
    needs_review = _bool_arg("needs_review")
    labels, total = get_labels_service().list_labels(
        dataset_id,
        _enum_arg(SuggestionType, "type"),
        _enum_arg(LabelSource, "source"),
        limit,
        offset,
        needs_review=needs_review,
    )
    return json_response(LabelsResponse(labels=labels, total=total, limit=limit, offset=offset))


@bp.patch("/suggestions/<suggestion_id>")
def review_suggestion(suggestion_id: str):
    payload = SuggestionReview.model_validate(request.get_json(silent=True) or {})
    if payload.action == SuggestionStatus.PENDING:
        json_abort(400, "Review action must be accepted, denied, or updated.")
    return json_response(get_labels_service().review_suggestion(suggestion_id, payload))


@bp.post("/datasets/<dataset_id>/pos-model/train")
def train_pos_model(dataset_id: str):
    payload = PosTrainingRequest.model_validate(request.get_json(silent=True) or {})
    pos_model, job = get_labels_service().train_pos_model(dataset_id, payload)
    return json_response(PosTrainingResponse(pos_model=pos_model, job=job))


@bp.get("/datasets/<dataset_id>/pos-model")
def get_pos_model(dataset_id: str):
    return json_response(get_labels_service().get_pos_model(dataset_id))
