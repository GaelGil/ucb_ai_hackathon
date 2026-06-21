from __future__ import annotations

import base64
import json
import mimetypes
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.src.config import Settings, get_settings
from app.src.models import (
    Dataset,
    ProviderWarning,
    ResearchArtifact,
    ResearchSource,
    TokenSuggestion,
    TranslationProviderResult,
    UPOS_TAGS,
    UploadedAsset,
)
from app.src.tracing import Tracer


@dataclass(frozen=True)
class JsonCompletion:
    data: dict[str, Any]
    usage: dict[str, Any]


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, settings: Settings | None = None, tracer: Tracer | None = None) -> None:
        self.settings = settings or get_settings()
        self.tracer = tracer or Tracer(self.settings)
        self.api_key = self.settings.anthropic_api_key
        self.model = self.settings.anthropic_model
        self.base_url = self.settings.anthropic_base_url.rstrip("/")
        self._client = None

    def complete_json(
        self,
        *,
        task_name: str,
        system: str,
        prompt: str,
        max_tokens: int | None = None,
    ) -> JsonCompletion:
        print(
            "[research-debug] anthropic request starting "
            f"task={task_name} model={self.model} prompt_chars={len(prompt)}",
            flush=True,
        )
        payload = self._message_payload(
            system=system,
            content=[{"type": "text", "text": prompt}],
            max_tokens=max_tokens,
        )
        with self.tracer.span("anthropic.request", task=task_name, model=self.model):
            response = self._post_message(payload, task_name)
        text = self._response_text(response)
        usage = self._usage(response)
        print(
            "[research-debug] anthropic response received "
            f"task={task_name} response_chars={len(text)} usage={usage}",
            flush=True,
        )
        parsed = self._parse_json(text, task_name)
        print(
            "[research-debug] anthropic json parsed "
            f"task={task_name} keys={sorted(parsed.keys())}",
            flush=True,
        )
        return JsonCompletion(data=parsed, usage=usage)

    def complete_vision_json(
        self,
        *,
        task_name: str,
        system: str,
        prompt: str,
        image_bytes: bytes,
        media_type: str,
        max_tokens: int | None = None,
    ) -> JsonCompletion:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload = self._message_payload(
            system=system,
            content=[
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": encoded,
                    },
                },
                {"type": "text", "text": prompt},
            ],
            max_tokens=max_tokens,
        )
        with self.tracer.span("anthropic.request", task=task_name, model=self.model, media_type=media_type):
            response = self._post_message(payload, task_name)
        return JsonCompletion(data=self._parse_json(self._response_text(response), task_name), usage=self._usage(response))

    def evaluate(
        self,
        *,
        task_name: str,
        rubric: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
    ) -> dict[str, Any]:
        completion = self.complete_json(
            task_name=f"evaluator_{task_name}",
            system="You are an LLM-as-judge evaluator. Return only valid JSON.",
            prompt=json.dumps(
                {
                    "evaluator_name": task_name,
                    "rubric": rubric,
                    "input": input_payload,
                    "output": output_payload,
                    "required_json_shape": {
                        "score": 0.0,
                        "label": "pass|warn|fail",
                        "feedback": "brief actionable feedback",
                    },
                },
                ensure_ascii=False,
            ),
            max_tokens=500,
        )
        data = completion.data
        return {
            "name": task_name,
            "kind": "llm",
            "score": self._score(data.get("score")),
            "label": str(data.get("label") or "warn"),
            "feedback": str(data.get("feedback") or data.get("explanation") or ""),
            "usage": completion.usage,
        }

    def _message_payload(self, *, system: str, content: list[dict[str, Any]], max_tokens: int | None) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
        return {
            "model": self.model,
            "max_tokens": max_tokens or self.settings.anthropic_max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": content}],
        }

    def _post_message(self, payload: dict[str, Any], task_name: str) -> dict[str, Any]:
        try:
            return self._anthropic_client().messages.create(**payload)
        except Exception as exc:
            print(
                "[research-debug] anthropic request error "
                f"task={task_name} error={type(exc).__name__}: {exc}",
                flush=True,
            )
            raise RuntimeError(f"Anthropic {task_name} failed: {exc}") from exc

    def _anthropic_client(self):
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
            from anthropic import Anthropic

            kwargs: dict[str, Any] = {
                "api_key": self.api_key,
                "timeout": self.settings.llm_timeout_seconds,
            }
            if self.base_url and self.base_url != "https://api.anthropic.com":
                kwargs["base_url"] = self.base_url
            self._client = Anthropic(**kwargs)
        return self._client

    def _response_text(self, response: object) -> str:
        parts = []
        for item in getattr(response, "content", []) or []:
            item_type = getattr(item, "type", None)
            text = getattr(item, "text", None)
            if item_type == "text" and text:
                parts.append(str(text))
        text = "\n".join(parts).strip()
        if not text:
            raise RuntimeError("Anthropic returned an empty text response.")
        return text

    def _usage(self, response: object) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            return usage.model_dump()
        if isinstance(usage, dict):
            return usage
        return {
            key: getattr(usage, key)
            for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
            if getattr(usage, key, None) is not None
        }

    def _parse_json(self, text: str, task_name: str) -> dict[str, Any]:
        cleaned = text.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
        if fenced:
            cleaned = fenced.group(1)
        else:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start : end + 1]
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Anthropic {task_name} returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError(f"Anthropic {task_name} returned JSON that was not an object.")
        return parsed

    def _score(self, value: object) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))


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
        sources = self._search_and_fetch(query)
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
        return ResearchArtifact(
            dataset_id=dataset.id,
            language_code=dataset.language_code,
            type=research_type,
            summary=summary,
            guidelines=guidelines,
            sources=sources,
            metadata=metadata,
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

    def _search_and_fetch(self, query: str) -> list[ResearchSource]:
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
                except Exception as exc:
                    print(
                        "[research-debug] browserbase fetch tool error "
                        f"url={result.get('url')} error={type(exc).__name__}: {exc}",
                        flush=True,
                    )
                    continue
        return sources

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
                results.append({"url": str(url), "title": str(item.get("title") or url)})
        return results

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _compact(self, text: str, limit: int) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        return normalized[:limit]


class ConfigurableLLMClient(AnthropicClient):
    def summarize_research(
        self, dataset: Dataset, samples: list[str], sources: list[ResearchSource], research_type: str = "pos"
    ) -> tuple[str, ProviderWarning | None]:
        prompt = BrowserbaseResearchProvider(settings=self.settings, llm=self)._research_prompt(
            dataset, samples, sources, research_type
        )
        completion = self.complete_json(
            task_name=f"{research_type}_research_summary",
            system="Return concise research JSON.",
            prompt=prompt,
        )
        return str(completion.data.get("summary") or ""), None


class PosAnnotationProvider:
    provider = "anthropic"

    def __init__(self, settings: Settings | None = None, llm: AnthropicClient | None = None, tracer: Tracer | None = None) -> None:
        self.settings = settings or get_settings()
        self.tracer = tracer or Tracer(self.settings)
        self.llm = llm or AnthropicClient(self.settings, self.tracer)
        self.model_name = self.llm.model

    def suggest(self, text: str, research: ResearchArtifact | None = None) -> list[TokenSuggestion]:
        tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        if not tokens:
            return []
        prompt = json.dumps(
            {
                "text": text,
                "tokens": [{"index": index, "token": token} for index, token in enumerate(tokens)],
                "upos_tags": sorted(UPOS_TAGS),
                "research": research.model_dump(mode="json") if research else None,
                "required_json_shape": {
                    "tokens": [
                        {
                            "index": 0,
                            "token": "token text",
                            "suggested_pos": "NOUN",
                            "confidence": 0.8,
                            "rationale": "short reason",
                        }
                    ],
                    "rationale": "sentence-level rationale",
                    "evaluation": {
                        "score": 0.0,
                        "feedback": "judge whether every token has exactly one valid UPOS tag",
                    },
                },
            },
            ensure_ascii=False,
        )
        completion = self.llm.complete_json(
            task_name="pos_suggestions",
            system=(
                "You tag tokens with Universal Dependencies UPOS labels. "
                "Return exactly one JSON object and preserve token indexes."
            ),
            prompt=prompt,
        )
        items = completion.data.get("tokens")
        if not isinstance(items, list):
            raise RuntimeError("Anthropic POS response did not include a tokens list.")
        if len(items) != len(tokens):
            raise RuntimeError("Anthropic POS response token count did not match the input.")

        suggestions: list[TokenSuggestion] = []
        for index, token in enumerate(tokens):
            item = items[index]
            if not isinstance(item, dict):
                raise RuntimeError("Anthropic POS response included an invalid token item.")
            tag = str(item.get("suggested_pos") or "").upper()
            if tag not in UPOS_TAGS:
                raise RuntimeError(f"Anthropic POS response included invalid UPOS tag: {tag or 'empty'}.")
            suggestions.append(
                TokenSuggestion(
                    index=index,
                    token=token,
                    suggested_pos=tag,
                    confidence=self._confidence(item.get("confidence"), default=0.65),
                    rationale=str(item.get("rationale") or completion.data.get("rationale") or "Claude UPOS suggestion."),
                )
            )
        return suggestions

    def evaluate(
        self,
        text: str,
        tokens: list[TokenSuggestion],
        research: ResearchArtifact | None = None,
    ) -> dict[str, Any]:
        return self.llm.evaluate(
            task_name="pos_quality",
            rubric=(
                "Score whether every token has exactly one valid UPOS tag, the rationale uses language research when "
                "helpful, and uncertainty is reflected in confidence. Higher is better."
            ),
            input_payload={
                "text": text,
                "research_summary": research.summary if research else "",
                "guidelines": research.guidelines if research else [],
            },
            output_payload={"tokens": [token.model_dump() for token in tokens]},
        )

    def _confidence(self, value: object, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        return max(0.0, min(1.0, number))


class OCRProvider:
    provider = "anthropic"

    def __init__(self, settings: Settings | None = None, llm: AnthropicClient | None = None, tracer: Tracer | None = None) -> None:
        self.settings = settings or get_settings()
        self.tracer = tracer or Tracer(self.settings)
        self.llm = llm or AnthropicClient(self.settings, self.tracer)
        self.model_name = self.llm.model

    def extract(self, asset: UploadedAsset) -> tuple[str, float, str]:
        if asset.source_type.value != "image":
            raise RuntimeError("OCR currently supports image uploads only.")
        if not asset.data:
            raise RuntimeError("Uploaded image bytes were empty.")
        media_type = self._media_type(asset)
        prompt = json.dumps(
            {
                "filename": asset.filename,
                "task": "Extract every visible text string from the image. Preserve line breaks when useful.",
                "required_json_shape": {
                    "text": "all extracted text",
                    "confidence": 0.8,
                    "rationale": "brief quality or uncertainty note",
                    "evaluation": {
                        "score": 0.0,
                        "feedback": "judge whether the extracted text is complete and faithful to the image",
                    },
                },
            },
            ensure_ascii=False,
        )
        completion = self.llm.complete_vision_json(
            task_name="ocr_extract",
            system="You are an OCR extraction agent. Return only valid JSON.",
            prompt=prompt,
            image_bytes=asset.data,
            media_type=media_type,
        )
        text = str(completion.data.get("text") or "").strip()
        if not text:
            raise RuntimeError("Anthropic OCR response did not include extracted text.")
        return text, self._confidence(completion.data.get("confidence"), default=0.7), str(
            completion.data.get("rationale") or "Claude vision OCR extraction."
        )

    def evaluate(self, asset: UploadedAsset, text: str, confidence: float, rationale: str) -> dict[str, Any]:
        return self.llm.evaluate(
            task_name="ocr_quality",
            rubric=(
                "Score whether the extracted text is complete, faithful to the image, reviewable by a human, "
                "and has clear uncertainty notes. Higher is better."
            ),
            input_payload={"filename": asset.filename, "content_type": asset.content_type},
            output_payload={"text": text, "confidence": confidence, "rationale": rationale},
        )

    def _media_type(self, asset: UploadedAsset) -> str:
        media_type = asset.content_type or mimetypes.guess_type(asset.filename)[0] or "image/png"
        if media_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
            raise RuntimeError(f"Unsupported image media type for Claude vision: {media_type}.")
        return media_type

    def _confidence(self, value: object, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        return max(0.0, min(1.0, number))


class TranslationProvider:
    provider = "anthropic"

    def __init__(self, settings: Settings | None = None, llm: AnthropicClient | None = None, tracer: Tracer | None = None) -> None:
        self.settings = settings or get_settings()
        self.tracer = tracer or Tracer(self.settings)
        self.llm = llm or AnthropicClient(self.settings, self.tracer)
        self.endpoint_url = self.settings.nahuatl_model_endpoint_url
        self.model = self.settings.nahuatl_model_name
        self.model_name = self.llm.model

    def suggest(
        self,
        *,
        text: str,
        direction: str,
        research: ResearchArtifact | None,
        row_metadata: dict[str, Any] | None = None,
    ) -> TranslationProviderResult:
        prompt = json.dumps(
            {
                "source_text": text,
                "direction": direction,
                "row_metadata": row_metadata or {},
                "research": research.model_dump(mode="json") if research else None,
                "required_json_shape": {
                    "translation": "translated text",
                    "confidence": 0.75,
                    "rationale": "short reason and uncertainty note",
                    "evaluation": {
                        "score": 0.0,
                        "feedback": "judge whether the translation preserves meaning and uses the research notes",
                    },
                },
            },
            ensure_ascii=False,
        )
        completion = self.llm.complete_json(
            task_name="translation_suggestion",
            system="You are a careful low-resource language translation assistant. Return only valid JSON.",
            prompt=prompt,
        )
        output = str(
            completion.data.get("translation") or completion.data.get("text") or completion.data.get("output_text") or ""
        ).strip()
        if not output:
            raise RuntimeError("Anthropic translation response did not include translated text.")
        return TranslationProviderResult(
            output_text=output,
            provider=self.provider,
            model=self.llm.model,
            confidence=self._confidence(completion.data.get("confidence"), default=0.65),
            rationale=str(completion.data.get("rationale") or "Claude translation suggestion."),
            metadata={
                "usage": completion.usage,
            },
        )

    def evaluate(
        self,
        *,
        text: str,
        direction: str,
        result: TranslationProviderResult,
        research: ResearchArtifact | None,
        row_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.llm.evaluate(
            task_name="translation_quality",
            rubric=(
                "Score whether the translation preserves source meaning, uses the target-language research notes, "
                "keeps uncertainty visible, and is useful as a human-review suggestion. Higher is better."
            ),
            input_payload={
                "source_text": text,
                "direction": direction,
                "row_metadata": row_metadata or {},
                "research_summary": research.summary if research else "",
                "guidelines": research.guidelines if research else [],
            },
            output_payload={
                "translation": result.output_text,
                "confidence": result.confidence,
                "rationale": result.rationale,
            },
        )

    def translate(self, text: str, direction: str = "spanish_to_nahuatl") -> TranslationProviderResult:
        if self.settings.anthropic_api_key:
            return self.suggest(text=text, direction=direction, research=None, row_metadata={})

        warning: ProviderWarning | None = None
        if self.endpoint_url:
            try:
                with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                    response = client.post(self.endpoint_url, json={"text": text, "direction": direction})
                    response.raise_for_status()
                    payload = response.json()
                    return TranslationProviderResult(
                        output_text=str(payload.get("translation") or payload.get("output_text")),
                        provider="aws-neuron-endpoint",
                        model=self.model,
                        confidence=0.75,
                        rationale="External translation endpoint response.",
                    )
            except Exception as exc:
                warning = ProviderWarning(
                    provider="aws-neuron-endpoint",
                    stage="translation",
                    message=f"Translation endpoint failed: {exc}",
                    fallback=True,
                )
        else:
            warning = ProviderWarning(
                provider="aws-neuron-endpoint",
                stage="translation",
                message="NAHUATL_MODEL_ENDPOINT_URL is not configured.",
                fallback=True,
            )

        demo_phrases = {
            "muchas flores son blancas": "miak xochitl istak",
            "el agua corre rapido": "atl motlaloa iciuhca",
            "mi familia habla nahuatl": "nochanehua tlahtoa nahuatlahtolli",
        }
        return TranslationProviderResult(
            output_text=demo_phrases.get(text.lower(), f"[Nahuatl demo translation] {text}"),
            provider="local-demo",
            model=self.model,
            confidence=0.35,
            rationale="Local demo endpoint fallback.",
            used_fallback=True,
            warning=warning,
        )

    def _confidence(self, value: object, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        return max(0.0, min(1.0, number))
