from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlmodel import SQLModel, Session

from app.src.api.data.controller import router as data_router
from app.src.api.dataset.controller import router as dataset_router
from app.src.api.dataset.service import DatasetService
from app.src.api.dependencies import AppServices
from app.src.api.labels.controller import router as labels_router
from app.src.api.language.controller import router as language_router
from app.src.api.research.controller import router as research_router
from app.src.config import Settings, get_settings
from app.src.database.session import create_database_engine, engine as default_engine, get_db
from app.src.providers import BrowserbaseResearchProvider, OCRProvider, PosAnnotationProvider, TranslationProvider
from app.src.repositories import NotFoundError
from app.src.storage import SupabaseStorage
from app.src.tracing import Tracer


def create_app(
    repository: object | None = None,
    settings: Settings | None = None,
    engine: Engine | None = None,
    create_tables: bool | None = None,
) -> FastAPI:
    del repository
    custom_settings = settings is not None
    settings = settings or get_settings()
    db_engine = engine or (create_database_engine(settings) if custom_settings else default_engine)
    should_create_tables = settings.create_db_on_startup if create_tables is None else create_tables
    if should_create_tables:
        SQLModel.metadata.create_all(db_engine)

    tracer = Tracer(settings)
    services = AppServices(
        db_engine=db_engine,
        settings=settings,
        tracer=tracer,
        research_provider=BrowserbaseResearchProvider(settings=settings),
        ocr_provider=OCRProvider(),
        pos_provider=PosAnnotationProvider(),
        translation_provider=TranslationProvider(settings=settings),
        storage=SupabaseStorage(settings),
    )

    if settings.seed_demo_data:
        with Session(db_engine) as session:
            DatasetService(session=session).seed_demo_dataset()

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.state.services = services

    if engine is not None or custom_settings:
        def get_app_db():
            with Session(db_engine) as session:
                yield session

        app.dependency_overrides[get_db] = get_app_db

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(dataset_router)
    app.include_router(data_router)
    app.include_router(research_router)
    app.include_router(labels_router)
    app.include_router(language_router)
    return app
