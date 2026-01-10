"""Observability configuration for metrics and tracing.

This module sets up:
- OpenTelemetry tracing with OTLP export
- Prometheus metrics instrumentation
- Structured logging with trace correlation
"""

import logging
import os
from typing import Optional

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator

# Service identification
SERVICE_NAME = os.getenv("SERVICE_NAME", "beacon-library-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
ENV = os.getenv("ENV", "local")
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://alloy:4317")


def setup_tracing() -> Optional[TracerProvider]:
    """Initialize OpenTelemetry tracing with OTLP export.

    Returns:
        TracerProvider if tracing is enabled, None otherwise.
    """
    # Skip tracing setup if disabled
    if os.getenv("OTEL_TRACING_ENABLED", "true").lower() == "false":
        return None

    # Create resource with service metadata
    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": SERVICE_VERSION,
            "deployment.environment": ENV,
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=OTLP_ENDPOINT,
        insecure=True,  # Use insecure for internal network
    )

    # Add batch processor for efficient export
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    return provider


def setup_logging() -> None:
    """Configure structured logging with trace correlation.

    Sets up structlog to output JSON logs with trace_id and span_id
    for correlation with distributed traces.
    """
    # Instrument standard logging to include trace context
    LoggingInstrumentor().instrument(set_logging_format=True)

    def add_trace_context(
        logger: logging.Logger, method_name: str, event_dict: dict
    ) -> dict:
        """Add OpenTelemetry trace context to log entries."""
        span = trace.get_current_span()
        if span.is_recording():
            ctx = span.get_span_context()
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
        return event_dict

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_trace_context,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))


def setup_metrics(app) -> Instrumentator:
    """Configure Prometheus metrics instrumentation for FastAPI.

    Args:
        app: FastAPI application instance.

    Returns:
        Configured Instrumentator instance.
    """
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=False,  # Always enable metrics, don't depend on env var
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/health", "/metrics"],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    return instrumentator


def instrument_app(app) -> None:
    """Apply all observability instrumentation to FastAPI app.

    This is the main entry point for setting up observability.
    Call this after creating your FastAPI app.

    Args:
        app: FastAPI application instance.
    """
    # Setup tracing first
    setup_tracing()

    # Setup structured logging with trace correlation
    setup_logging()

    # Instrument FastAPI for automatic span creation
    FastAPIInstrumentor.instrument_app(app)

    # Setup and expose Prometheus metrics
    instrumentator = setup_metrics(app)
    instrumentator.instrument(app).expose(app, endpoint="/metrics")
