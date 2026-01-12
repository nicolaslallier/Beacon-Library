"""Observability configuration for MCP Vector Server.

Provides:
- Structured logging with structlog
- OpenTelemetry tracing (optional)
- Prometheus-compatible metrics
"""

import logging
import sys
from typing import Optional

import structlog
from structlog.types import Processor

from app.config import settings


def setup_logging():
    """Configure structured logging with structlog."""

    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Shared processors for all output
    # Note: We don't use add_logger_name with PrintLoggerFactory as PrintLogger
    # doesn't have a 'name' attribute
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure structlog
    if settings.env in ("local", "dev", "development", "test"):
        # Pretty printing for development
        structlog.configure(
            processors=shared_processors
            + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # JSON output for production
        structlog.configure(
            processors=shared_processors
            + [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def setup_tracing() -> Optional["TracerProvider"]:
    """Configure OpenTelemetry tracing if enabled."""
    if not settings.otlp_enabled or not settings.otlp_endpoint:
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Create resource with service info
        resource = Resource.create({
            SERVICE_NAME: settings.service_name,
            SERVICE_VERSION: settings.service_version,
            "deployment.environment": settings.env,
        })

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.otlp_endpoint,
            insecure=True,  # Use insecure for local development
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Set as global tracer provider
        trace.set_tracer_provider(tracer_provider)

        logger = structlog.get_logger(__name__)
        logger.info(
            "tracing_enabled",
            endpoint=settings.otlp_endpoint,
        )

        return tracer_provider

    except ImportError:
        logger = structlog.get_logger(__name__)
        logger.warning(
            "opentelemetry_not_installed",
            message="Tracing disabled - install opentelemetry packages",
        )
        return None
    except Exception as e:
        logger = structlog.get_logger(__name__)
        logger.error("tracing_setup_error", error=str(e))
        return None




class MetricsCollector:
    """Collects and exposes metrics for the MCP Vector Server."""

    def __init__(self):
        self.counters = {
            "query_total": 0,
            "upsert_total": 0,
            "delete_total": 0,
            "get_total": 0,
            "error_total": 0,
            "rate_limit_exceeded_total": 0,
        }
        self.gauges = {
            "query_latency_ms": 0.0,
            "upsert_latency_ms": 0.0,
            "no_results_rate": 0.0,
            "low_confidence_rate": 0.0,
        }
        self.histograms = {
            "query_latency_bucket": {},  # {bucket: count}
            "top_k_distribution": {},  # {top_k: count}
        }

        # Latency buckets (in ms)
        self.latency_buckets = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

    def inc_counter(self, name: str, value: int = 1):
        """Increment a counter."""
        if name in self.counters:
            self.counters[name] += value

    def set_gauge(self, name: str, value: float):
        """Set a gauge value."""
        if name in self.gauges:
            self.gauges[name] = value

    def observe_latency(self, name: str, value_ms: float):
        """Observe a latency value for histogram."""
        bucket_name = f"{name}_bucket"
        if bucket_name not in self.histograms:
            self.histograms[bucket_name] = {}

        # Find the right bucket
        for bucket in self.latency_buckets:
            if value_ms <= bucket:
                key = f"le_{bucket}"
                self.histograms[bucket_name][key] = (
                    self.histograms[bucket_name].get(key, 0) + 1
                )
                break
        else:
            # +Inf bucket
            self.histograms[bucket_name]["le_inf"] = (
                self.histograms[bucket_name].get("le_inf", 0) + 1
            )

    def observe_top_k(self, value: int):
        """Observe a top_k value."""
        key = str(value)
        self.histograms["top_k_distribution"][key] = (
            self.histograms["top_k_distribution"].get(key, 0) + 1
        )

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        # Counters
        for name, value in self.counters.items():
            metric_name = f"mcp_vector_{name}"
            lines.append(f"# HELP {metric_name} Total count of {name.replace('_', ' ')}")
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"{metric_name} {value}")
            lines.append("")

        # Gauges
        for name, value in self.gauges.items():
            metric_name = f"mcp_vector_{name}"
            lines.append(f"# HELP {metric_name} Current value of {name.replace('_', ' ')}")
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"{metric_name} {value:.4f}")
            lines.append("")

        # Histograms (simplified)
        for name, buckets in self.histograms.items():
            if not buckets:
                continue
            metric_name = f"mcp_vector_{name}"
            lines.append(f"# HELP {metric_name} Distribution of {name.replace('_', ' ')}")
            lines.append(f"# TYPE {metric_name} histogram")
            for bucket, count in sorted(buckets.items()):
                lines.append(f'{metric_name}{{bucket="{bucket}"}} {count}')
            lines.append("")

        return "\n".join(lines)


# Global metrics collector
metrics_collector = MetricsCollector()
