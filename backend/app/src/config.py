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
    seed_demo_data: bool = True

    browserbase_api_key: str | None = None
    browserbase_base_url: str = "https://api.browserbase.com"

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4.1-mini"

    phoenix_enabled: bool = False
    phoenix_otel_endpoint: str = "http://localhost:6006/v1/traces"
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
