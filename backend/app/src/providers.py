from __future__ import annotations

import json
import re
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
    UploadedAsset,
)


class BrowserbaseResearchProvider:
    def __init__(
        self,
        settings: Settings | None = None,
        api_key: str | None = None,
        llm: "ConfigurableLLMClient | None" = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.BROWSERBASE_API_KEY
        self.llm = llm or ConfigurableLLMClient(self.settings)
        self.base_url = self.settings.browserbase_base_url

    def create_research(self, dataset: Dataset, samples: list[str], research_type: str = "pos") -> ResearchArtifact:
        if not self.api_key:
            return self._fallback_research(
                dataset,
                samples,
                research_type,
                self._warning("browserbase", "search", "BROWSERBASE_API_KEY is not configured."),
            )

        query = self._research_query(dataset, research_type)
        headers = {"x-bb-api-key": self.api_key, "Content-Type": "application/json"}
        sources: list[ResearchSource] = []
        try:
            with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
                search_response = client.post(
                    f"{self.base_url}/v1/search", headers=headers, json={"query": query}
                )
                search_response.raise_for_status()
                results = self._extract_search_results(search_response.json())
                for result in results[:3]:
                    fetched = client.post(
                        f"{self.base_url}/v1/fetch",
                        headers=headers,
                        json={
                            "url": result["url"],
                            "format": "markdown",
                            "allowRedirects": True,
                        },
                    )
                    if fetched.status_code < 400:
                        content = fetched.json().get("content", "")
                        sources.append(
                            ResearchSource(
                                title=result.get("title") or result["url"],
                                url=result["url"],
                                excerpt=str(content)[:900],
                            )
                        )
        except Exception as exc:
            return self._fallback_research(
                dataset,
                samples,
                research_type,
                self._warning("browserbase", "search", f"Browserbase research failed: {exc}"),
            )

        if not sources:
            return self._fallback_research(
                dataset,
                samples,
                research_type,
                self._warning("browserbase", "fetch", "Browserbase returned no usable sources."),
            )

        summary, warning = self.llm.summarize_research(dataset, samples, sources, research_type)
        return ResearchArtifact(
            dataset_id=dataset.id,
            language_code=dataset.language_code,
            type=research_type,
            summary=summary,
            guidelines=self._guidelines(research_type),
            sources=sources,
            warnings=[warning] if warning else [],
        )

    def _research_query(self, dataset: Dataset, research_type: str) -> str:
        if research_type == "translation":
            return (
                f"{dataset.language_name} language Spanish translation parallel corpus "
                "orthography grammar morphology translation notes"
            )
        return (
            f"{dataset.language_name} language part of speech grammar annotation "
            "Universal Dependencies POS morphology"
        )

    def _guidelines(self, research_type: str) -> list[str]:
        if research_type == "translation":
            return [
                "Preserve the source sentence meaning before attempting literal word-by-word alignment.",
                "Use existing reviewer-approved translations as stronger evidence than generated suggestions.",
                "Keep named entities, numbers, and punctuation consistent unless the target language convention differs.",
                "Flag uncertain translations for human review instead of over-normalizing low-resource forms.",
            ]
        return [
            "Use Universal Dependencies UPOS tags for every token.",
            "Prefer language-specific grammar notes from the cached research when the surface form is ambiguous.",
            "Mark uncertain or borrowed words as X only when no stronger UPOS category is justified.",
            "Keep punctuation as PUNCT and numerals as NUM.",
        ]

    def _extract_search_results(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        candidates = (
            payload.get("results")
            or payload.get("data")
            or payload.get("organic")
            or []
        )
        results: list[dict[str, str]] = []
        for item in candidates:
            url = item.get("url") or item.get("link")
            if url:
                results.append({"url": url, "title": item.get("title", url)})
        return results

    def _fallback_research(
        self,
        dataset: Dataset,
        samples: list[str],
        research_type: str = "pos",
        warning: ProviderWarning | None = None,
    ) -> ResearchArtifact:
        sample_preview = (
            "; ".join(samples[:3]) if samples else "No samples uploaded yet."
        )
        if research_type == "translation":
            return ResearchArtifact(
                dataset_id=dataset.id,
                language_code=dataset.language_code,
                type=research_type,
                summary=(
                    f"{dataset.language_name} translation profile for this dataset. "
                    f"Use uploaded examples as local evidence for Spanish-to-{dataset.language_name} suggestions: "
                    f"{sample_preview}"
                ),
                guidelines=self._guidelines(research_type),
                sources=[
                    ResearchSource(
                        title="Dataset translation samples",
                        url="local://uploaded-samples",
                        excerpt="Fallback translation guidance is based on uploaded rows and reviewer corrections.",
                    )
                ],
                warnings=[warning] if warning else [],
            )
        return ResearchArtifact(
            dataset_id=dataset.id,
            language_code=dataset.language_code,
            type=research_type,
            summary=(
                f"{dataset.language_name} annotation profile for this dataset. "
                f"Use the uploaded examples as the strongest local evidence: {sample_preview}"
            ),
            guidelines=self._guidelines(research_type),
            sources=[
                ResearchSource(
                    title="Universal Dependencies UPOS",
                    url="https://universaldependencies.org/u/pos/",
                    excerpt="Universal POS tags provide the default cross-lingual tag schema for this MVP.",
                )
            ],
            warnings=[warning] if warning else [],
        )

    def _warning(self, provider: str, stage: str, message: str) -> ProviderWarning:
        return ProviderWarning(provider=provider, stage=stage, message=message, fallback=True)


class ConfigurableLLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.llm_base_url
        self.api_key = self.settings.llm_api_key
        self.model = self.settings.llm_model

    def summarize_research(
        self, dataset: Dataset, samples: list[str], sources: list[ResearchSource], research_type: str = "pos"
    ) -> tuple[str, ProviderWarning | None]:
        if not self.base_url or not self.api_key:
            return self._fallback_summary(dataset, sources, research_type), ProviderWarning(
                provider="llm",
                stage="summary",
                message="LLM_BASE_URL or LLM_API_KEY is not configured.",
                fallback=True,
            )

        prompt = {
            "language": dataset.language_name,
            "language_code": dataset.language_code,
            "samples": samples[:10],
            "sources": [source.model_dump() for source in sources],
            "task": self._task_prompt(research_type),
        }
        try:
            with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "Return concise annotation research notes.",
                            },
                            {"role": "user", "content": json.dumps(prompt)},
                        ],
                    },
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"], None
        except Exception as exc:
            return self._fallback_summary(dataset, sources, research_type), ProviderWarning(
                provider="llm",
                stage="summary",
                message=f"LLM summary failed: {exc}",
                fallback=True,
            )

    def _task_prompt(self, research_type: str) -> str:
        if research_type == "translation":
            return "Summarize translation guidance for low-resource Spanish-to-target-language dataset review."
        return "Summarize POS annotation guidance for low-resource language dataset review."

    def _fallback_summary(self, dataset: Dataset, sources: list[ResearchSource], research_type: str) -> str:
        if research_type == "translation":
            return (
                f"{dataset.language_name} translation notes synthesized from {len(sources)} source(s). "
                "Focus on meaning preservation, phrase alignment, orthography, and reviewer-approved corrections."
            )
        return (
            f"{dataset.language_name} research notes synthesized from {len(sources)} source(s). "
            "Focus on UPOS consistency, morphology cues, particles, auxiliaries, and ambiguous borrowed forms."
        )


class PosAnnotationProvider:
    _punct = re.compile(r"^\W+$", re.UNICODE)

    def suggest(
        self, text: str, research: ResearchArtifact | None = None
    ) -> list[TokenSuggestion]:
        tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        suggestions: list[TokenSuggestion] = []
        for index, token in enumerate(tokens):
            tag, confidence, rationale = self._tag_token(token, index)
            if research and research.guidelines:
                rationale = f"{rationale} Uses cached research profile {research.id}."
            suggestions.append(
                TokenSuggestion(
                    index=index,
                    token=token,
                    suggested_pos=tag,
                    confidence=confidence,
                    rationale=rationale,
                )
            )
        return suggestions

    def _tag_token(self, token: str, index: int) -> tuple[str, float, str]:
        lower = token.lower()
        if self._punct.match(token):
            return "PUNCT", 0.99, "Punctuation is tagged as PUNCT."
        if lower.isdigit():
            return "NUM", 0.98, "Numeric tokens are tagged as NUM."
        if lower in {"el", "la", "los", "las", "un", "una", "the", "a", "an"}:
            return "DET", 0.86, "Article/determiner form."
        if lower in {
            "de",
            "del",
            "en",
            "con",
            "para",
            "por",
            "to",
            "from",
            "of",
            "in",
            "on",
        }:
            return "ADP", 0.84, "Adposition-like function word."
        if lower in {"y", "o", "and", "or"}:
            return "CCONJ", 0.9, "Coordinating conjunction."
        if lower in {"que", "si", "cuando", "because", "that"}:
            return "SCONJ", 0.78, "Subordinating connector candidate."
        if lower in {"yo", "tu", "mi", "su", "he", "she", "they", "we", "i"}:
            return "PRON", 0.82, "Pronoun or possessive pronoun candidate."
        if lower.endswith(("ar", "er", "ir", "ing", "ed")) or lower in {
            "es",
            "son",
            "esta",
            "corre",
            "habla",
        }:
            return (
                "VERB",
                0.72,
                "Verb-like form from suffix or common copula/action cue.",
            )
        if token[:1].isupper() and index > 0:
            return "PROPN", 0.7, "Capitalized non-initial token."
        if lower.endswith(("o", "a", "os", "as", "able", "ible")):
            return "ADJ", 0.58, "Adjective-like ending; needs human review."
        return "NOUN", 0.55, "Default content-word guess for low-resource review."


class OCRProvider:
    def extract(self, asset: UploadedAsset) -> tuple[str, float, str]:
        decoded = self._try_decode(asset.data)
        if decoded.strip():
            return decoded.strip(), 0.88, "Decoded text from uploaded asset bytes."

        label = asset.filename or asset.source_type.value
        return (
            f"[OCR draft for {label}]",
            0.35,
            "No local OCR engine is configured; placeholder is ready for manual correction or a cloud OCR adapter.",
        )

    def _try_decode(self, data: bytes) -> str:
        for encoding in ("utf-8", "latin-1"):
            try:
                text = data.decode(encoding)
            except UnicodeDecodeError:
                continue
            if any(character.isalpha() for character in text):
                return text
        return ""


class TranslationProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.endpoint_url = self.settings.nahuatl_model_endpoint_url
        self.model = self.settings.nahuatl_model_name

    def translate(
        self, text: str, direction: str = "spanish_to_nahuatl"
    ) -> TranslationProviderResult:
        warning: ProviderWarning | None = None
        if self.endpoint_url:
            try:
                with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                    response = client.post(
                        self.endpoint_url, json={"text": text, "direction": direction}
                    )
                    response.raise_for_status()
                    payload = response.json()
                    return TranslationProviderResult(
                        output_text=str(payload.get("translation") or payload.get("output_text")),
                        provider="aws-neuron-endpoint",
                        model=self.model,
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
            used_fallback=True,
            warning=warning,
        )
