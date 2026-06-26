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
    suggestion_max_tokens = 2400

    def __init__(self, settings: Settings | None = None, llm: AnthropicClient | None = None, tracer: Tracer | None = None) -> None:
        self.settings = settings or get_settings()
        self.tracer = tracer or Tracer(self.settings)
        self.llm = llm or AnthropicClient(self.settings, self.tracer)
        self.model_name = self.llm.model

    def suggest(
        self,
        text: str,
        research: ResearchArtifact | None = None,
        feedback_examples: dict[str, Any] | None = None,
    ) -> list[TokenSuggestion]:
        tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        if not tokens:
            return []
        request = {
            "text": text,
            "tokens": [{"index": index, "token": token} for index, token in enumerate(tokens)],
            "upos_tags": sorted(UPOS_TAGS),
            "research": self._pos_research_context(research),
            "instructions": [
                "Use the cached POS research as task context before assigning tags.",
                "Use approved, edited, imported, and human POS labels as reviewer-preferred positive examples.",
                "Treat denied POS suggestions as mistakes to avoid, not gold labels.",
                "Do not copy feedback examples unless the token and sentence context actually match.",
                "Apply language-specific syntax, morphology, word-order, and tokenization notes when available.",
                "Preserve token indexes exactly and assign one valid UPOS tag per input token.",
                "When uncertain, choose the best-supported UPOS tag and lower confidence instead of using X by default.",
                "Return compact JSON only: no markdown, no code fences, and no prose outside the JSON object.",
                "Keep token rationales short, ideally under 12 words each.",
            ],
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
            },
        }
        feedback_context = self._pos_feedback_context(feedback_examples)
        if feedback_context:
            request["reviewer_feedback"] = feedback_context
        prompt = json.dumps(request, ensure_ascii=False)
        print(
            "[research-debug] pos suggestion prompt built "
            f"text_chars={len(text)} token_count={len(tokens)} prompt_chars={len(prompt)}",
            flush=True,
        )
        completion = self._complete_pos_json(prompt)
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
        print(
            "[research-debug] pos suggestion parsed "
            f"text_chars={len(text)} token_count={len(suggestions)}",
            flush=True,
        )
        return suggestions

    def _complete_pos_json(self, prompt: str):
        system = (
            "You tag tokens with Universal Dependencies UPOS labels. "
            "Use the provided compact language research for syntax, morphology, word order, and POS inventory. "
            "Return exactly one compact valid JSON object and preserve token indexes."
        )
        try:
            return self.llm.complete_json(
                task_name="pos_suggestions",
                system=system,
                prompt=prompt,
                max_tokens=self.suggestion_max_tokens,
            )
        except RuntimeError as exc:
            if "invalid JSON" not in str(exc):
                raise
            print(
                "[research-debug] anthropic pos suggestion invalid json; retrying with compact instructions "
                f"error={exc}",
                flush=True,
            )
            retry_prompt = json.dumps(
                {
                    "previous_error": str(exc),
                    "instruction": (
                        "The previous answer was invalid JSON. Return one compact valid JSON object only. "
                        "No markdown, no code fences, no extra prose. Preserve token indexes exactly. "
                        "Return only the required tokens array and optional sentence rationale."
                    ),
                    "original_request": json.loads(prompt),
                },
                ensure_ascii=False,
            )
            return self.llm.complete_json(
                task_name="pos_suggestions_retry",
                system=system,
                prompt=retry_prompt,
                max_tokens=self.suggestion_max_tokens,
            )

    def _pos_research_context(self, research: ResearchArtifact | None) -> dict[str, Any] | None:
        if research is None:
            return None
        metadata = research.metadata or {}
        context = {
            "summary": self._compact(research.summary, 900),
            "guidelines": [self._compact(item, 220) for item in research.guidelines[:5]],
            "language_profile": metadata.get("language_profile"),
            "task_notes": self._compact(str(metadata.get("task_notes") or ""), 700),
            "upos_inventory": metadata.get("upos_inventory"),
            "examples": metadata.get("examples")[:2] if isinstance(metadata.get("examples"), list) else [],
        }
        return {key: value for key, value in context.items() if value not in (None, "", [])}

    def _pos_feedback_context(self, feedback_examples: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(feedback_examples, dict):
            return {}
        positive_examples = feedback_examples.get("positive_examples")
        negative_examples = feedback_examples.get("negative_examples")
        context: dict[str, Any] = {}
        if isinstance(positive_examples, list) and positive_examples:
            context["positive_examples"] = positive_examples[:5]
        if isinstance(negative_examples, list) and negative_examples:
            context["negative_examples"] = negative_examples[:3]
        return context

    def _compact(self, text: str, limit: int) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        return normalized[:limit]

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
