from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlmodel import SQLModel, Session
from werkzeug.exceptions import HTTPException

import app.src.database.models  # noqa: F401  (registers SQLModel tables)
from app.src.api.data.controller import bp as data_bp
from app.src.api.dataset.controller import bp as dataset_bp
from app.src.api.dataset.service import DatasetService
from app.src.api.dependencies import AppServices, SERVICES_CONFIG_KEY, close_db_session
from app.src.api.labels.controller import bp as labels_bp
from app.src.api.language.controller import bp as language_bp
from app.src.api.research.controller import bp as research_bp
from app.src.config import Settings, get_settings
from app.src.database.session import create_database_engine
from app.src.providers import BrowserbaseResearchProvider, OCRProvider, PosAnnotationProvider, TranslationProvider
from app.src.repositories import NotFoundError
from app.src.storage import SupabaseStorage
from app.src.tracing import Tracer


def create_app(
    repository: object | None = None,
    settings: Settings | None = None,
    engine: Engine | None = None,
    create_tables: bool | None = None,
) -> Flask:
    del repository
    settings = settings or get_settings()
    engine = engine or create_database_engine(settings)
    should_create_tables = settings.create_db_on_startup if create_tables is None else create_tables
    if should_create_tables:
        SQLModel.metadata.create_all(engine)

    tracer = Tracer(settings)
    services = AppServices(
        settings=settings,
        engine=engine,
        tracer=tracer,
        research_provider=BrowserbaseResearchProvider(settings=settings),
        ocr_provider=OCRProvider(),
        pos_provider=PosAnnotationProvider(),
        translation_provider=TranslationProvider(settings=settings),
        storage=SupabaseStorage(settings),
    )

    if settings.seed_demo_data:
        with Session(engine) as session:
            DatasetService(session=session).seed_demo_dataset()

    app = Flask(__name__)
    app.config["APP_NAME"] = settings.app_name
    app.config["APP_VERSION"] = settings.app_version
    app.config[SERVICES_CONFIG_KEY] = services
    app.teardown_appcontext(close_db_session)

    CORS(
        app,
        origins=settings.cors_origins,
        supports_credentials=True,
        methods=["*"],
        allow_headers=["*"],
    )

    @app.errorhandler(NotFoundError)
    def not_found_handler(exc: NotFoundError):
        return jsonify(detail=str(exc)), 404

    @app.errorhandler(ValidationError)
    def validation_error_handler(exc: ValidationError):
        return jsonify(detail=exc.errors(include_url=False)), 422

    @app.errorhandler(HTTPException)
    def http_exception_handler(exc: HTTPException):
        # Render framework errors (404/405/...) as JSON. Aborts that already
        # carry a JSON response (see responses.json_abort) pass through untouched.
        if exc.response is not None:
            return exc.response
        return jsonify(detail=exc.description), exc.code

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    app.register_blueprint(dataset_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(labels_bp)
    app.register_blueprint(language_bp)
    return app
