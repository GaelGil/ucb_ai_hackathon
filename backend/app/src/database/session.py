from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from app.src.config import Settings, get_settings


def create_database_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return create_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
    )


def get_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """Yield a database session for scripts and one-off tasks."""
    database_engine = engine or create_database_engine()
    with Session(database_engine) as session:
        yield session
