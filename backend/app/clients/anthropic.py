from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.clients.tracing import Tracer


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
