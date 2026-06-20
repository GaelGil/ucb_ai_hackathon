from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.src.api.data.service import DataService
from app.src.api.dataset.service import DatasetService
from app.src.api.labels.service import LabelsService
from app.src.api.language.service import LanguageService
from app.src.api.research.service import ResearchService
from app.src.config import Settings
from app.src.repositories import InMemoryRepository


@dataclass(frozen=True)
class AppServices:
    settings: Settings
    repository: InMemoryRepository
    data: DataService
    dataset: DatasetService
    labels: LabelsService
    language: LanguageService
    research: ResearchService


def get_services(request: Request) -> AppServices:
    return request.app.state.services


def get_data_service(request: Request) -> DataService:
    return get_services(request).data


def get_dataset_service(request: Request) -> DatasetService:
    return get_services(request).dataset


def get_labels_service(request: Request) -> LabelsService:
    return get_services(request).labels


def get_language_service(request: Request) -> LanguageService:
    return get_services(request).language


def get_research_service(request: Request) -> ResearchService:
    return get_services(request).research


def get_repository(request: Request) -> InMemoryRepository:
    return get_services(request).repository
