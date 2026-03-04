"""
OpenObserve SDK Client Module

This module provides the core client functionality for initializing
OpenTelemetry logs, metrics, and traces with OpenObserve as the backend.
"""

import atexit
import threading
from typing import Optional

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter as GRPCLogExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter as GRPCMetricExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http._log_exporter import (
    OTLPLogExporter as HTTPLogExporter,
)
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter as HTTPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPProtobufSpanExporter,
)
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

from .config import OpenObserveConfig

# Global state for singleton pattern
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None
_logger_provider: Optional[LoggerProvider] = None
_initialized_signals: set = set()  # tracks which signals are initialized: "traces", "logs", "metrics"
_lock = threading.RLock()
_atexit_registered: bool = False


class OpenObserveClient:
    """
    OpenObserve client for managing OpenTelemetry providers.

    This client handles:
    - TracerProvider / MeterProvider / LoggerProvider initialization
    - OTLP exporter setup with OpenObserve authentication
    - Global provider registration
    """

    def __init__(self, config: OpenObserveConfig):
        self.config = config
        self._tracer_provider: Optional[TracerProvider] = None
        self._meter_provider: Optional[MeterProvider] = None
        self._logger_provider: Optional[LoggerProvider] = None

    def _build_resource(self) -> Resource:
        resource_attributes = {}
        if self.config.resource_attributes:
            resource_attributes.update(self.config.resource_attributes)
        return Resource.create(resource_attributes) if resource_attributes else Resource.get_empty()

    def _build_headers(self) -> dict:
        headers = {"Authorization": self.config.auth_token}
        if self.config.additional_headers:
            headers.update(self.config.additional_headers)
        return headers

    def initialize_traces(self) -> TracerProvider:
        """Initialize and register the OpenTelemetry tracer provider."""
        resource = self._build_resource()
        self._tracer_provider = TracerProvider(resource=resource)

        headers = self._build_headers()
        endpoint = self.config.get_otlp_endpoint()

        if self.config.protocol == "grpc":
            headers["organization"] = self.config.org
            headers["stream-name"] = self.config.stream_name
            lowercase_headers = {k.lower(): v for k, v in headers.items()}
            insecure = self.config.url.startswith("http://")
            exporter = GRPCSpanExporter(
                endpoint=endpoint,
                headers=tuple(lowercase_headers.items()),
                timeout=self.config.timeout,
                insecure=insecure,
            )
        else:
            headers["stream-name"] = self.config.stream_name
            exporter = HTTPProtobufSpanExporter(
                endpoint=endpoint,
                headers=headers,
                timeout=self.config.timeout,
            )

        self._tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(self._tracer_provider)
        return self._tracer_provider

    def initialize_logs(self) -> LoggerProvider:
        """Initialize and register the OpenTelemetry logger provider."""
        resource = self._build_resource()
        self._logger_provider = LoggerProvider(resource=resource)

        headers = self._build_headers()
        endpoint = self.config.get_otlp_logs_endpoint()

        if self.config.protocol == "grpc":
            headers["organization"] = self.config.org
            headers["stream-name"] = self.config.logs_stream_name
            lowercase_headers = {k.lower(): v for k, v in headers.items()}
            insecure = self.config.url.startswith("http://")
            exporter = GRPCLogExporter(
                endpoint=endpoint,
                headers=tuple(lowercase_headers.items()),
                timeout=self.config.timeout,
                insecure=insecure,
            )
        else:
            headers["stream-name"] = self.config.logs_stream_name
            exporter = HTTPLogExporter(
                endpoint=endpoint,
                headers=headers,
                timeout=self.config.timeout,
            )

        self._logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        set_logger_provider(self._logger_provider)
        return self._logger_provider

    def initialize_metrics(self) -> MeterProvider:
        """Initialize and register the OpenTelemetry meter provider."""
        resource = self._build_resource()
        headers = self._build_headers()
        endpoint = self.config.get_otlp_metrics_endpoint()

        if self.config.protocol == "grpc":
            headers["organization"] = self.config.org
            lowercase_headers = {k.lower(): v for k, v in headers.items()}
            insecure = self.config.url.startswith("http://")
            exporter = GRPCMetricExporter(
                endpoint=endpoint,
                headers=tuple(lowercase_headers.items()),
                timeout=self.config.timeout,
                insecure=insecure,
            )
        else:
            exporter = HTTPMetricExporter(
                endpoint=endpoint,
                headers=headers,
                timeout=self.config.timeout,
            )

        reader = PeriodicExportingMetricReader(exporter)
        self._meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(self._meter_provider)
        return self._meter_provider

    def shutdown(self, timeout_millis: int = 30000) -> bool:
        if self._tracer_provider is not None:
            self._tracer_provider.shutdown()
        if self._meter_provider is not None:
            self._meter_provider.shutdown()
        if self._logger_provider is not None:
            self._logger_provider.shutdown()
        return True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        result = True
        if self._tracer_provider is not None:
            result = self._tracer_provider.force_flush(timeout_millis) and result
        if self._meter_provider is not None:
            result = self._meter_provider.force_flush(timeout_millis) and result
        if self._logger_provider is not None:
            result = self._logger_provider.force_flush(timeout_millis) and result
        return result


def _build_config(**kwargs) -> OpenObserveConfig:
    """Build OpenObserveConfig from keyword arguments, falling back to env vars."""
    config_overrides = {k: v for k, v in kwargs.items() if v is not None}
    return OpenObserveConfig.from_env(**config_overrides)


def _ensure_atexit():
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(_auto_shutdown)
        _atexit_registered = True


def openobserve_init(
    url: Optional[str] = None,
    org: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout: Optional[int] = None,
    enabled: Optional[bool] = None,
    protocol: Optional[str] = None,
    stream_name: Optional[str] = None,
    logs_stream_name: Optional[str] = None,
    additional_headers: Optional[dict] = None,
    resource_attributes: Optional[dict] = None,
    logs: Optional[bool] = None,
    metrics: Optional[bool] = None,
    traces: Optional[bool] = None,
) -> None:
    """
    Initialize OpenObserve SDK. By default initializes all signals (logs, metrics, traces).
    Pass any combination of logs/metrics/traces to selectively initialize.

    Args:
        url: Override OPENOBSERVE_URL
        org: Override OPENOBSERVE_ORG
        auth_token: Override OPENOBSERVE_AUTH_TOKEN
        timeout: Override OPENOBSERVE_TIMEOUT
        enabled: Override OPENOBSERVE_ENABLED
        protocol: Override OPENOBSERVE_PROTOCOL - "grpc" or "http/protobuf"
        stream_name: Override OPENOBSERVE_TRACES_STREAM_NAME
        logs_stream_name: Override OPENOBSERVE_LOGS_STREAM_NAME
        additional_headers: Additional HTTP headers
        resource_attributes: Additional resource attributes
        logs: Initialize logs provider. If no signal arguments are provided, defaults to True.
        metrics: Initialize metrics provider. If no signal arguments are provided, defaults to True.
        traces: Initialize traces provider. If no signal arguments are provided, defaults to True.

    Example:
        >>> from openobserve import openobserve_init
        >>>
        >>> # Initialize all (logs, metrics, traces)
        >>> openobserve_init()
        >>>
        >>> # Only logs
        >>> openobserve_init(logs=True)
        >>>
        >>> # Logs and metrics
        >>> openobserve_init(logs=True, metrics=True)
    """
    global _initialized_signals

    with _lock:
        config = _build_config(
            url=url,
            org=org,
            auth_token=auth_token,
            timeout=timeout,
            enabled=enabled,
            protocol=protocol,
            stream_name=stream_name,
            logs_stream_name=logs_stream_name,
            additional_headers=additional_headers,
            resource_attributes=resource_attributes,
        )

        if not config.enabled:
            return

        client = OpenObserveClient(config)

        signal_explicitly_set = any(flag is not None for flag in (logs, metrics, traces))
        logs_enabled = logs if logs is not None else (not signal_explicitly_set)
        metrics_enabled = metrics if metrics is not None else (not signal_explicitly_set)
        traces_enabled = traces if traces is not None else (not signal_explicitly_set)

        if traces_enabled:
            _init_traces(client)
        if logs_enabled:
            _init_logs(client)
        if metrics_enabled:
            _init_metrics(client)

        _ensure_atexit()


def openobserve_init_traces(
    url: Optional[str] = None,
    org: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout: Optional[int] = None,
    protocol: Optional[str] = None,
    stream_name: Optional[str] = None,
    additional_headers: Optional[dict] = None,
    resource_attributes: Optional[dict] = None,
) -> TracerProvider:
    """Initialize only the traces provider."""
    global _initialized_signals

    with _lock:
        config = _build_config(
            url=url, org=org, auth_token=auth_token, timeout=timeout,
            protocol=protocol, stream_name=stream_name,
            additional_headers=additional_headers, resource_attributes=resource_attributes,
        )
        client = OpenObserveClient(config)
        provider = _init_traces(client)
        _ensure_atexit()
        return provider


def openobserve_init_logs(
    url: Optional[str] = None,
    org: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout: Optional[int] = None,
    protocol: Optional[str] = None,
    logs_stream_name: Optional[str] = None,
    additional_headers: Optional[dict] = None,
    resource_attributes: Optional[dict] = None,
) -> LoggerProvider:
    """Initialize only the logs provider."""
    global _initialized_signals

    with _lock:
        config = _build_config(
            url=url, org=org, auth_token=auth_token, timeout=timeout,
            protocol=protocol, logs_stream_name=logs_stream_name,
            additional_headers=additional_headers, resource_attributes=resource_attributes,
        )
        client = OpenObserveClient(config)
        provider = _init_logs(client)
        _ensure_atexit()
        return provider


def openobserve_init_metrics(
    url: Optional[str] = None,
    org: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout: Optional[int] = None,
    protocol: Optional[str] = None,
    additional_headers: Optional[dict] = None,
    resource_attributes: Optional[dict] = None,
) -> MeterProvider:
    """Initialize only the metrics provider."""
    global _initialized_signals

    with _lock:
        config = _build_config(
            url=url, org=org, auth_token=auth_token, timeout=timeout,
            protocol=protocol,
            additional_headers=additional_headers, resource_attributes=resource_attributes,
        )
        client = OpenObserveClient(config)
        provider = _init_metrics(client)
        _ensure_atexit()
        return provider


def _init_traces(client: OpenObserveClient) -> TracerProvider:
    global _tracer_provider, _initialized_signals
    if "traces" in _initialized_signals:
        raise RuntimeError("Traces already initialized. Call openobserve_shutdown() first.")
    _tracer_provider = client.initialize_traces()
    _initialized_signals.add("traces")
    return _tracer_provider


def _init_logs(client: OpenObserveClient) -> LoggerProvider:
    global _logger_provider, _initialized_signals
    if "logs" in _initialized_signals:
        raise RuntimeError("Logs already initialized. Call openobserve_shutdown() first.")
    _logger_provider = client.initialize_logs()
    _initialized_signals.add("logs")
    return _logger_provider


def _init_metrics(client: OpenObserveClient) -> MeterProvider:
    global _meter_provider, _initialized_signals
    if "metrics" in _initialized_signals:
        raise RuntimeError("Metrics already initialized. Call openobserve_shutdown() first.")
    _meter_provider = client.initialize_metrics()
    _initialized_signals.add("metrics")
    return _meter_provider


def _auto_shutdown() -> None:
    global _atexit_registered
    if _atexit_registered:
        atexit.unregister(_auto_shutdown)
        _atexit_registered = False
    openobserve_shutdown(silent=True)


def openobserve_shutdown(timeout_millis: int = 30000, silent: bool = False) -> bool:
    """Shutdown all initialized providers and flush remaining data."""
    global _tracer_provider, _meter_provider, _logger_provider
    global _initialized_signals, _atexit_registered

    with _lock:
        if not _initialized_signals:
            return True

        if _tracer_provider is not None:
            _tracer_provider.shutdown()
            _tracer_provider = None
        if _meter_provider is not None:
            _meter_provider.shutdown()
            _meter_provider = None
        if _logger_provider is not None:
            _logger_provider.shutdown()
            _logger_provider = None

        _initialized_signals.clear()

        if _atexit_registered:
            atexit.unregister(_auto_shutdown)
            _atexit_registered = False

        return True


def openobserve_flush(timeout_millis: int = 30000) -> bool:
    """Force flush all pending data."""
    result = True
    if _tracer_provider is not None:
        result = _tracer_provider.force_flush(timeout_millis) and result
    if _meter_provider is not None:
        result = _meter_provider.force_flush(timeout_millis) and result
    if _logger_provider is not None:
        result = _logger_provider.force_flush(timeout_millis) and result
    return result


def is_initialized() -> bool:
    """Check if any signal is initialized."""
    return bool(_initialized_signals)


def get_tracer_provider() -> Optional[TracerProvider]:
    """Get the current tracer provider."""
    return _tracer_provider


def get_meter_provider() -> Optional[MeterProvider]:
    """Get the current meter provider."""
    return _meter_provider


def get_logger_provider() -> Optional[LoggerProvider]:
    """Get the current logger provider."""
    return _logger_provider
