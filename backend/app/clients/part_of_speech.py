from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings, get_settings
from app.clients.anthropic import AnthropicClient
from app.clients.tracing import Tracer
from app.schemas import ResearchArtifact, TokenSuggestion, UPOS_TAGS


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
