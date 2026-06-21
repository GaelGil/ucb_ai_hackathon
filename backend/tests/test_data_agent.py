"""Tests for the data agent: sentence parsing and the tool-use loop."""

import pytest

import app.agents.data_agent as da
from tests.conftest import block, fake_anthropic_factory, response


def test_parse_plain_json_array():
    assert da._parse_sentences('["a", "b"]', 50) == ["a", "b"]


def test_parse_strips_code_fence_and_prose():
    text = 'Here you go:\n```json\n["x", "y"]\n```'
    assert da._parse_sentences(text, 50) == ["x", "y"]


def test_parse_dedupes_strips_and_skips_non_strings():
    assert da._parse_sentences('[" a ", "a", 3, "", "b"]', 50) == ["a", "b"]


def test_parse_respects_max():
    assert da._parse_sentences('["a", "b", "c"]', 2) == ["a", "b"]


def test_parse_garbage_returns_empty():
    assert da._parse_sentences("no json here", 50) == []
    assert da._parse_sentences("", 50) == []


def test_empty_language_raises(fake_keys):
    with pytest.raises(ValueError, match="non-empty"):
        da.run_get_more_data("")


def test_missing_key_raises(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        da.run_get_more_data("Quechua")


def test_tool_use_loop_returns_sentences(monkeypatch, fake_keys):
    monkeypatch.setattr(da, "gather_research_json", lambda *a, **k: '{"pages": []}')
    responses = [
        response(
            "tool_use",
            [block(type="tool_use", name="search_web_for_sentences", id="t1", input={"query": "Quechua news"})],
        ),
        response("end_turn", [block(type="text", text='["Ñuqaqa rimani.", "Allillanchu."]')]),
    ]
    monkeypatch.setattr(da, "Anthropic", fake_anthropic_factory(responses))

    sentences = da.run_get_more_data("Quechua")
    assert sentences == ["Ñuqaqa rimani.", "Allillanchu."]
