import json as json_module

import pytest
import httpx

from app.src.config import Settings
from app.src.models import Dataset, ResearchArtifact, ResearchSource
from app.src.providers import BrowserbaseResearchProvider, JsonCompletion, PosAnnotationProvider
from app.src.tracing import Tracer


class FakeLLM:
    provider = "anthropic"
    model = "fake-claude"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete_json(self, *, task_name, system, prompt, max_tokens=None):
        self.calls.append({"task_name": task_name, "system": system, "prompt": prompt, "max_tokens": max_tokens})
        return JsonCompletion(
            data={
                "summary": "Nahuatl translation notes from search results.",
                "guidelines": ["Use reviewer examples first."],
                "examples": ["amoxtli -> book"],
                "evaluation": {"score": 0.8, "feedback": "Useful enough for demo."},
            },
            usage={"input_tokens": 10, "output_tokens": 20},
        )


class FakePosLLM:
    provider = "anthropic"
    model = "fake-claude"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete_json(self, *, task_name, system, prompt, max_tokens=None):
        self.calls.append({"task_name": task_name, "system": system, "prompt": prompt, "max_tokens": max_tokens})
        return JsonCompletion(
            data={
                "tokens": [
                    {
                        "index": 0,
                        "token": "amoxtli",
                        "suggested_pos": "NOUN",
                        "confidence": 0.82,
                        "rationale": "Research notes support this as a nominal form.",
                    }
                ],
                "rationale": "Used cached POS research.",
            },
            usage={"input_tokens": 8, "output_tokens": 12},
        )


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, url: str) -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = json_module.dumps(payload).encode("utf-8")
        self._response = httpx.Response(status_code, request=httpx.Request("POST", url), json=payload)

    def raise_for_status(self) -> None:
        self._response.raise_for_status()

    def json(self) -> dict:
        return self._payload


def make_fake_http_client(*, search_payload: dict, fetch_status: int = 402, fetch_payload: dict | None = None):
    calls: list[tuple[str, dict | None]] = []

    class FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, headers=None, json=None):
            calls.append((url, json))
            if url.endswith("/v1/search"):
                return FakeResponse(200, search_payload, url)
            if url.endswith("/v1/fetch"):
                return FakeResponse(fetch_status, fetch_payload or {"error": "Payment Required"}, url)
            raise AssertionError(f"Unexpected URL: {url}")

    return FakeHttpClient, calls


def provider_with(fake_llm: FakeLLM) -> BrowserbaseResearchProvider:
    settings = Settings(
        _env_file=None,
        BROWSERBASE_API_KEY="test-browserbase-key",
        anthropic_api_key="test-anthropic-key",
        arize_enabled=False,
        phoenix_enabled=False,
    )
    return BrowserbaseResearchProvider(
        settings=settings,
        api_key="test-browserbase-key",
        llm=fake_llm,
        tracer=Tracer(settings),
    )


def test_browserbase_fetch_402_falls_back_to_search_results(monkeypatch) -> None:
    fake_client, calls = make_fake_http_client(
        search_payload={
            "results": [
                {
                    "url": "https://example.test/nahuatl",
                    "title": "Nahuatl transcription",
                    "snippet": "Nahuatl orthography and translation example notes.",
                }
            ]
        },
        fetch_status=402,
    )
    monkeypatch.setattr("app.src.providers.httpx.Client", fake_client)
    fake_llm = FakeLLM()
    provider = provider_with(fake_llm)

    artifact = provider.create_research(
        Dataset(name="Nahuatl", language_code="nah", language_name="Nahuatl"),
        ["amoxtli"],
        "translation",
    )

    assert any(url.endswith("/v1/search") for url, _ in calls)
    assert any(url.endswith("/v1/fetch") for url, _ in calls)
    assert len(fake_llm.calls) == 1
    assert artifact.summary == "Nahuatl translation notes from search results."
    assert artifact.sources[0].url == "https://example.test/nahuatl"
    assert artifact.sources[0].excerpt == "Nahuatl orthography and translation example notes."
    assert artifact.metadata["source_mode"] == "browserbase_search_fallback"
    assert artifact.warnings[0].provider == "browserbase"
    assert artifact.warnings[0].stage == "browserbase.fetch"
    assert "search results only" in artifact.warnings[0].message


def test_pos_research_query_and_prompt_are_syntax_focused(monkeypatch) -> None:
    fake_client, calls = make_fake_http_client(
        search_payload={
            "results": [
                {
                    "url": "https://example.test/nahuatl-pos",
                    "title": "Nahuatl syntax",
                    "snippet": "Nahuatl word order, morphology, particles, and POS tagging examples.",
                }
            ]
        },
        fetch_status=402,
    )
    monkeypatch.setattr("app.src.providers.httpx.Client", fake_client)
    fake_llm = FakeLLM()
    provider = provider_with(fake_llm)

    provider.create_research(
        Dataset(name="Nahuatl", language_code="nah", language_name="Nahuatl"),
        ["amoxtli"],
        "pos",
    )

    search_payload = next(payload for url, payload in calls if url.endswith("/v1/search"))
    query = search_payload["query"]
    assert "word order" in query
    assert "SVO" in query
    assert "SOV" in query
    assert "VSO" in query
    assert "syntax" in query
    assert "morphology" in query
    assert "UPOS" in query

    prompt = json_module.loads(fake_llm.calls[0]["prompt"])
    prompt_text = json_module.dumps(prompt)
    assert prompt["task"] == "part-of-speech tagging guidance using Universal Dependencies UPOS tags"
    assert "word order" in prompt_text
    assert "SVO" in prompt_text
    assert "SOV" in prompt_text
    assert "morphology" in prompt_text
    assert "upos_inventory" in prompt["required_json_shape"]
    assert "token -> UPOS -> reason" in prompt_text


def test_pos_suggestion_prompt_requires_cached_research_context() -> None:
    settings = Settings(
        _env_file=None,
        anthropic_api_key="test-anthropic-key",
        arize_enabled=False,
        phoenix_enabled=False,
    )
    fake_llm = FakePosLLM()
    provider = PosAnnotationProvider(settings=settings, llm=fake_llm, tracer=Tracer(settings))
    research = ResearchArtifact(
        dataset_id="ds_test",
        language_code="nah",
        type="pos",
        summary="Nahuatl POS notes: flexible word order and rich morphology matter for tagging.",
        guidelines=["Use syntax and morphology notes before assigning UPOS tags."],
        sources=[ResearchSource(title="Nahuatl syntax", url="https://example.test", excerpt="word order and POS notes")],
        metadata={"language_profile": {"basic_word_order": "free/flexible"}},
    )

    provider.suggest("amoxtli", research)

    call = fake_llm.calls[0]
    prompt = json_module.loads(call["prompt"])
    assert "syntax, morphology, word order, and POS inventory" in call["system"]
    assert prompt["research"]["summary"] == research.summary
    assert any("cached POS research" in instruction for instruction in prompt["instructions"])
    assert any("token indexes" in instruction for instruction in prompt["instructions"])


def test_browserbase_empty_search_still_fails_without_calling_llm(monkeypatch) -> None:
    fake_client, _ = make_fake_http_client(search_payload={"results": []})
    monkeypatch.setattr("app.src.providers.httpx.Client", fake_client)
    fake_llm = FakeLLM()
    provider = provider_with(fake_llm)

    with pytest.raises(RuntimeError, match="Browserbase returned no usable sources"):
        provider.create_research(
            Dataset(name="Nahuatl", language_code="nah", language_name="Nahuatl"),
            ["amoxtli"],
            "translation",
        )

    assert fake_llm.calls == []
