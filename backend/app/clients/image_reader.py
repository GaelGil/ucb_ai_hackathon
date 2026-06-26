from __future__ import annotations

import json
import mimetypes
from typing import Any

from app.config import Settings, get_settings
from app.clients.anthropic import AnthropicClient
from app.clients.tracing import Tracer
from app.schemas import UploadedAsset


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
