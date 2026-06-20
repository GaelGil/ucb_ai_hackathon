from __future__ import annotations

from fastapi import APIRouter, Depends

from app.src.api.dependencies import get_dataset_service
from app.src.api.dataset.service import DatasetService
from app.src.models import Dashboard, Dataset, DatasetCreate, JobResponse


router = APIRouter()


@router.post("/datasets", response_model=Dataset)
def create_dataset(payload: DatasetCreate, service: DatasetService = Depends(get_dataset_service)) -> Dataset:
    return service.create_dataset(payload)


@router.get("/datasets", response_model=list[Dataset])
def list_datasets(service: DatasetService = Depends(get_dataset_service)) -> list[Dataset]:
    return service.list_datasets()


@router.get("/datasets/{dataset_id}/dashboard", response_model=Dashboard)
def get_dashboard(dataset_id: str, service: DatasetService = Depends(get_dataset_service)) -> Dashboard:
    return service.get_dashboard(dataset_id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, service: DatasetService = Depends(get_dataset_service)) -> JobResponse:
    return JobResponse(job=service.get_job(job_id))
