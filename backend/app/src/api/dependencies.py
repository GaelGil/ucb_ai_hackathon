from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import Engine

from app.src.api.data.service import DataService
from app.src.api.dataset.service import DatasetService
from app.src.api.labels.service import LabelsService
from app.src.api.language.service import LanguageService
from app.src.api.research.service import ResearchService
from app.src.config import Settings
from app.src.database.session import SessionDep
from app.src.jobs import JobRunner
from app.src.providers import BrowserbaseResearchProvider, OCRProvider, PosAnnotationProvider, TranslationProvider
from app.src.storage import SupabaseStorage
from app.src.tracing import Tracer


@dataclass(frozen=True)
class AppServices:
    db_engine: Engine
    settings: Settings
    tracer: Tracer
    research_provider: BrowserbaseResearchProvider
    ocr_provider: OCRProvider
    pos_provider: PosAnnotationProvider
    translation_provider: TranslationProvider
    storage: SupabaseStorage


def get_services(request: Request) -> AppServices:
    return request.app.state.services


def get_data_service(request: Request, session: SessionDep) -> DataService:
    services = get_services(request)
    return DataService(
        session=session,
        ocr_provider=services.ocr_provider,
        jobs=JobRunner(session, services.tracer),
        storage=services.storage,
    )


def get_dataset_service(session: SessionDep) -> DatasetService:
    return DatasetService(session=session)


def get_labels_service(request: Request, session: SessionDep) -> LabelsService:
    services = get_services(request)
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


def get_language_service(request: Request) -> LanguageService:
    services = get_services(request)
    return LanguageService(translation_provider=services.translation_provider, tracer=services.tracer)


def get_research_service(request: Request, session: SessionDep) -> ResearchService:
    services = get_services(request)
    return ResearchService(
        session=session,
        research_provider=services.research_provider,
        jobs=JobRunner(session, services.tracer),
        tracer=services.tracer,
    )
