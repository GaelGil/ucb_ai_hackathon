from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "LangBase API"
    app_version: str = "0.1.0"
    environment: str = "development"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])
    seed_demo_data: bool = False
    database_url: str = Field(
        default="sqlite:///./langbase.db",
        description="SQLAlchemy database URL. Use Supabase Postgres in deployed environments.",
    )
    db_echo: bool = False
    create_db_on_startup: bool = False
    agent_jobs_background: bool = True

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "langbase-uploads"

    BROWSERBASE_API_KEY: str | None = None
    browserbase_base_url: str = "https://api.browserbase.com"

    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_version: str = "2023-06-01"
    anthropic_max_tokens: int = 1600

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4.1-mini"

    arize_enabled: bool = False
    arize_space_id: str | None = None
    arize_api_key: str | None = None
    arize_project_name: str = "langbase-hackathon"

    phoenix_enabled: bool = False
    phoenix_otel_endpoint: str = "http://localhost:6006/v1/traces"
    phoenix_api_key: str | None = None
    phoenix_project_name: str = "langbase-hackathon"
    otel_service_name: str = "langbase-backend"

    nahuatl_model_endpoint_url: str | None = None
    nahuatl_model_name: str = "somosnlp-hackathon-2022/t5-small-spanish-nahuatl"

    http_timeout_seconds: float = 30.0
    llm_timeout_seconds: float = 45.0

    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", BACKEND_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return value
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
