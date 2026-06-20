from app.src.config import Settings


def test_settings_loads_dotenv_file(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_NAME=Dotenv LangBase",
                "CORS_ORIGINS=http://localhost:3000,http://localhost:5173",
                "PHOENIX_ENABLED=true",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "Dotenv LangBase"
    assert settings.cors_origins == ["http://localhost:3000", "http://localhost:5173"]
    assert settings.phoenix_enabled is True


def test_environment_variables_override_dotenv(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("LLM_MODEL", "from-environment")

    settings = Settings(_env_file=env_file)

    assert settings.llm_model == "from-environment"
