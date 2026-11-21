from unittest.mock import patch

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.infrastructure.observability.telemetry import (
    TelemetryManager,
    build_telemetry,
)


def test_telemetry_disabled_by_default_without_conn_str() -> None:
    settings = Settings(
        telemetry_enabled=True,
        applicationinsights_connection_string=SecretStr(""),
    )
    tm = build_telemetry(settings)
    assert not tm.is_enabled
    assert tm.tracer is not None


def test_telemetry_disabled_when_flag_false() -> None:
    settings = Settings(
        telemetry_enabled=False,
        applicationinsights_connection_string=SecretStr(
            "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
            "IngestionEndpoint=https://eastus.in.applicationinsights.azure.com/"
        ),
    )
    tm = build_telemetry(settings)
    assert not tm.is_enabled


def test_trace_span_executes_block() -> None:
    settings = Settings(telemetry_enabled=False)
    tm = build_telemetry(settings)

    executed = False
    with tm.trace_span("test_span", {"test.attr": "value"}) as span:
        executed = True
        assert span is not None

    assert executed


def test_trace_span_captures_exception() -> None:
    settings = Settings(telemetry_enabled=False)
    tm = build_telemetry(settings)

    with pytest.raises(ValueError, match="intentional error"):
        with tm.trace_span("error_span"):
            raise ValueError("intentional error")


def test_record_tokens_outside_and_inside_span() -> None:
    settings = Settings(telemetry_enabled=False)
    tm = build_telemetry(settings)

    # Calling outside active span should be a safe no-op
    tm.record_tokens("review", 100, 200, model="gpt-4o")

    # Calling inside active span should execute without error
    with tm.trace_span("token_span"):
        tm.record_tokens("review", 100, 200, model="gpt-4o")


def test_record_run_metric() -> None:
    settings = Settings(telemetry_enabled=False)
    tm = build_telemetry(settings)

    with tm.trace_span("metric_span"):
        tm.record_run_metric("ready_to_merge", 4.5, findings_count=3)


def test_telemetry_initializes_with_azure_connection_string() -> None:
    conn_str = (
        "InstrumentationKey=547dbf14-d6c6-489d-ae27-b1403b817c6a;"
        "IngestionEndpoint=https://eastus-8.in.applicationinsights.azure.com/;"
        "LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/;"
        "ApplicationId=79513bc6-d29d-49a7-8ba7-bb7c2c81b7ca"
    )
    settings = Settings(
        telemetry_enabled=True,
        applicationinsights_connection_string=SecretStr(conn_str),
    )
    tm = build_telemetry(settings)
    assert tm.is_enabled
    assert tm.tracer is not None


def test_telemetry_fallback_on_exporter_exception() -> None:
    settings = Settings(
        telemetry_enabled=True,
        applicationinsights_connection_string=SecretStr("InstrumentationKey=bad-key"),
    )
    with patch(
        "azure.monitor.opentelemetry.exporter.AzureMonitorTraceExporter.from_connection_string",
        side_effect=Exception("Exporter failure"),
    ):
        tm = build_telemetry(settings)
        assert not tm.is_enabled


async def test_aclose_clean_shutdown() -> None:
    settings = Settings(telemetry_enabled=False)
    tm = build_telemetry(settings)
    await tm.aclose()


def test_container_telemetry_wiring() -> None:
    from app.core.container import build_container

    settings = Settings(telemetry_enabled=False)
    container = build_container(settings)
    assert container.telemetry is not None
    assert isinstance(container.telemetry, TelemetryManager)
