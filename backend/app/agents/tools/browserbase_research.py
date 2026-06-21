"""Browserbase-backed research tool.

This is the concrete tool the research agent calls. It drives Browserbase
through the installed `browse` CLI (a subprocess), so no Browserbase SDK
dependency is needed in Python:

  1. `browse cloud search` finds candidate pages for a query.
  2. `browse cloud fetch --format markdown` reads each page as markdown.

It deliberately visits at least ``MIN_PAGES`` and at most ``MAX_PAGES`` pages.

Requires the `browse` CLI on PATH and ``BROWSERBASE_API_KEY`` in the
environment (the CLI reads it itself).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass

# The agent is asked to visit at least 3 and no more than 5 pages.
MIN_PAGES = 3
MAX_PAGES = 5

# Keep per-page content bounded so a single huge page can't blow up the
# context window we hand back to the model.
_MAX_CHARS_PER_PAGE = 8000


class BrowserbaseError(RuntimeError):
    """Raised when the `browse` CLI is missing or returns a non-zero status."""


@dataclass
class ResearchPage:
    url: str
    title: str
    content: str


def _run_browse(args: list[str], timeout: int = 150) -> str:
    """Run a `browse` subcommand and return its stdout, raising on failure."""
    if shutil.which("browse") is None:
        raise BrowserbaseError(
            "`browse` CLI not found on PATH. Install it with `npm install -g browse`."
        )
    try:
        proc = subprocess.run(
            ["browse", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - environment dependent
        raise BrowserbaseError(f"`browse {' '.join(args)}` timed out") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise BrowserbaseError(f"`browse {' '.join(args)}` failed: {detail}")
    return proc.stdout


def _extract_results(payload: object) -> list[dict]:
    """Normalize the various shapes `browse cloud search --json` may return."""
    if isinstance(payload, list):
        results = payload
    elif isinstance(payload, dict):
        results = (
            payload.get("results")
            or payload.get("data")
            or payload.get("items")
            or []
        )
    else:
        results = []

    normalized: list[dict] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("link") or item.get("href")
        if not url:
            continue
        normalized.append(
            {
                "url": url,
                "title": item.get("title") or item.get("name") or "",
                "snippet": item.get("description") or item.get("snippet") or "",
            }
        )
    return normalized


def search_web(query: str, num_results: int = 10) -> list[dict]:
    """Return a list of {url, title, snippet} dicts for a search query."""
    num_results = max(1, min(num_results, 25))
    out = _run_browse(
        ["cloud", "search", query, "--json", "--num-results", str(num_results)]
    )
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        raise BrowserbaseError(f"Could not parse search output as JSON: {out[:200]}") from exc
    return _extract_results(payload)


def fetch_page(url: str) -> str:
    """Fetch a single page as markdown."""
    return _run_browse(["cloud", "fetch", url, "--format", "markdown"]).strip()


def gather_research(query: str, max_pages: int = MAX_PAGES) -> list[ResearchPage]:
    """Search the web for ``query`` and read between MIN_PAGES and max_pages.

    Walks the search results in order, fetching each page until ``max_pages``
    successful reads are collected. Pages that fail to fetch are skipped so a
    single dead link doesn't abort the run.
    """
    max_pages = max(MIN_PAGES, min(max_pages, MAX_PAGES))

    # Over-fetch search results so failed pages still leave room to reach the
    # minimum page count.
    candidates = search_web(query, num_results=max_pages * 2 + 2)

    pages: list[ResearchPage] = []
    for candidate in candidates:
        if len(pages) >= max_pages:
            break
        try:
            content = fetch_page(candidate["url"])
        except BrowserbaseError:
            continue
        if not content:
            continue
        pages.append(
            ResearchPage(
                url=candidate["url"],
                title=candidate["title"],
                content=content[:_MAX_CHARS_PER_PAGE],
            )
        )
    return pages


def gather_research_json(query: str, max_pages: int = MAX_PAGES) -> str:
    """Same as ``gather_research`` but serialized to a JSON string for tool I/O."""
    pages = gather_research(query, max_pages=max_pages)
    return json.dumps(
        {"query": query, "page_count": len(pages), "pages": [asdict(p) for p in pages]},
        ensure_ascii=False,
    )
