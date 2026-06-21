"""Tests for DataService: sentence persistence, dataset grouping, failure safety."""

import pytest

import app.api.data.service as svc
from app.database.models.data import DataType
from app.database.repositories.language import LanguageRepository


def test_get_more_data_persists_sentences_under_one_dataset(session, monkeypatch):
    monkeypatch.setattr(
        svc, "run_get_more_data", lambda name: ["sentence one", "sentence two"]
    )
    rows = svc.DataService(session).get_more_data("Quechua")

    assert len(rows) == 2
    assert {r.name for r in rows} == {"sentence one", "sentence two"}
    assert all(r.type == DataType.text for r in rows)

    # All sentences share a single freshly created dataset.
    dataset_ids = {r.dataset_id for r in rows}
    assert len(dataset_ids) == 1 and None not in dataset_ids

    language = LanguageRepository(session).get_by_name("Quechua")
    assert language is not None
    assert all(r.language_id == language.id for r in rows)


def test_empty_result_writes_nothing(session, monkeypatch):
    """No sentences found -> no language, dataset, or data rows created."""
    monkeypatch.setattr(svc, "run_get_more_data", lambda name: [])

    rows = svc.DataService(session).get_more_data("axolot")

    assert rows == []
    assert LanguageRepository(session).get_by_name("axolot") is None


def test_agent_failure_writes_nothing(session, monkeypatch):
    def boom(name):
        raise RuntimeError("BROWSERBASE_API_KEY is not set")

    monkeypatch.setattr(svc, "run_get_more_data", boom)

    with pytest.raises(RuntimeError):
        svc.DataService(session).get_more_data("axolot")

    assert LanguageRepository(session).get_by_name("axolot") is None
