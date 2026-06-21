from __future__ import annotations

from flask import Blueprint, request

from app.api.context import get_dataset_service
from app.api.responses import json_response
from app.schemas import DatasetCreate, JobResponse


bp = Blueprint("dataset", __name__)


@bp.post("/datasets")
def create_dataset():
    payload = DatasetCreate.model_validate(request.get_json(silent=True) or {})
    return json_response(get_dataset_service().create_dataset(payload))


@bp.get("/datasets")
def list_datasets():
    return json_response(get_dataset_service().list_datasets())


@bp.delete("/datasets/<dataset_id>")
def delete_dataset(dataset_id: str):
    get_dataset_service().delete_dataset(dataset_id)
    return "", 204


@bp.get("/datasets/<dataset_id>/dashboard")
def get_dashboard(dataset_id: str):
    return json_response(get_dataset_service().get_dashboard(dataset_id))


@bp.get("/jobs/<job_id>")
def get_job(job_id: str):
    return json_response(JobResponse(job=get_dataset_service().get_job(job_id)))
