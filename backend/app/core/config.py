from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Full SQLAlchemy connection string to the Supabase Postgres database, e.g.
    # postgresql+psycopg2://postgres:<password>@<host>:5432/postgres
    database_url: str

    # Echo SQL statements to stdout (handy while developing).
    db_echo: bool = False


settings = Settings()
