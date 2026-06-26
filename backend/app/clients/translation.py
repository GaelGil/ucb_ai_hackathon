from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.clients.anthropic import AnthropicClient
from app.clients.tracing import Tracer
from app.schemas import ProviderWarning, ResearchArtifact, TranslationProviderResult


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
