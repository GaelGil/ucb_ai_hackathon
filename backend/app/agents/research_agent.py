"""Research agent.

A Claude agent that researches one of two topics for a given language:

  * ``pos``       -> part-of-speech (POS) tagging resources for the language
  * ``translate`` -> translation resources for the language

It is given a single tool, ``research_web``, which is the Browserbase-backed
researcher in ``app.agents.tools.browserbase_research``. The agent decides what
to search for, the tool visits 3-5 pages, and the agent returns synthesized
notes on what it found.

Usage::

    from app.agents.research_agent import run_research
    notes = run_research("Tigrinya", "pos")
"""

from __future__ import annotations

from anthropic import Anthropic

from app.agents.tools.browserbase_research import (
    MAX_PAGES,
    MIN_PAGES,
    BrowserbaseError,
    gather_research_json,
)
from app.core.config import settings

# The latest, most capable Claude model at time of writing.
MODEL = "claude-opus-4-8"
MAX_TOKENS = 4096

# Cap how many times the agent may call the research tool, so a misbehaving
# loop can't run forever.
MAX_TOOL_CALLS = 4

# Map the endpoint's `type` value onto a human description of the topic.
_RESEARCH_TOPICS = {
    "pos": "part-of-speech (POS) tagging",
    "pos_tagging": "part-of-speech (POS) tagging",
    "translate": "translation",
    "translation": "translation",
}


def _normalize_type(research_type: str) -> str:
    key = (research_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key not in _RESEARCH_TOPICS:
        raise ValueError(
            f"Unknown research type {research_type!r}. "
            f"Expected one of: {sorted(set(_RESEARCH_TOPICS))}."
        )
    return key


_RESEARCH_TOOL = {
    "name": "research_web",
    "description": (
        "Search the web via Browserbase and read several pages about a topic. "
        f"Visits at least {MIN_PAGES} and at most {MAX_PAGES} pages, returning "
        "their URLs, titles, and markdown content. Call this with a focused "
        "search query."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A focused web search query for the research topic.",
            }
        },
        "required": ["query"],
    },
}


def _build_prompt(language_name: str, topic: str) -> str:
    return (
        f"Research existing work and resources on {topic} for the "
        f"{language_name} language.\n\n"
        f"Use the `research_web` tool to search the internet and read pages. "
        f"Visit at least {MIN_PAGES} and no more than {MAX_PAGES} pages. You may "
        "refine your query and search again if the first results are weak, but "
        f"do not exceed {MAX_PAGES} pages total.\n\n"
        "Then write concise, well-organized notes covering: existing datasets "
        "or corpora, tools/models/libraries, key papers or projects, tagsets or "
        "standards where relevant, and how much support the language currently "
        "has. Cite the source URL for each notable finding. If little exists, "
        "say so explicitly."
    )


def _system_prompt(language_name: str, topic: str) -> str:
    return (
        "You are a meticulous research assistant specializing in computational "
        "linguistics and low-resource language technology. You gather evidence "
        "by browsing the web and report grounded, source-cited notes. You never "
        "fabricate resources — every claim about a dataset, tool, or paper must "
        "come from a page you actually read via the research tool. You are "
        f"researching {topic} for the {language_name} language."
    )


def run_research(language_name: str, research_type: str) -> str:
    """Run the research agent and return synthesized notes as text.

    Args:
        language_name: Name of the language to research (e.g. "Tigrinya").
        research_type: Either ``"pos"`` or ``"translate"`` (aliases accepted).

    Returns:
        The agent's final notes as a string.
    """
    if not language_name or not language_name.strip():
        raise ValueError("language_name must be a non-empty string.")

    topic = _RESEARCH_TOPICS[_normalize_type(research_type)]

    # Pass the key explicitly so a missing key fails loudly and early.
    client = Anthropic(api_key=settings.require_anthropic_api_key())

    messages: list[dict] = [
        {"role": "user", "content": _build_prompt(language_name, topic)}
    ]
    system = _system_prompt(language_name, topic)

    tool_calls = 0
    # A generous ceiling on turns: each tool call costs two turns (request +
    # result) plus a final synthesis turn.
    for _ in range(MAX_TOOL_CALLS * 2 + 2):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[_RESEARCH_TOOL],
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return _collect_text(response.content)

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue

            if block.name == "research_web" and tool_calls < MAX_TOOL_CALLS:
                tool_calls += 1
                query = (block.input or {}).get("query", "")
                try:
                    result = gather_research_json(query)
                    is_error = False
                except BrowserbaseError as exc:
                    result = f"Research tool error: {exc}"
                    is_error = True
            else:
                # Either an unknown tool or we've hit the page/call budget.
                result = (
                    "Page budget reached — do not call research_web again. "
                    "Synthesize your notes from the results already gathered."
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

    # Budget exhausted without a final text answer: ask once more for notes.
    messages.append(
        {
            "role": "user",
            "content": "Stop researching now and write your final notes.",
        }
    )
    final = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
    )
    return _collect_text(final.content)


def _collect_text(content: list) -> str:
    """Concatenate the text blocks of a Claude response."""
    parts = [
        block.text
        for block in content
        if getattr(block, "type", None) == "text"
    ]
    return "\n".join(parts).strip()
