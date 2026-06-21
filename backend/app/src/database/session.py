from collections.abc import Generator

from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from app.src.config import Settings, get_settings

import app.src.database.models  # noqa: F401  (registers SQLModel tables)


def create_database_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    return create_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        pool_recycle=300,
    )


engine = create_database_engine()


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def get_session(db_engine: Engine | None = None) -> Generator[Session, None, None]:
    """Yield a database session for scripts and one-off tasks."""
    database_engine = db_engine or engine
    with Session(database_engine) as session:
        yield session
