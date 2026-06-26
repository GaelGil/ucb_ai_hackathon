from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.clients.anthropic import AnthropicClient
from app.clients.tracing import Tracer
from app.schemas import Dataset, ProviderWarning, ResearchArtifact, ResearchSource


class BrowserbaseResearchProvider:
    provider = "browserbase"

    def __init__(
        self,
        settings: Settings | None = None,
        api_key: str | None = None,
        llm: AnthropicClient | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.tracer = tracer or Tracer(self.settings)
        self.api_key = api_key or self.settings.BROWSERBASE_API_KEY
        self.llm = llm or AnthropicClient(self.settings, self.tracer)
        self.base_url = self.settings.browserbase_base_url.rstrip("/")
        self.model_name = self.llm.model

    def create_research(self, dataset: Dataset, samples: list[str], research_type: str = "pos") -> ResearchArtifact:
        print(
            "[research-debug] BrowserbaseResearchProvider.create_research reached "
            f"dataset_id={dataset.id} language={dataset.language_code} type={research_type} sample_count={len(samples)}",
            flush=True,
        )
        if not self.api_key:
            print("[research-debug] browserbase api key missing", flush=True)
            raise RuntimeError("BROWSERBASE_API_KEY is not configured.")

        query = self._research_query(dataset, research_type)
        print(
            "[research-debug] research query built "
            f"dataset_id={dataset.id} type={research_type} query={query!r}",
            flush=True,
        )
        sources, warnings = self._search_and_fetch(query)
        print(
            "[research-debug] browserbase search/fetch complete "
            f"dataset_id={dataset.id} type={research_type} source_count={len(sources)}",
            flush=True,
        )
        if not sources:
            print(
                "[research-debug] browserbase returned no usable sources "
                f"dataset_id={dataset.id} type={research_type}",
                flush=True,
            )
            raise RuntimeError("Browserbase returned no usable sources.")

        prompt = self._research_prompt(dataset, samples, sources, research_type)
        print(
            "[research-debug] calling anthropic for research summary "
            f"dataset_id={dataset.id} type={research_type} prompt_chars={len(prompt)} source_count={len(sources)}",
            flush=True,
        )
        completion = self.llm.complete_json(
            task_name=f"{research_type}_research",
            system="You are a careful low-resource language research assistant. Return only valid JSON.",
            prompt=prompt,
        )
        data = completion.data
        summary = str(data.get("summary") or "").strip()
        if not summary:
            print(
                "[research-debug] anthropic research response missing summary "
                f"dataset_id={dataset.id} type={research_type} keys={sorted(data.keys())}",
                flush=True,
            )
            raise RuntimeError("Anthropic research response did not include a summary.")

        guidelines = self._string_list(data.get("guidelines")) or self._guidelines(research_type)
        print(
            "[research-debug] research artifact built "
            f"dataset_id={dataset.id} type={research_type} summary_chars={len(summary)} "
            f"guideline_count={len(guidelines)}",
            flush=True,
        )
        metadata = {
            "provider": self.provider,
            "llm_provider": self.llm.provider,
            "model": self.llm.model,
            "query": query,
            "examples": data.get("examples") if isinstance(data.get("examples"), list) else [],
            "evaluation": data.get("evaluation") if isinstance(data.get("evaluation"), dict) else {},
            "language_profile": data.get("language_profile") or "",
            "task_notes": data.get("task_notes") or "",
            "usage": completion.usage,
        }
        if warnings:
            metadata["source_mode"] = "browserbase_search_fallback"
        return ResearchArtifact(
            dataset_id=dataset.id,
            language_code=dataset.language_code,
            type=research_type,
            summary=summary,
            guidelines=guidelines,
            sources=sources,
            metadata=metadata,
            warnings=warnings,
        )

    def evaluate_research(
        self,
        dataset: Dataset,
        samples: list[str],
        artifact: ResearchArtifact,
        research_type: str,
    ) -> dict[str, Any]:
        print(
            "[research-debug] calling anthropic research evaluator "
            f"dataset_id={dataset.id} type={research_type} source_count={len(artifact.sources)}",
            flush=True,
        )
        return self.llm.evaluate(
            task_name=f"{research_type}_research_quality",
            rubric=(
                "Score whether the research notes are grounded in provided sources, useful for the selected task, "
                "specific to the language, and actionable for a human reviewer. Higher is better."
            ),
            input_payload={
                "language": dataset.language_name,
                "language_code": dataset.language_code,
                "research_type": research_type,
                "samples": samples[:8],
                "sources": [source.model_dump() for source in artifact.sources],
            },
            output_payload={
                "summary": artifact.summary,
                "guidelines": artifact.guidelines,
                "metadata": artifact.metadata,
            },
        )

    def _search_and_fetch(self, query: str) -> tuple[list[ResearchSource], list[ProviderWarning]]:
        headers = {"x-bb-api-key": self.api_key or "", "Content-Type": "application/json"}
        with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
            with self.tracer.span("browserbase.search", query=query, num_results=6):
                print(
                    "[research-debug] executing browserbase search tool "
                    f"url={self.base_url}/v1/search query={query!r}",
                    flush=True,
                )
                search_response = client.post(
                    f"{self.base_url}/v1/search",
                    headers=headers,
                    json={"query": query, "numResults": 6},
                )
                search_response.raise_for_status()
                print(
                    "[research-debug] browserbase search tool response "
                    f"status={search_response.status_code} bytes={len(search_response.content)}",
                    flush=True,
                )
            results = self._extract_search_results(search_response.json())
            print(
                "[research-debug] browserbase search results parsed "
                f"result_count={len(results)}",
                flush=True,
            )

            sources: list[ResearchSource] = []
            fetch_errors: list[str] = []
            for result in results[:4]:
                try:
                    with self.tracer.span("browserbase.fetch", url=result["url"]):
                        print(
                            "[research-debug] executing browserbase fetch tool "
                            f"url={result['url']}",
                            flush=True,
                        )
                        fetched = client.post(
                            f"{self.base_url}/v1/fetch",
                            headers=headers,
                            json={"url": result["url"], "format": "markdown", "allowRedirects": True},
                        )
                        fetched.raise_for_status()
                        print(
                            "[research-debug] browserbase fetch tool response "
                            f"url={result['url']} status={fetched.status_code} bytes={len(fetched.content)}",
                            flush=True,
                        )
                    payload = fetched.json()
                    content = str(payload.get("content") or "").strip()
                    if content:
                        sources.append(
                            ResearchSource(
                                title=result.get("title") or result["url"],
                                url=result["url"],
                                excerpt=self._compact(content, 1400),
                            )
                        )
                        print(
                            "[research-debug] browserbase source accepted "
                            f"url={result['url']} content_chars={len(content)}",
                            flush=True,
                        )
                    else:
                        print(
                            "[research-debug] browserbase source skipped empty content "
                            f"url={result['url']}",
                            flush=True,
                        )
                        fetch_errors.append(f"{result['url']}: empty content")
                except Exception as exc:
                    fetch_errors.append(f"{result.get('url')}: {type(exc).__name__}: {exc}")
                    print(
                        "[research-debug] browserbase fetch tool error "
                        f"url={result.get('url')} error={type(exc).__name__}: {exc}",
                        flush=True,
                    )
                    continue
        if sources:
            return sources, []

        fallback_sources = self._fallback_search_sources(results, query)
        if fallback_sources:
            first_error = fetch_errors[0] if fetch_errors else "no fetched page content"
            warning = ProviderWarning(
                provider=self.provider,
                stage="browserbase.fetch",
                message=(
                    "Browserbase fetch returned no usable page content; using Browserbase search results only. "
                    f"First fetch issue: {first_error}"
                ),
                fallback=True,
            )
            print(
                "[research-debug] browserbase fetch fallback activated "
                f"source_count={len(fallback_sources)} fetch_issue_count={len(fetch_errors)}",
                flush=True,
            )
            return fallback_sources, [warning]

        return [], []

    def _research_query(self, dataset: Dataset, research_type: str) -> str:
        if research_type == "translation":
            return (
                f"{dataset.language_name} language translation examples grammar orthography "
                "Wikipedia dictionary parallel corpus"
            )
        return (
            f"{dataset.language_name} language parts of speech grammar morphology "
            "Universal Dependencies Wikipedia examples"
        )

    def _research_prompt(
        self,
        dataset: Dataset,
        samples: list[str],
        sources: list[ResearchSource],
        research_type: str,
    ) -> str:
        source_payload = [source.model_dump() for source in sources]
        task = (
            "translation guidance, source/target language considerations, examples, and review cautions"
            if research_type == "translation"
            else "part-of-speech tagging guidance using Universal Dependencies UPOS tags"
        )
        return json.dumps(
            {
                "language": dataset.language_name,
                "language_code": dataset.language_code,
                "task": task,
                "uploaded_samples": samples[:12],
                "sources": source_payload,
                "required_json_shape": {
                    "summary": "short research notes for the reviewer",
                    "language_profile": "what type of language this is and important grammar facts",
                    "task_notes": "task-specific notes",
                    "guidelines": ["concise actionable guideline"],
                    "examples": ["short example relevant to the task"],
                    "evaluation": {
                        "score": 0.0,
                        "feedback": "judge whether the notes are grounded, useful, and task-specific",
                    },
                },
            },
            ensure_ascii=False,
        )

    def _guidelines(self, research_type: str) -> list[str]:
        if research_type == "translation":
            return [
                "Preserve meaning before literal word order.",
                "Use uploaded reviewer examples as stronger evidence than web examples.",
                "Keep named entities, numbers, and punctuation consistent unless the target language convention differs.",
                "Flag uncertainty in the rationale for human review.",
            ]
        return [
            "Use Universal Dependencies UPOS tags for every token.",
            "Use the cached language notes when a form is ambiguous.",
            "Tag punctuation as PUNCT and numerals as NUM.",
            "Use X only when no stronger UPOS category is justified.",
        ]

    def _extract_search_results(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        candidates = payload.get("results") or payload.get("data") or payload.get("organic") or []
        results: list[dict[str, str]] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("link")
            if url:
                excerpt = (
                    item.get("excerpt")
                    or item.get("snippet")
                    or item.get("description")
                    or item.get("content")
                    or item.get("text")
                    or ""
                )
                results.append({"url": str(url), "title": str(item.get("title") or url), "excerpt": str(excerpt)})
        return results

    def _fallback_search_sources(self, results: list[dict[str, str]], query: str) -> list[ResearchSource]:
        sources: list[ResearchSource] = []
        for result in results[:4]:
            url = result.get("url")
            if not url:
                continue
            title = result.get("title") or url
            excerpt = result.get("excerpt") or f"Browserbase search result for: {query}"
            sources.append(
                ResearchSource(
                    title=title,
                    url=url,
                    excerpt=self._compact(excerpt, 900),
                )
            )
        return sources

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _compact(self, text: str, limit: int) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        return normalized[:limit]


class ConfigurableLLMClient(AnthropicClient):
    def summarize_research(self, dataset: Dataset, samples: list[str], sources: list[ResearchSource], research_type: str = "pos") -> tuple[str, ProviderWarning | None]:
        prompt = BrowserbaseResearchProvider(settings=self.settings, llm=self)._research_prompt(
            dataset, samples, sources, research_type
        )
        completion = self.complete_json(
            task_name=f"{research_type}_research_summary",
            system="Return concise research JSON.",
            prompt=prompt,
        )
        return str(completion.data.get("summary") or ""), None
