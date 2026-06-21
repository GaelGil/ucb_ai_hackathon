from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.src.config import Settings, get_settings


class Tracer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.enabled = self.settings.phoenix_enabled
        self._tracer = None
        if self.enabled:
            self._configure()

    def _configure(self) -> None:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(resource=Resource.create({"service.name": self.settings.otel_service_name}))
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=self.settings.phoenix_otel_endpoint)))
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer("langbase")
        except Exception:
            self.enabled = False
            self._tracer = None

    @contextmanager
    def span(self, name: str, **attributes: object) -> Iterator[None]:
        if not self.enabled or self._tracer is None:
            yield
            return

        with self._tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, str(value))
            yield
