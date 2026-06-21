from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.src.config import Settings, get_settings


class Tracer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.enabled = self.settings.arize_enabled or self.settings.phoenix_enabled
        self._tracer = None
        if self.enabled:
            self._configure()

    def _configure(self) -> None:
        if self.settings.arize_enabled:
            self._configure_arize()
            return
        self._configure_phoenix()

    def _configure_arize(self) -> None:
        try:
            from opentelemetry import trace
            from arize.otel import register
            from openinference.instrumentation.anthropic import AnthropicInstrumentor

            provider = register(
                space_id=self.settings.arize_space_id or "",
                api_key=self.settings.arize_api_key or "",
                project_name=self.settings.arize_project_name or "langbase-hackathon",
            )
            AnthropicInstrumentor().instrument(tracer_provider=provider)
            self._tracer = trace.get_tracer("langbase")
        except Exception:
            self.enabled = False
            self._tracer = None

    def _configure_phoenix(self) -> None:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(
                resource=Resource.create(
                    {
                        "service.name": self.settings.otel_service_name,
                        "openinference.project.name": self.settings.phoenix_project_name,
                    }
                )
            )
            headers = {}
            if self.settings.phoenix_api_key:
                headers = {
                    "api_key": self.settings.phoenix_api_key,
                    "Authorization": f"Bearer {self.settings.phoenix_api_key}",
                }
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=self.settings.phoenix_otel_endpoint, headers=headers or None))
            )
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
            try:
                yield
            except Exception as exc:
                try:
                    from opentelemetry.trace import Status, StatusCode

                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                finally:
                    raise

    def record_evaluation(self, name: str, evaluation: dict, **attributes: object) -> None:
        if not evaluation:
            return
        with self.span(
            f"evaluator.{name}",
            evaluator_name=name,
            evaluator_kind=evaluation.get("kind") or "llm",
            evaluator_score=evaluation.get("score"),
            evaluator_label=evaluation.get("label"),
            evaluator_feedback=evaluation.get("feedback") or evaluation.get("explanation"),
            **attributes,
        ):
            pass
