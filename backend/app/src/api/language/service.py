from __future__ import annotations

from app.src.providers import TranslationProvider
from app.src.tracing import Tracer


class LanguageService:
    def __init__(self, translation_provider: TranslationProvider, tracer: Tracer) -> None:
        self.translation_provider = translation_provider
        self.tracer = tracer

    def translate(self, text: str, direction: str) -> tuple[str, str, str]:
        with self.tracer.span("translation.run", direction=direction):
            return self.translation_provider.translate(text, direction)
