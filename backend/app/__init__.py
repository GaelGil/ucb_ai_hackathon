"""LangBase backend application package."""
from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlmodel import SQLModel, Session
from werkzeug.exceptions import HTTPException

import app.database.models  # noqa: F401  (registers SQLModel tables)
from app.routes.data.routes import bp as data_bp
from app.routes.dataset.routes import bp as dataset_bp
from app.routes.dataset.service import DatasetService
from app.routes.context import AppServices, SERVICES_CONFIG_KEY, close_db_session
from app.routes.labels.routes import bp as labels_bp
from app.routes.language.routes import bp as language_bp
from app.routes.research.routes import bp as research_bp
from app.config import Settings, get_settings
from app.database.session import create_database_engine, engine as default_engine
from app.providers import BrowserbaseResearchProvider, OCRProvider, PosAnnotationProvider, TranslationProvider
from app.exceptions import NotFoundError
from app.storage import SupabaseStorage
from app.tracing import Tracer


def create_app(
    repository: object | None = None,
    settings: Settings | None = None,
    engine: Engine | None = None,
    create_tables: bool | None = None,
) -> Flask:
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
        research_provider=BrowserbaseResearchProvider(settings=settings, tracer=tracer),
        ocr_provider=OCRProvider(settings=settings, tracer=tracer),
        pos_provider=PosAnnotationProvider(settings=settings, tracer=tracer),
        translation_provider=TranslationProvider(settings=settings, tracer=tracer),
        storage=SupabaseStorage(settings),
    )

    if settings.seed_demo_data:
        with Session(db_engine) as session:
            DatasetService(session=session).seed_demo_dataset()

    flask_app = Flask(__name__)
    flask_app.config["APP_NAME"] = settings.app_name
    flask_app.config["APP_VERSION"] = settings.app_version
    flask_app.config[SERVICES_CONFIG_KEY] = services
    flask_app.teardown_appcontext(close_db_session)

    CORS(
        flask_app,
        origins=settings.cors_origins,
        supports_credentials=True,
        methods=["*"],
        allow_headers=["*"],
    )

    @flask_app.errorhandler(NotFoundError)
    def not_found_handler(exc: NotFoundError):
        return jsonify(detail=str(exc)), 404

    @flask_app.errorhandler(ValidationError)
    def validation_error_handler(exc: ValidationError):
        return jsonify(detail=exc.errors(include_url=False)), 422

    @flask_app.errorhandler(HTTPException)
    def http_exception_handler(exc: HTTPException):
        # Render framework errors (404/405/...) as JSON. Aborts that already
        # carry a JSON response (see responses.json_abort) pass through untouched.
        if exc.response is not None:
            return exc.response
        return jsonify(detail=exc.description), exc.code

    @flask_app.get("/health")
    def health():
        return jsonify(status="ok")

    flask_app.register_blueprint(dataset_bp)
    flask_app.register_blueprint(data_bp)
    flask_app.register_blueprint(research_bp)
    flask_app.register_blueprint(labels_bp)
    flask_app.register_blueprint(language_bp)
    return flask_app
