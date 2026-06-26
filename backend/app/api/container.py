from __future__ import annotations

from dataclasses import dataclass

from flask import current_app, g
from sqlmodel import Session
from sqlalchemy import Engine

from app.api.data.service import DataService
from app.api.dataset.service import DatasetService
from app.api.labels.service import LabelsService
from app.api.language.service import LanguageService
from app.api.research.service import ResearchService
from app.config import Settings
from app.utils.job_runner import JobRunner
from app.clients.browserbase import BrowserbaseResearchProvider
from app.clients.image_reader import OCRProvider
from app.clients.part_of_speech import PosAnnotationProvider
from app.clients.translation import TranslationProvider
from app.clients.storage import SupabaseStorage
from app.clients.tracing import Tracer

SERVICES_CONFIG_KEY = "APP_SERVICES"


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


def get_services() -> AppServices:
    return current_app.config[SERVICES_CONFIG_KEY]


def get_db_session() -> Session:
    """Return the request-scoped database session, creating it on first use.

    One session is shared across all service factories within a single request
    (mirroring FastAPI's per-request dependency caching) and closed in the
    app-context teardown registered by ``create_app``.
    """
    if "db_session" not in g:
        g.db_session = Session(get_services().db_engine)
    return g.db_session


def close_db_session(exc: BaseException | None = None) -> None:
    session = g.pop("db_session", None)
    if session is not None:
        session.close()


def get_data_service() -> DataService:
    services = get_services()
    session = get_db_session()
    return DataService(
        session=session,
        ocr_provider=services.ocr_provider,
        jobs=JobRunner(session, services.tracer),
        storage=services.storage,
    )


def get_dataset_service() -> DatasetService:
    return DatasetService(session=get_db_session())


def get_labels_service() -> LabelsService:
    services = get_services()
    session = get_db_session()
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


def get_language_service() -> LanguageService:
    services = get_services()
    return LanguageService(translation_provider=services.translation_provider, tracer=services.tracer)


def get_research_service() -> ResearchService:
    services = get_services()
    session = get_db_session()
    return ResearchService(
        session=session,
        research_provider=services.research_provider,
        jobs=JobRunner(session, services.tracer),
        tracer=services.tracer,
    )
