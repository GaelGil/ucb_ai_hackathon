"""Shared pytest fixtures.

Tests run fully offline: no real Anthropic/Browserbase keys and no Postgres.
The database is an in-memory SQLite built from the SQLModel metadata, and the
agents are monkeypatched per-test.
"""

import types

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Importing the models package registers every table on SQLModel.metadata,
# which create_all() needs.
import app.src.database.models  # noqa: F401
from app.src.config import Settings

settings = Settings(_env_file=None)

collect_ignore = [
    "test_browserbase_tool.py",
    "test_data_agent.py",
    "test_data_service.py",
    "test_research_agent.py",
    "test_research_service.py",
]


@pytest.fixture
def session():
    """An isolated in-memory SQLite session with all tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def fake_keys(monkeypatch):
    """Pretend both API keys are configured so the fail-loud guards pass."""
    monkeypatch.setattr(settings, "anthropic_api_key", "test-anthropic-key")
    monkeypatch.setattr(settings, "BROWSERBASE_API_KEY", "test-browserbase-key")


# --- Helpers for faking the Anthropic SDK -------------------------------------


def block(**kwargs) -> types.SimpleNamespace:
    """Build a fake content block (text or tool_use)."""
    return types.SimpleNamespace(**kwargs)


def response(stop_reason: str, content: list) -> types.SimpleNamespace:
    """Build a fake Messages.create() response."""
    return types.SimpleNamespace(stop_reason=stop_reason, content=content)


def fake_anthropic_factory(responses):
    """Return a stand-in for the Anthropic class that replays `responses`.

    Each call to client.messages.create(...) returns the next queued response.
    """

    class _FakeMessages:
        def __init__(self):
            self._i = 0

        def create(self, **kwargs):
            resp = responses[self._i]
            self._i += 1
            return resp

    class _FakeAnthropic:
        def __init__(self, *args, **kwargs):
            self.messages = _FakeMessages()

    return _FakeAnthropic
