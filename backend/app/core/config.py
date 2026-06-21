from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load the .env file into the process environment (os.environ) on import.
#
# pydantic-settings reads .env into the Settings object below, but it does NOT
# export the values into os.environ. The `browse` CLI subprocess (and any other
# library that reads os.environ directly) wouldn't see the keys otherwise.
# load_dotenv() bridges that gap so the keys are available both ways.
load_dotenv()


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

    # Claude API key for the research / data agents.
    anthropic_api_key: str | None = None

    # Browserbase API key, used by the `browse` CLI that the agents' tool drives.
    browserbase_api_key: str | None = None

    def require_anthropic_api_key(self) -> str:
        """Return the Anthropic key or raise a clear error if it's missing."""
        if not self.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to backend/.env or export it "
                "in the environment before running an agent."
            )
        return self.anthropic_api_key

    def require_browserbase_api_key(self) -> str:
        """Return the Browserbase key or raise a clear error if it's missing."""
        if not self.browserbase_api_key:
            raise RuntimeError(
                "BROWSERBASE_API_KEY is not set. Add it to backend/.env or export it "
                "in the environment before running an agent."
            )
        return self.browserbase_api_key


settings = Settings()
