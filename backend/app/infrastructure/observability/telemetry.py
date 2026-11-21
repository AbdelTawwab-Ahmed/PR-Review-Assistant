"""Azure Application Insights and OpenTelemetry integration.

Configures Azure Monitor trace exporter (direct export without an external OTLP daemon)
when a valid connection string is provided, and gracefully defaults to a no-op tracer
for local development or testing when telemetry is disabled.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, StatusCode

from app.core.config import Settings

logger = logging.getLogger(__name__)


class TelemetryManager:
    """Manages OpenTelemetry tracing and metrics with Azure Application Insights."""

    def __init__(self, settings: Settings) -> None:
        self._service_name = settings.telemetry_service_name
        conn_str = settings.applicationinsights_connection_string.get_secret_value()
        self._enabled = settings.telemetry_enabled and bool(conn_str)
        self._tracer_provider: TracerProvider | None = None

        if self._enabled:
            try:
                from azure.monitor.opentelemetry.exporter import (
                    AzureMonitorTraceExporter,
                )

                exporter = AzureMonitorTraceExporter.from_connection_string(conn_str)
                resource = Resource.create(
                    {
                        "service.name": self._service_name,
                        "service.version": "0.1.0",
                    }
                )
                provider = TracerProvider(resource=resource)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                self._tracer_provider = provider
                self._tracer = provider.get_tracer(self._service_name)
                logger.info(
                    "Azure Application Insights telemetry initialized for service %s",
                    self._service_name,
                )
            except Exception as exc:
                logger.warning(
                    "Could not initialize Azure App Insights exporter: %s; falling back to no-op",
                    exc,
                )
                self._enabled = False
                self._tracer = trace.get_tracer(self._service_name)
        else:
            self._tracer = trace.get_tracer(self._service_name)
            logger.debug("Telemetry disabled or connection string missing; running in no-op mode")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def tracer(self) -> trace.Tracer:
        return self._tracer

    @contextmanager
    def trace_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        """Context manager to create a trace span with automatic error recording."""
        attrs = attributes or {}
        with self._tracer.start_as_current_span(name, attributes=attrs) as span:
            try:
                yield span
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise

    def record_tokens(
        self,
        purpose: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "",
    ) -> None:
        """Record LLM token consumption in the active span as an event."""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.add_event(
                "llm_token_usage",
                {
                    "llm.purpose": purpose,
                    "llm.model": model,
                    "llm.input_tokens": input_tokens,
                    "llm.output_tokens": output_tokens,
                    "llm.total_tokens": input_tokens + output_tokens,
                },
            )

    def record_run_metric(
        self,
        status: str,
        duration_seconds: float,
        findings_count: int = 0,
    ) -> None:
        """Record review run completion metrics on the current span."""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute("review.status", status)
            current_span.set_attribute("review.duration_seconds", duration_seconds)
            current_span.set_attribute("review.findings_count", findings_count)

    async def aclose(self) -> None:
        """Flush and shut down the trace provider."""
        if self._tracer_provider is not None:
            self._tracer_provider.shutdown()
            logger.debug("Telemetry trace provider shut down successfully")


def build_telemetry(settings: Settings) -> TelemetryManager:
    return TelemetryManager(settings)
