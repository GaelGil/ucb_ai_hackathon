from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.src.config import Settings, get_settings
from app.src.models import Dataset, ResearchArtifact, ResearchSource, TokenSuggestion, UploadedAsset


class BrowserbaseResearchProvider:
    def __init__(
        self,
        settings: Settings | None = None,
        api_key: str | None = None,
        llm: "ConfigurableLLMClient | None" = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.browserbase_api_key
        self.llm = llm or ConfigurableLLMClient(self.settings)
        self.base_url = self.settings.browserbase_base_url

    def create_research(self, dataset: Dataset, samples: list[str]) -> ResearchArtifact:
        if not self.api_key:
            return self._fallback_research(dataset, samples)

        query = (
            f"{dataset.language_name} language part of speech grammar annotation "
            "Universal Dependencies POS morphology"
        )
        headers = {"x-bb-api-key": self.api_key, "Content-Type": "application/json"}
        sources: list[ResearchSource] = []
        try:
            with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
                search_response = client.post(f"{self.base_url}/v1/search", headers=headers, json={"query": query})
                search_response.raise_for_status()
                results = self._extract_search_results(search_response.json())
                for result in results[:3]:
                    fetched = client.post(
                        f"{self.base_url}/v1/fetch",
                        headers=headers,
                        json={"url": result["url"], "format": "markdown", "allowRedirects": True},
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
        except Exception:
            return self._fallback_research(dataset, samples)

        if not sources:
            return self._fallback_research(dataset, samples)

        summary = self.llm.summarize_research(dataset, samples, sources)
        return ResearchArtifact(
            dataset_id=dataset.id,
            language_code=dataset.language_code,
            summary=summary,
            guidelines=[
                "Use Universal Dependencies UPOS tags for every token.",
                "Prefer language-specific grammar notes from the cached research when the surface form is ambiguous.",
                "Mark uncertain or borrowed words as X only when no stronger UPOS category is justified.",
                "Keep punctuation as PUNCT and numerals as NUM.",
            ],
            sources=sources,
        )

    def _extract_search_results(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        candidates = payload.get("results") or payload.get("data") or payload.get("organic") or []
        results: list[dict[str, str]] = []
        for item in candidates:
            url = item.get("url") or item.get("link")
            if url:
                results.append({"url": url, "title": item.get("title", url)})
        return results

    def _fallback_research(self, dataset: Dataset, samples: list[str]) -> ResearchArtifact:
        sample_preview = "; ".join(samples[:3]) if samples else "No samples uploaded yet."
        return ResearchArtifact(
            dataset_id=dataset.id,
            language_code=dataset.language_code,
            summary=(
                f"{dataset.language_name} annotation profile for this dataset. "
                f"Use the uploaded examples as the strongest local evidence: {sample_preview}"
            ),
            guidelines=[
                "Annotate each token with one Universal Dependencies UPOS tag.",
                "Use sentence context before relying on isolated word shape.",
                "Use PROPN for names, NUM for numeric tokens, PUNCT for punctuation, and X for unclear residual tokens.",
                "Preserve reviewer edits as stronger evidence than generated suggestions.",
            ],
            sources=[
                ResearchSource(
                    title="Universal Dependencies UPOS",
                    url="https://universaldependencies.org/u/pos/",
                    excerpt="Universal POS tags provide the default cross-lingual tag schema for this MVP.",
                )
            ],
        )


class ConfigurableLLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.llm_base_url
        self.api_key = self.settings.llm_api_key
        self.model = self.settings.llm_model

    def summarize_research(self, dataset: Dataset, samples: list[str], sources: list[ResearchSource]) -> str:
        if not self.base_url or not self.api_key:
            return (
                f"{dataset.language_name} research notes synthesized from {len(sources)} source(s). "
                "Focus on UPOS consistency, morphology cues, particles, auxiliaries, and ambiguous borrowed forms."
            )

        prompt = {
            "language": dataset.language_name,
            "language_code": dataset.language_code,
            "samples": samples[:10],
            "sources": [source.model_dump() for source in sources],
            "task": "Summarize POS annotation guidance for low-resource language dataset review.",
        }
        try:
            with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "Return concise annotation research notes."},
                            {"role": "user", "content": json.dumps(prompt)},
                        ],
                    },
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
        except Exception:
            return (
                f"{dataset.language_name} research notes synthesized from {len(sources)} source(s). "
                "Focus on UPOS consistency, morphology cues, particles, auxiliaries, and ambiguous borrowed forms."
            )


class PosAnnotationProvider:
    _punct = re.compile(r"^\W+$", re.UNICODE)

    def suggest(self, text: str, research: ResearchArtifact | None = None) -> list[TokenSuggestion]:
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
        if lower in {"de", "del", "en", "con", "para", "por", "to", "from", "of", "in", "on"}:
            return "ADP", 0.84, "Adposition-like function word."
        if lower in {"y", "o", "and", "or"}:
            return "CCONJ", 0.9, "Coordinating conjunction."
        if lower in {"que", "si", "cuando", "because", "that"}:
            return "SCONJ", 0.78, "Subordinating connector candidate."
        if lower in {"yo", "tu", "mi", "su", "he", "she", "they", "we", "i"}:
            return "PRON", 0.82, "Pronoun or possessive pronoun candidate."
        if lower.endswith(("ar", "er", "ir", "ing", "ed")) or lower in {"es", "son", "esta", "corre", "habla"}:
            return "VERB", 0.72, "Verb-like form from suffix or common copula/action cue."
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

    def translate(self, text: str, direction: str = "spanish_to_nahuatl") -> tuple[str, str, str]:
        if self.endpoint_url:
            try:
                with httpx.Client(timeout=self.settings.llm_timeout_seconds) as client:
                    response = client.post(self.endpoint_url, json={"text": text, "direction": direction})
                    response.raise_for_status()
                    payload = response.json()
                    return str(payload.get("translation") or payload.get("output_text")), "aws-neuron-endpoint", self.model
            except Exception:
                pass

        demo_phrases = {
            "muchas flores son blancas": "miak xochitl istak",
            "el agua corre rapido": "atl motlaloa iciuhca",
            "mi familia habla nahuatl": "nochanehua tlahtoa nahuatlahtolli",
        }
        return demo_phrases.get(text.lower(), f"[Nahuatl demo translation] {text}"), "local-demo", self.model
