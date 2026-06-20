from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.src.api.data.controller import router as data_router
from app.src.api.data.service import DataService
from app.src.api.dataset.controller import router as dataset_router
from app.src.api.dataset.service import DatasetService
from app.src.api.dependencies import AppServices
from app.src.api.labels.controller import router as labels_router
from app.src.api.labels.service import LabelsService
from app.src.api.language.controller import router as language_router
from app.src.api.language.service import LanguageService
from app.src.api.research.controller import router as research_router
from app.src.api.research.service import ResearchService
from app.src.config import Settings, get_settings
from app.src.jobs import JobRunner
from app.src.providers import BrowserbaseResearchProvider, OCRProvider, PosAnnotationProvider, TranslationProvider
from app.src.repositories import InMemoryRepository, NotFoundError
from app.src.tracing import Tracer


def create_app(repository: InMemoryRepository | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    repo = repository or InMemoryRepository()
    tracer = Tracer(settings)
    jobs = JobRunner(repo, tracer)

    research_service = ResearchService(
        repository=repo,
        research_provider=BrowserbaseResearchProvider(settings=settings),
        jobs=jobs,
        tracer=tracer,
    )
    services = AppServices(
        settings=settings,
        repository=repo,
        dataset=DatasetService(repository=repo),
        data=DataService(repository=repo, ocr_provider=OCRProvider(), jobs=jobs),
        labels=LabelsService(
            repository=repo,
            pos_provider=PosAnnotationProvider(),
            research_service=research_service,
            jobs=jobs,
        ),
        language=LanguageService(translation_provider=TranslationProvider(settings=settings), tracer=tracer),
        research=research_service,
    )

    if settings.seed_demo_data:
        repo.seed_demo_dataset()

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.state.services = services
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
