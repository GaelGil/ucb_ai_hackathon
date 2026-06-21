from __future__ import annotations

from flask import Blueprint, request

from app.src.api.dependencies import get_labels_service
from app.src.api.responses import json_abort, json_response
from app.src.models import (
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


def _enum_arg(enum_cls, name):
    raw = request.args.get(name)
    if raw is None:
        return None
    try:
        return enum_cls(raw)
    except ValueError:
        json_abort(422, f"Invalid value for {name}: {raw}")


def _limit_arg(name, low, high):
    raw = request.args.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        json_abort(422, f"Invalid value for {name}: {raw}")
    if value < low or value > high:
        json_abort(422, f"{name} must be between {low} and {high}.")
    return value


@bp.post("/datasets/<dataset_id>/pos-suggestions")
def create_pos_suggestions(dataset_id: str):
    payload = PosSuggestionRequest.model_validate(request.get_json(silent=True) or {})
    suggestions, job = get_labels_service().create_pos_suggestions(dataset_id, limit=payload.limit)
    return json_response({"suggestions": suggestions, "job": job})


@bp.post("/datasets/<dataset_id>/translation-suggestions")
def create_translation_suggestions(dataset_id: str):
    payload = TranslationSuggestionRequest.model_validate(request.get_json(silent=True) or {})
    suggestions, job = get_labels_service().create_translation_suggestions(dataset_id, limit=payload.limit)
    return json_response({"suggestions": suggestions, "job": job})


@bp.get("/datasets/<dataset_id>/suggestions")
def list_suggestions(dataset_id: str):
    suggestions = get_labels_service().list_suggestions(
        dataset_id,
        _enum_arg(SuggestionType, "type"),
        _enum_arg(SuggestionStatus, "status"),
        _limit_arg("limit", 1, 100),
    )
    return json_response(SuggestionsResponse(suggestions=suggestions))


@bp.get("/datasets/<dataset_id>/labels")
def list_labels(dataset_id: str):
    labels = get_labels_service().list_labels(
        dataset_id,
        _enum_arg(SuggestionType, "type"),
        _enum_arg(LabelSource, "source"),
        _limit_arg("limit", 1, 500),
    )
    return json_response(LabelsResponse(labels=labels))


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
