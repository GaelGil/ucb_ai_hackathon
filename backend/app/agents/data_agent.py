"""Data-gathering agent.

A Claude agent that finds naturally-occurring sentences written in a given
language, so they can be saved into our dataset.

It uses the *same* Browserbase-backed researcher tool as the research agent
(``app.agents.tools.browserbase_research``) — search the web and read 3-5
pages — but instead of writing notes, it extracts sentences from those pages
and returns them as a plain list of strings.

Usage::

    from app.agents.data_agent import run_get_more_data
    sentences = run_get_more_data("Tigrinya")
"""

from __future__ import annotations

import json
import re

from anthropic import Anthropic

from app.agents.tools.browserbase_research import (
    MAX_PAGES,
    MIN_PAGES,
    BrowserbaseError,
    gather_research_json,
)

MODEL = "claude-opus-4-8"
MAX_TOKENS = 4096

# Cap how many times the agent may call the search tool.
MAX_TOOL_CALLS = 4

# Default ceiling on how many sentences to return.
DEFAULT_MAX_SENTENCES = 50

# Same Browserbase tool as the research agent — it searches the web and reads
# 3-5 pages. Only the name/description differ to signal we want raw sentences.
_SEARCH_TOOL = {
    "name": "search_web_for_sentences",
    "description": (
        "Search the web via Browserbase and read several pages written in the "
        f"target language. Visits at least {MIN_PAGES} and at most {MAX_PAGES} "
        "pages, returning their URLs, titles, and markdown content. Call this "
        "with a focused search query likely to surface text written in the "
        "language (e.g. news sites, Wikipedia, stories, forums in that language)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A focused web search query likely to surface pages written in the target language.",
            }
        },
        "required": ["query"],
    },
}


def _system_prompt(language_name: str) -> str:
    return (
        "You are a data-collection assistant building a text corpus for a "
        f"low-resource language: {language_name}. Your job is to find real, "
        f"naturally-occurring sentences written in {language_name} by browsing "
        "the web. You only collect sentences that are genuinely written in "
        f"{language_name} — never translations into English, navigation labels, "
        "boilerplate, or text in other languages. You never invent sentences."
    )


def _build_prompt(language_name: str, max_sentences: int) -> str:
    return (
        f"Collect up to {max_sentences} sentences written in the {language_name} "
        "language.\n\n"
        "Use the `search_web_for_sentences` tool to search the internet and read "
        f"pages. Visit at least {MIN_PAGES} and no more than {MAX_PAGES} pages. "
        "You may refine your query and search again if the first results are "
        f"weak, but do not exceed {MAX_PAGES} pages total.\n\n"
        f"From the page content, extract complete, well-formed sentences that are "
        f"actually written in {language_name}. Discard English glosses, menus, "
        "code, and anything not in the target language. Deduplicate.\n\n"
        "Respond with ONLY a JSON array of strings — one sentence per element — "
        "and nothing else. Example: [\"sentence one\", \"sentence two\"]. "
        "If you cannot find any, return an empty array []."
    )


def run_get_more_data(
    language_name: str, max_sentences: int = DEFAULT_MAX_SENTENCES
) -> list[str]:
    """Run the data agent and return a list of sentences in the language.

    Args:
        language_name: Name of the language (e.g. "Tigrinya").
        max_sentences: Upper bound on how many sentences to return.

    Returns:
        A list of sentence strings written in the language.
    """
    if not language_name or not language_name.strip():
        raise ValueError("language_name must be a non-empty string.")

    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    messages: list[dict] = [
        {"role": "user", "content": _build_prompt(language_name, max_sentences)}
    ]
    system = _system_prompt(language_name)

    tool_calls = 0
    for _ in range(MAX_TOOL_CALLS * 2 + 2):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[_SEARCH_TOOL],
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return _parse_sentences(_collect_text(response.content), max_sentences)

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue

            if block.name == "search_web_for_sentences" and tool_calls < MAX_TOOL_CALLS:
                tool_calls += 1
                query = (block.input or {}).get("query", "")
                try:
                    result = gather_research_json(query)
                    is_error = False
                except BrowserbaseError as exc:
                    result = f"Search tool error: {exc}"
                    is_error = True
            else:
                result = (
                    "Page budget reached — do not search again. Return the JSON "
                    "array of sentences gathered so far."
                )
                is_error = True

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                    "is_error": is_error,
                }
            )

        messages.append({"role": "user", "content": tool_results})

    # Budget exhausted: ask once more for the final list.
    messages.append(
        {
            "role": "user",
            "content": "Stop searching now and return ONLY the JSON array of sentences.",
        }
    )
    final = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
    )
    return _parse_sentences(_collect_text(final.content), max_sentences)


def _collect_text(content: list) -> str:
    """Concatenate the text blocks of a Claude response."""
    parts = [
        block.text for block in content if getattr(block, "type", None) == "text"
    ]
    return "\n".join(parts).strip()


def _parse_sentences(text: str, max_sentences: int) -> list[str]:
    """Pull a JSON array of strings out of the agent's final answer.

    Tolerates surrounding prose or code fences by extracting the first
    bracketed JSON array.
    """
    if not text:
        return []

    candidate = text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        candidate = match.group(0)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    sentences: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if s and s not in seen:
            seen.add(s)
            sentences.append(s)
        if len(sentences) >= max_sentences:
            break
    return sentences
