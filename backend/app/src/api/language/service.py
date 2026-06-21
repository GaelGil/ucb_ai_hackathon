from __future__ import annotations

from app.src.models import TranslationProviderResult
from app.src.providers import TranslationProvider
from app.src.tracing import Tracer


class LanguageService:
    def __init__(self, translation_provider: TranslationProvider, tracer: Tracer) -> None:
        self.translation_provider = translation_provider
        self.tracer = tracer

    def translate(self, text: str, direction: str) -> TranslationProviderResult:
        with self.tracer.span("translation.run", direction=direction):
            result = self.translation_provider.translate(text, direction)
        if result.used_fallback:
            with self.tracer.span(
                "translation.fallback",
                direction=direction,
                provider=result.warning.provider if result.warning else result.provider,
                stage=result.warning.stage if result.warning else "translation",
            ):
                pass
        return result
