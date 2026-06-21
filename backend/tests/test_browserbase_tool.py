"""Tests for the Browserbase researcher tool (the `browse` CLI wrapper).

`subprocess.run` and `shutil.which` are mocked so nothing is actually executed.
"""

import json
import types

import pytest

from app.agents.tools import browserbase_research as bb
from app.core.config import settings


def _proc(stdout="", stderr="", returncode=0):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


@pytest.fixture
def browse_on_path(monkeypatch):
    """Pretend the `browse` CLI is installed."""
    monkeypatch.setattr(bb.shutil, "which", lambda _name: "/usr/local/bin/browse")


def test_missing_browserbase_key_raises(monkeypatch, browse_on_path):
    monkeypatch.setattr(settings, "browserbase_api_key", None)
    with pytest.raises(RuntimeError, match="BROWSERBASE_API_KEY is not set"):
        bb.search_web("anything")


def test_missing_cli_raises(monkeypatch, fake_keys):
    monkeypatch.setattr(bb.shutil, "which", lambda _name: None)
    with pytest.raises(bb.BrowserbaseError, match="not found on PATH"):
        bb.search_web("anything")


def test_nonzero_exit_raises(monkeypatch, fake_keys, browse_on_path):
    monkeypatch.setattr(
        bb.subprocess, "run", lambda *a, **k: _proc(stderr="boom", returncode=1)
    )
    with pytest.raises(bb.BrowserbaseError, match="boom"):
        bb.fetch_page("https://example.com")


def test_search_web_normalizes_shapes(monkeypatch, fake_keys, browse_on_path):
    payload = {
        "results": [
            {"url": "https://a", "title": "A", "description": "da"},
            {"link": "https://b", "name": "B"},  # alternate key names
            {"title": "no url"},  # dropped — no url
        ]
    }
    monkeypatch.setattr(
        bb.subprocess, "run", lambda *a, **k: _proc(stdout=json.dumps(payload))
    )
    results = bb.search_web("query")
    assert [r["url"] for r in results] == ["https://a", "https://b"]
    assert results[0]["snippet"] == "da"
    assert results[1]["title"] == "B"


def test_search_web_passes_browserbase_key_to_subprocess(
    monkeypatch, fake_keys, browse_on_path
):
    captured = {}

    def spy(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env", {})
        return _proc(stdout="[]")

    monkeypatch.setattr(bb.subprocess, "run", spy)
    bb.search_web("query")
    assert captured["cmd"][:3] == ["browse", "cloud", "search"]
    assert captured["env"]["BROWSERBASE_API_KEY"] == "test-browserbase-key"


def test_gather_research_clamps_to_max_pages(monkeypatch, fake_keys, browse_on_path):
    # Ten candidates available, but the tool must read at most MAX_PAGES.
    def fake_run(cmd, **kwargs):
        if cmd[2] == "search":
            urls = [{"url": f"https://p{i}"} for i in range(10)]
            return _proc(stdout=json.dumps({"results": urls}))
        return _proc(stdout=f"content of {cmd[3]}")

    monkeypatch.setattr(bb.subprocess, "run", fake_run)
    pages = bb.gather_research("query", max_pages=99)  # over-asking is clamped
    assert len(pages) == bb.MAX_PAGES
    assert all(p.content for p in pages)


def test_gather_research_skips_failed_fetches(monkeypatch, fake_keys, browse_on_path):
    # First two pages fail to fetch; the tool should skip them and still reach
    # MIN_PAGES from the remaining candidates.
    def fake_run(cmd, **kwargs):
        if cmd[2] == "search":
            urls = [{"url": f"https://p{i}"} for i in range(6)]
            return _proc(stdout=json.dumps({"results": urls}))
        url = cmd[3]
        if url in ("https://p0", "https://p1"):
            return _proc(stderr="dead link", returncode=1)
        return _proc(stdout=f"content of {url}")

    monkeypatch.setattr(bb.subprocess, "run", fake_run)
    pages = bb.gather_research("query", max_pages=bb.MIN_PAGES)
    assert len(pages) == bb.MIN_PAGES
    assert "https://p0" not in [p.url for p in pages]


def test_gather_research_json_is_serializable(monkeypatch, fake_keys, browse_on_path):
    def fake_run(cmd, **kwargs):
        if cmd[2] == "search":
            return _proc(stdout=json.dumps({"results": [{"url": "https://a"}]}))
        return _proc(stdout="hello world")

    monkeypatch.setattr(bb.subprocess, "run", fake_run)
    out = bb.gather_research_json("query")
    parsed = json.loads(out)
    assert parsed["query"] == "query"
    assert parsed["page_count"] == len(parsed["pages"]) >= 1
