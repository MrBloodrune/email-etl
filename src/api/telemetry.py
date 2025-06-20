"""
OpenTelemetry instrumentation for Gmail ETL API

Provides comprehensive tracing, metrics, and logging for troubleshooting.
"""

import logging
import os
from typing import Dict, Any, Optional
from functools import wraps
import time

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.trace import Status, StatusCode
from prometheus_client import make_asgi_app

logger = logging.getLogger(__name__)


class TelemetryConfig:
    """Configuration for OpenTelemetry"""
    
    def __init__(self):
        self.service_name = "gmail-etl-api"
        self.service_version = "1.0.0"
        self.otlp_endpoint = os.getenv("OTLP_ENDPOINT", "localhost:4317")
        self.enable_observability = os.getenv("ENABLE_OBSERVABILITY", "true").lower() == "true"
        self.enable_console_export = os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true"
        self.enable_prometheus = os.getenv("ENABLE_PROMETHEUS_METRICS", "true").lower() == "true"
        self.prometheus_port = int(os.getenv("PROMETHEUS_PORT", "9090"))


telemetry_config = TelemetryConfig()


def setup_telemetry(app=None, config: Optional[TelemetryConfig] = None) -> Dict[str, Any]:
    """
    Set up OpenTelemetry instrumentation
    
    Returns dict with tracer, meter, and metrics app
    """
    if config:
        telemetry_config.__dict__.update(config.__dict__)
    
    # If observability is disabled, return no-op implementations
    if not telemetry_config.enable_observability:
        logger.info("Observability is disabled. Using no-op telemetry providers.")
        return setup_noop_telemetry()
    
    # Create resource
    resource = Resource.create({
        SERVICE_NAME: telemetry_config.service_name,
        SERVICE_VERSION: telemetry_config.service_version,
        "deployment.environment": os.getenv("ENVIRONMENT", "production"),
    })
    
    # Set up tracing
    trace_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(trace_provider)
    
    # Add span processors
    if telemetry_config.enable_console_export:
        trace_provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )
    
    # Add OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=telemetry_config.otlp_endpoint,
        insecure=True
    )
    trace_provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )
    
    # Set up metrics
    metrics_exporters = []
    
    # Add OTLP metrics exporter
    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=telemetry_config.otlp_endpoint,
        insecure=True
    )
    metrics_exporters.append(
        PeriodicExportingMetricReader(otlp_metric_exporter)
    )
    
    # Add Prometheus exporter
    prometheus_app = None
    if telemetry_config.enable_prometheus:
        prometheus_reader = PrometheusMetricReader()
        metrics_exporters.append(prometheus_reader)
        prometheus_app = make_asgi_app()
    
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=metrics_exporters
    )
    metrics.set_meter_provider(meter_provider)
    
    # Instrument libraries
    if app:
        FastAPIInstrumentor.instrument_app(app)
    
    Psycopg2Instrumentor().instrument()
    RequestsInstrumentor().instrument()
    LoggingInstrumentor().instrument()
    
    # Get tracer and meter
    tracer = trace.get_tracer(telemetry_config.service_name)
    meter = metrics.get_meter(telemetry_config.service_name)
    
    # Create custom metrics
    email_import_counter = meter.create_counter(
        "gmail_etl_emails_imported",
        description="Number of emails imported",
        unit="1"
    )
    
    embedding_generation_histogram = meter.create_histogram(
        "gmail_etl_embedding_generation_duration",
        description="Time taken to generate embeddings",
        unit="s"
    )
    
    search_latency_histogram = meter.create_histogram(
        "gmail_etl_search_latency",
        description="Search request latency",
        unit="s"
    )
    
    attachment_size_histogram = meter.create_histogram(
        "gmail_etl_attachment_size",
        description="Size of email attachments",
        unit="bytes"
    )
    
    logger.info(f"OpenTelemetry instrumentation set up for {telemetry_config.service_name}")
    
    return {
        "tracer": tracer,
        "meter": meter,
        "prometheus_app": prometheus_app,
        "metrics": {
            "email_import_counter": email_import_counter,
            "embedding_generation_histogram": embedding_generation_histogram,
            "search_latency_histogram": search_latency_histogram,
            "attachment_size_histogram": attachment_size_histogram,
        }
    }


# Global telemetry instances
telemetry = None


def get_tracer():
    """Get the global tracer instance"""
    if telemetry:
        return telemetry["tracer"]
    return trace.get_tracer("gmail-etl-api")


def get_meter():
    """Get the global meter instance"""
    if telemetry:
        return telemetry["meter"]
    return metrics.get_meter("gmail-etl-api")


def get_metrics():
    """Get custom metrics"""
    if telemetry:
        return telemetry["metrics"]
    return {}


def trace_operation(operation_name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator for tracing operations with intelligent span creation
    
    Usage:
        @trace_operation("import_emails", {"source": "gmail"})
        async def import_emails(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # If observability is disabled, just run the function
            if not telemetry_config.enable_observability:
                return await func(*args, **kwargs)
            
            tracer = get_tracer()
            with tracer.start_as_current_span(
                operation_name,
                attributes=attributes or {}
            ) as span:
                try:
                    # Add function arguments as span attributes
                    span.set_attribute("function.name", func.__name__)
                    
                    # Execute function
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    # Add result metadata
                    span.set_attribute("duration_seconds", duration)
                    if isinstance(result, dict):
                        for key, value in result.items():
                            if isinstance(value, (str, int, float, bool)):
                                span.set_attribute(f"result.{key}", value)
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                    
                except Exception as e:
                    span.set_status(
                        Status(StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # If observability is disabled, just run the function
            if not telemetry_config.enable_observability:
                return func(*args, **kwargs)
            
            tracer = get_tracer()
            with tracer.start_as_current_span(
                operation_name,
                attributes=attributes or {}
            ) as span:
                try:
                    span.set_attribute("function.name", func.__name__)
                    
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    span.set_attribute("duration_seconds", duration)
                    if isinstance(result, dict):
                        for key, value in result.items():
                            if isinstance(value, (str, int, float, bool)):
                                span.set_attribute(f"result.{key}", value)
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                    
                except Exception as e:
                    span.set_status(
                        Status(StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


def record_metric(metric_name: str, value: float, attributes: Optional[Dict[str, str]] = None):
    """Record a metric value"""
    if not telemetry_config.enable_observability:
        return
    
    metrics_dict = get_metrics()
    if metric_name in metrics_dict:
        metric = metrics_dict[metric_name]
        if hasattr(metric, 'add'):
            metric.add(value, attributes or {})
        elif hasattr(metric, 'record'):
            metric.record(value, attributes or {})


def create_span_context(span_name: str, attributes: Optional[Dict[str, Any]] = None):
    """Create a span context for manual span management"""
    if not telemetry_config.enable_observability:
        # Return a no-op context manager
        from contextlib import contextmanager
        @contextmanager
        def noop_span():
            yield NoOpSpan()
        return noop_span()
    
    tracer = get_tracer()
    return tracer.start_as_current_span(span_name, attributes=attributes or {})


class NoOpSpan:
    """No-op span implementation"""
    def __init__(self):
        self.start_time = time.time()
        self.end_time = None
    
    def set_attribute(self, key: str, value: Any):
        pass
    
    def set_status(self, status):
        pass
    
    def record_exception(self, exception):
        pass
    
    def get_span_context(self):
        return NoOpSpanContext()


class NoOpSpanContext:
    """No-op span context"""
    @property
    def trace_id(self):
        return 0


def setup_noop_telemetry() -> Dict[str, Any]:
    """
    Set up no-op telemetry when observability is disabled
    """
    # Return dummy implementations that do nothing
    return {
        "tracer": trace.get_tracer("noop"),
        "meter": metrics.get_meter("noop"),
        "prometheus_app": None,
        "metrics": {
            "email_import_counter": NoOpMetric(),
            "embedding_generation_histogram": NoOpMetric(),
            "search_latency_histogram": NoOpMetric(),
            "attachment_size_histogram": NoOpMetric(),
        }
    }


class NoOpMetric:
    """No-op metric implementation"""
    def add(self, value, attributes=None):
        pass
    
    def record(self, value, attributes=None):
        pass


# Initialize telemetry on module import
telemetry = setup_telemetry()