import json as json_module

import pytest
import httpx

from app.config import Settings
from app.models import Dataset
from app.providers import BrowserbaseResearchProvider, JsonCompletion
from app.tracing import Tracer


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
    monkeypatch.setattr("app.providers.httpx.Client", fake_client)
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


def test_browserbase_empty_search_still_fails_without_calling_llm(monkeypatch) -> None:
    fake_client, _ = make_fake_http_client(search_payload={"results": []})
    monkeypatch.setattr("app.providers.httpx.Client", fake_client)
    fake_llm = FakeLLM()
    provider = provider_with(fake_llm)

    with pytest.raises(RuntimeError, match="Browserbase returned no usable sources"):
        provider.create_research(
            Dataset(name="Nahuatl", language_code="nah", language_name="Nahuatl"),
            ["amoxtli"],
            "translation",
        )

    assert fake_llm.calls == []
