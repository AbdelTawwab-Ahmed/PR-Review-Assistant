"""Azure Application Insights and OpenTelemetry integration.

Configures Azure Monitor telemetry, direct background telemetry ingestion
for Requests, Events, Exceptions, and Traces, and integrates standard Python
logging with Azure Application Insights.
"""

import datetime
import json
import logging
import queue
import threading
import time
import urllib.request
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


def parse_connection_string(conn_str: str) -> tuple[str, str]:
    """Extract InstrumentationKey and IngestionEndpoint from connection string."""
    parts = {}
    for item in conn_str.split(";"):
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k.strip().lower()] = v.strip()

    ikey = parts.get("instrumentationkey", "")
    endpoint = parts.get("ingestionendpoint", "https://dc.services.visualstudio.com/")
    if not endpoint.endswith("/"):
        endpoint += "/"
    return ikey, endpoint + "v2/track"


def format_duration(ms: float) -> str:
    secs = int(ms // 1000)
    millis = int(ms % 1000)
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{millis:03d}"


class AppInsightsSender:
    """Non-blocking background sender for Application Insights telemetry."""

    def __init__(self, ikey: str, track_url: str, service_name: str) -> None:
        self._ikey = ikey
        self._track_url = track_url
        self._service_name = service_name
        self._queue: queue.Queue = queue.Queue(maxsize=1000)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="app-insights-sender",
        )
        self._thread.start()

    def enqueue(self, item: dict[str, Any]) -> None:
        if self._stop_event.is_set():
            return
        item["iKey"] = self._ikey
        item["time"] = datetime.datetime.now(datetime.UTC).isoformat()
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            pass

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            batch = []
            try:
                # Wait for at least one item
                first = self._queue.get(timeout=1.0)
                batch.append(first)
                # Drain up to 20 items for bulk efficiency
                while len(batch) < 20:
                    try:
                        batch.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                continue

            if batch:
                self._send_batch(batch)
                for _ in batch:
                    self._queue.task_done()

    def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        try:
            data = json.dumps(batch).encode("utf-8")
            req = urllib.request.Request(  # noqa: S310
                self._track_url,
                headers={"Content-Type": "application/json"},
                data=data,
            )
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 # nosec B310
                if resp.status != 200:
                    logger.debug("App Insights non-200: %s", resp.status)
        except Exception as exc:
            logger.debug("Failed sending App Insights batch: %s", exc)

    def flush(self) -> None:
        self._stop_event.set()
        # Drain remaining items
        batch = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch:
            self._send_batch(batch)


class AppInsightsLoggingHandler(logging.Handler):
    """Bridges standard Python logging into Application Insights Message traces."""

    def __init__(self, sender: AppInsightsSender) -> None:
        super().__init__(level=logging.INFO)
        self._sender = sender

    def emit(self, record: logging.LogRecord) -> None:
        # Ignore noisy internal loggers to prevent recursive feedback
        if record.name.startswith(("azure", "urllib3", "httpx", "httpcore", "uvicorn.access")):
            return
        msg = self.format(record)
        severity = "Information"
        if record.levelno >= logging.ERROR:
            severity = "Error"
        elif record.levelno >= logging.WARNING:
            severity = "Warning"

        self._sender.enqueue(
            {
                "data": {
                    "baseType": "MessageData",
                    "baseData": {
                        "ver": 2,
                        "message": msg[:2000],
                        "severityLevel": severity,
                        "properties": {
                            "logger": record.name,
                            "function": record.funcName,
                            "line": str(record.lineno),
                        },
                    },
                },
                "ver": 1,
                "name": "Microsoft.ApplicationInsights.Message",
            }
        )


class TelemetryManager:
    """Manages OpenTelemetry tracing and direct Azure Application Insights telemetry."""

    def __init__(self, settings: Settings) -> None:
        self._service_name = settings.telemetry_service_name
        conn_str = settings.applicationinsights_connection_string.get_secret_value()
        self._enabled = settings.telemetry_enabled and bool(conn_str)
        self._tracer_provider: TracerProvider | None = None
        self._sender: AppInsightsSender | None = None
        self._log_handler: AppInsightsLoggingHandler | None = None

        if self._enabled:
            try:
                ikey, track_url = parse_connection_string(conn_str)
                self._sender = AppInsightsSender(ikey, track_url, self._service_name)

                # Attach log handler to forward application logs
                self._log_handler = AppInsightsLoggingHandler(self._sender)
                logging.getLogger().addHandler(self._log_handler)

                # Configure OpenTelemetry exporter if available
                from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

                exporter = AzureMonitorTraceExporter.from_connection_string(conn_str)
                resource = Resource.create(
                    {
                        "service.name": self._service_name,
                        "service.version": "0.1.0",
                    }
                )
                provider = TracerProvider(resource=resource)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                trace.set_tracer_provider(provider)
                self._tracer_provider = provider
                self._tracer = provider.get_tracer(self._service_name)
                logger.info(
                    "Azure Application Insights telemetry active for %s", self._service_name
                )
            except Exception as exc:
                logger.warning("Azure App Insights exporter setup note: %s", exc)
                self._enabled = False
                self._tracer = trace.get_tracer(self._service_name)
        else:
            self._tracer = trace.get_tracer(self._service_name)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def tracer(self) -> trace.Tracer:
        return self._tracer

    def track_request(
        self,
        name: str,
        url: str,
        duration_ms: float,
        status_code: int,
        success: bool,
        error: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Record HTTP Request in Application Insights."""
        if not self._enabled or not self._sender:
            return
        props = properties or {}
        props["service"] = self._service_name
        if error:
            props["error"] = error[:500]

        self._sender.enqueue(
            {
                "data": {
                    "baseType": "RequestData",
                    "baseData": {
                        "ver": 2,
                        "id": f"req-{int(time.time() * 1000)}",
                        "name": name,
                        "duration": format_duration(duration_ms),
                        "responseCode": str(status_code),
                        "success": success,
                        "url": url,
                        "properties": props,
                    },
                },
                "ver": 1,
                "name": "Microsoft.ApplicationInsights.Request",
            }
        )

    def track_event(self, name: str, properties: dict[str, Any] | None = None) -> None:
        """Record custom business event in Application Insights."""
        if not self._enabled or not self._sender:
            return
        props = properties or {}
        props["service"] = self._service_name
        self._sender.enqueue(
            {
                "data": {
                    "baseType": "EventData",
                    "baseData": {
                        "ver": 2,
                        "name": name,
                        "properties": props,
                    },
                },
                "ver": 1,
                "name": "Microsoft.ApplicationInsights.Event",
            }
        )

    def track_exception(self, exc: Exception, properties: dict[str, Any] | None = None) -> None:
        """Record exception details in Application Insights."""
        if not self._enabled or not self._sender:
            return
        props = properties or {}
        props["service"] = self._service_name
        props["exception.type"] = type(exc).__name__
        props["exception.message"] = str(exc)

        self._sender.enqueue(
            {
                "data": {
                    "baseType": "ExceptionData",
                    "baseData": {
                        "ver": 2,
                        "exceptions": [
                            {
                                "typeName": type(exc).__name__,
                                "message": str(exc),
                                "hasFullStack": False,
                            }
                        ],
                        "properties": props,
                    },
                },
                "ver": 1,
                "name": "Microsoft.ApplicationInsights.Exception",
            }
        )

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
        self.track_event(
            "LLMTokenUsage",
            {
                "purpose": purpose,
                "model": model,
                "input_tokens": str(input_tokens),
                "output_tokens": str(output_tokens),
                "total_tokens": str(input_tokens + output_tokens),
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
        self.track_event(
            "ReviewRunMetric",
            {
                "status": status,
                "duration_seconds": f"{duration_seconds:.2f}",
                "findings_count": str(findings_count),
            },
        )

    async def aclose(self) -> None:
        """Flush telemetry and shut down providers cleanly."""
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
        if self._sender is not None:
            self._sender.flush()
        if self._tracer_provider is not None:
            self._tracer_provider.shutdown()
            logger.debug("Telemetry trace provider shut down successfully")


def build_telemetry(settings: Settings) -> TelemetryManager:
    return TelemetryManager(settings)
