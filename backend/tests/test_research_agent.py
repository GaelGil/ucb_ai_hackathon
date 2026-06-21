"""Tests for the research agent's tool-use loop and validation."""

import pytest

import app.agents.research_agent as ra
from tests.conftest import block, fake_anthropic_factory, response


def test_normalize_type_accepts_aliases():
    assert ra._normalize_type("pos") == "pos"
    assert ra._normalize_type("Translate") == "translate"
    assert ra._normalize_type("translation") == "translation"
    assert ra._normalize_type("POS tagging") == "pos_tagging"


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown research type"):
        ra._normalize_type("sentiment")


def test_empty_language_raises(fake_keys):
    with pytest.raises(ValueError, match="non-empty"):
        ra.run_research("   ", "pos")


def test_missing_key_raises_before_any_work(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        ra.run_research("Quechua", "pos")


def test_tool_use_loop_returns_final_notes(monkeypatch, fake_keys):
    calls = {"gather": 0}

    def fake_gather(query, **kwargs):
        calls["gather"] += 1
        return '{"query": "q", "page_count": 2, "pages": []}'

    monkeypatch.setattr(ra, "gather_research_json", fake_gather)

    # Turn 1: model calls the tool. Turn 2: model returns final notes.
    responses = [
        response(
            "tool_use",
            [block(type="tool_use", name="research_web", id="t1", input={"query": "Quechua POS"})],
        ),
        response("end_turn", [block(type="text", text="Final research notes.")]),
    ]
    monkeypatch.setattr(ra, "Anthropic", fake_anthropic_factory(responses))

    notes = ra.run_research("Quechua", "pos")
    assert notes == "Final research notes."
    assert calls["gather"] == 1


def test_immediate_answer_without_tool(monkeypatch, fake_keys):
    monkeypatch.setattr(ra, "gather_research_json", lambda *a, **k: "{}")
    responses = [response("end_turn", [block(type="text", text="Nothing to research.")])]
    monkeypatch.setattr(ra, "Anthropic", fake_anthropic_factory(responses))
    assert ra.run_research("Quechua", "translate") == "Nothing to research."


def test_tool_error_is_reported_to_model_not_raised(monkeypatch, fake_keys):
    def boom(query, **kwargs):
        raise ra.BrowserbaseError("browserbase down")

    monkeypatch.setattr(ra, "gather_research_json", boom)
    responses = [
        response(
            "tool_use",
            [block(type="tool_use", name="research_web", id="t1", input={"query": "x"})],
        ),
        response("end_turn", [block(type="text", text="Could not gather sources.")]),
    ]
    monkeypatch.setattr(ra, "Anthropic", fake_anthropic_factory(responses))
    # The agent should swallow the tool error, hand it back to the model, and
    # still return the model's final text.
    assert ra.run_research("Quechua", "pos") == "Could not gather sources."
