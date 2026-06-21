"""Tests for ResearchService: persistence, language resolution, failure safety."""

import pytest

import app.api.research.service as svc
from app.database.models.language import Language
from app.database.repositories.language import LanguageRepository


def test_run_research_persists_notes_and_creates_language(session, monkeypatch):
    monkeypatch.setattr(
        svc, "run_research_agent", lambda name, type: f"notes for {name} ({type})"
    )
    research = svc.ResearchService(session).run_research("Quechua", "pos")

    assert research.id is not None
    assert research.type == "pos"
    assert research.notes == "notes for Quechua (pos)"

    language = LanguageRepository(session).get_by_name("Quechua")
    assert language is not None
    assert research.language_id == language.id


def test_run_research_reuses_existing_language(session, monkeypatch):
    existing = LanguageRepository(session).create(Language(name="Quechua"))
    monkeypatch.setattr(svc, "run_research_agent", lambda name, type: "notes")

    research = svc.ResearchService(session).run_research("Quechua", "translate")

    assert research.language_id == existing.id
    # No duplicate language created.
    statement_count = len(LanguageRepository(session).list())
    assert statement_count == 1


def test_agent_failure_writes_nothing(session, monkeypatch):
    """The 'axolot' scenario: a failing agent must not leave a junk row."""

    def boom(name, type):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    monkeypatch.setattr(svc, "run_research_agent", boom)

    with pytest.raises(RuntimeError):
        svc.ResearchService(session).run_research("axolot", "pos")

    assert LanguageRepository(session).get_by_name("axolot") is None
