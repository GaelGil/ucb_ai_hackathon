from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

# `pool_pre_ping` avoids stale connections, which matters with Supabase's
# connection pooler. Supabase requires SSL; the sslmode is part of the URL.
engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,
)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session (use as a FastAPI dependency)."""
    with Session(engine) as session:
        yield session
