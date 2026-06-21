from logging.config import fileConfig
import os

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context

# Load app settings (DATABASE_URL from .env) and import every model so that
# they register on SQLModel.metadata for autogenerate.
from app.src.config import BACKEND_ROOT, get_settings
import app.src.database.models  # noqa: F401  (registers all tables)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Load dotenv files explicitly for Alembic, then inject the runtime URL so
# migrations never use the placeholder in alembic.ini.
load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(BACKEND_ROOT / ".env.local")

settings = get_settings()
database_url = os.getenv("DATABASE_URL") or settings.database_url
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for 'autogenerate' support.
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
