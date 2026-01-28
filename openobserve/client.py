"""
OpenObserve SDK Client Module

This module provides the core client functionality for initializing
OpenTelemetry with OpenObserve as the backend.
"""

import atexit
import threading
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPProtobufSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

from .config import OpenObserveConfig

# Global state for singleton pattern
_tracer_provider: Optional[TracerProvider] = None
_initialized: bool = False
_lock = threading.RLock()
_atexit_registered: bool = False


class OpenObserveClient:
    """
    OpenObserve client for managing OpenTelemetry tracer provider.

    This client handles:
    - TracerProvider initialization and configuration
    - OTLP exporter setup with OpenObserve authentication
    - BatchSpanProcessor configuration
    - Global tracer provider registration
    """

    def __init__(self, config: OpenObserveConfig):
        """
        Initialize OpenObserve client.

        Args:
            config: OpenObserveConfig instance with connection details
        """
        self.config = config
        self._tracer_provider: Optional[TracerProvider] = None
        self._initialized = False

    def initialize(self) -> TracerProvider:
        """
        Initialize and register the OpenTelemetry tracer provider.

        This method:
        1. Creates a Resource (with custom attributes if provided)
        2. Initializes a TracerProvider
        3. Configures OTLP exporter with authentication
        4. Adds a BatchSpanProcessor
        5. Registers the provider globally

        Returns:
            TracerProvider instance

        Raises:
            RuntimeError: If already initialized or if tracing is disabled
        """
        if not self.config.enabled:
            raise RuntimeError("OpenObserve tracing is disabled")

        if self._initialized:
            raise RuntimeError("OpenObserve client already initialized")

        # 1. Create resource with custom attributes if provided
        resource_attributes = {}
        if self.config.resource_attributes:
            resource_attributes.update(self.config.resource_attributes)

        resource = (
            Resource.create(resource_attributes) if resource_attributes else Resource.get_empty()
        )

        # 2. Create TracerProvider
        self._tracer_provider = TracerProvider(resource=resource)

        # 3. Configure OTLP exporter with authentication
        otlp_exporter = self._create_otlp_exporter()

        # 4. Add BatchSpanProcessor for efficient export
        span_processor = BatchSpanProcessor(otlp_exporter)
        self._tracer_provider.add_span_processor(span_processor)

        # 5. Register as global tracer provider
        trace.set_tracer_provider(self._tracer_provider)

        self._initialized = True

        return self._tracer_provider

    def _create_otlp_exporter(self) -> SpanExporter:
        """
        Create OTLP span exporter configured for OpenObserve.

        Returns:
            SpanExporter instance (gRPC or HTTP/Protobuf based on configuration)
        """
        # Prepare headers with authorization token
        headers = {
            "Authorization": self.config.auth_token,
        }

        # Add additional headers if provided
        if self.config.additional_headers:
            headers.update(self.config.additional_headers)

        # Create OTLP exporter
        endpoint = self.config.get_otlp_endpoint()

        # Choose exporter based on protocol configuration
        if self.config.protocol == "grpc":
            # For gRPC, OpenObserve requires organization and stream-name as headers
            # (organization is not in the endpoint URL for gRPC)
            headers["organization"] = self.config.org
            headers["stream-name"] = self.config.stream_name

            # gRPC requires lowercase metadata keys
            lowercase_headers = {k.lower(): v for k, v in headers.items()}

            # Use insecure channel for HTTP URLs (non-TLS)
            # gRPC defaults to TLS, but plain HTTP endpoints need insecure=True
            insecure = self.config.url.startswith("http://")

            return GRPCSpanExporter(
                endpoint=endpoint,
                headers=tuple(lowercase_headers.items()),
                timeout=self.config.timeout,
                insecure=insecure,
            )
        else:  # http/protobuf (default)
            # For HTTP/Protobuf, organization is in the URL path, not headers
            # Only add stream-name header
            headers["stream-name"] = self.config.stream_name

            return HTTPProtobufSpanExporter(
                endpoint=endpoint,
                headers=headers,
                timeout=self.config.timeout,
            )

    def get_tracer(self, name: str = __name__, version: Optional[str] = None):
        """
        Get a tracer from the initialized provider.

        Args:
            name: Tracer name (typically __name__ of the module)
            version: Optional version string

        Returns:
            Tracer instance

        Raises:
            RuntimeError: If client is not initialized
        """
        if not self._initialized or self._tracer_provider is None:
            raise RuntimeError("OpenObserve client not initialized. Call initialize() first.")

        return self._tracer_provider.get_tracer(name, version)

    def shutdown(self, timeout_millis: int = 30000) -> bool:
        """
        Shutdown the tracer provider and flush remaining spans.

        Args:
            timeout_millis: Timeout in milliseconds (default: 30000)

        Returns:
            True if shutdown was successful
        """
        if self._tracer_provider is not None:
            return self._tracer_provider.shutdown()
        return True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """
        Force flush all pending spans.

        Args:
            timeout_millis: Timeout in milliseconds (default: 30000)

        Returns:
            True if flush was successful
        """
        if self._tracer_provider is not None:
            return self._tracer_provider.force_flush(timeout_millis)
        return True


def openobserve_init(
    url: Optional[str] = None,
    org: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout: Optional[int] = None,
    enabled: Optional[bool] = None,
    protocol: Optional[str] = None,
    stream_name: Optional[str] = None,
    additional_headers: Optional[dict] = None,
    resource_attributes: Optional[dict] = None,
) -> TracerProvider:
    """
    Initialize OpenObserve SDK and register global tracer provider.

    This is the main entry point for the SDK. All configuration is read from
    environment variables by default. You can optionally pass parameters to
    override specific settings.

    Environment Variables:
        OPENOBSERVE_URL: OpenObserve base URL (required)
        OPENOBSERVE_ORG: Organization name (default: "default")
        OPENOBSERVE_AUTH_TOKEN: Authorization token (required)
                                Format: "Basic <base64-encoded-credentials>"
                                Example: "Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="
        OPENOBSERVE_TIMEOUT: Request timeout in seconds (default: 30)
        OPENOBSERVE_ENABLED: Enable/disable tracing (default: "true")
        OPENOBSERVE_PROTOCOL: Protocol to use - "grpc" or "http/protobuf" (default: "http/protobuf")
        OPENOBSERVE_STREAM_NAME: Stream name for traces (default: "default")

    Args:
        url: Override OPENOBSERVE_URL (optional)
        org: Override OPENOBSERVE_ORG (optional)
        auth_token: Override OPENOBSERVE_AUTH_TOKEN (optional)
        timeout: Override OPENOBSERVE_TIMEOUT (optional)
        enabled: Override OPENOBSERVE_ENABLED (optional)
        protocol: Override OPENOBSERVE_PROTOCOL - "grpc" or "http/protobuf" (optional)
        stream_name: Override OPENOBSERVE_STREAM_NAME - stream name for traces (optional)
        additional_headers: Additional HTTP headers (optional)
        resource_attributes: Additional resource attributes (optional)

    Returns:
        TracerProvider instance

    Raises:
        ValueError: If required configuration is missing from environment
        RuntimeError: If already initialized

    Example:
        >>> from openobserve import openobserve_init
        >>> from opentelemetry import trace
        >>>
        >>> # Recommended: Use environment variables
        >>> # export OPENOBSERVE_URL="http://localhost:5080"
        >>> # export OPENOBSERVE_ORG="default"
        >>> # export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="
        >>> openobserve_init()
        >>>
        >>> # Use the global tracer
        >>> tracer = trace.get_tracer(__name__)
        >>> with tracer.start_as_current_span("my-operation"):
        ...     # Your code here
        ...     pass
        >>>
        >>> # No need to call openobserve_shutdown() explicitly!
        >>> # The SDK will automatically flush and shutdown on program exit.
    """
    global _tracer_provider, _initialized, _atexit_registered

    with _lock:
        if _initialized:
            raise RuntimeError(
                "OpenObserve SDK already initialized. "
                "Call openobserve_shutdown() first if you need to reinitialize."
            )

        # Build configuration from environment and parameters
        config_overrides = {}
        if url is not None:
            config_overrides["url"] = url
        if org is not None:
            config_overrides["org"] = org
        if auth_token is not None:
            config_overrides["auth_token"] = auth_token
        if timeout is not None:
            config_overrides["timeout"] = timeout
        if enabled is not None:
            config_overrides["enabled"] = enabled
        if protocol is not None:
            config_overrides["protocol"] = protocol
        if stream_name is not None:
            config_overrides["stream_name"] = stream_name
        if additional_headers is not None:
            config_overrides["additional_headers"] = additional_headers
        if resource_attributes is not None:
            config_overrides["resource_attributes"] = resource_attributes

        # Create configuration
        config = OpenObserveConfig.from_env(**config_overrides)

        # Create and initialize client
        client = OpenObserveClient(config)
        _tracer_provider = client.initialize()
        _initialized = True

        # Register automatic shutdown on program exit
        if not _atexit_registered:
            atexit.register(_auto_shutdown)
            _atexit_registered = True

        return _tracer_provider


def _auto_shutdown() -> None:
    """
    Internal function called automatically on program exit via atexit.

    This ensures all pending spans are flushed before the program terminates.
    """
    global _atexit_registered

    # Unregister to prevent duplicate calls
    if _atexit_registered:
        atexit.unregister(_auto_shutdown)
        _atexit_registered = False

    # Perform shutdown silently (no print statements)
    openobserve_shutdown(silent=True)


def openobserve_shutdown(timeout_millis: int = 30000, silent: bool = False) -> bool:
    """
    Shutdown the OpenObserve SDK and flush remaining spans.

    Note: This function is called automatically on program exit via atexit.
    You typically don't need to call this manually unless you want to explicitly
    control when the SDK shuts down.

    Args:
        timeout_millis: Timeout in milliseconds (default: 30000)
        silent: If True, suppress output messages (default: False)

    Returns:
        True if shutdown was successful
    """
    global _tracer_provider, _initialized, _atexit_registered

    with _lock:
        if not _initialized or _tracer_provider is None:
            return True

        result = _tracer_provider.shutdown()
        _tracer_provider = None
        _initialized = False

        # Unregister atexit handler to prevent duplicate shutdown
        if _atexit_registered:
            atexit.unregister(_auto_shutdown)
            _atexit_registered = False

        if not silent:
            print("✓ OpenObserve SDK shutdown complete")
        return result


def openobserve_flush(timeout_millis: int = 30000) -> bool:
    """
    Force flush all pending spans to OpenObserve.

    Args:
        timeout_millis: Timeout in milliseconds (default: 30000)

    Returns:
        True if flush was successful
    """
    global _tracer_provider

    if _tracer_provider is not None:
        return _tracer_provider.force_flush(timeout_millis)
    return True


def is_initialized() -> bool:
    """
    Check if OpenObserve SDK is initialized.

    Returns:
        True if initialized
    """
    return _initialized


def get_tracer_provider() -> Optional[TracerProvider]:
    """
    Get the current tracer provider.

    Returns:
        TracerProvider instance or None if not initialized
    """
    return _tracer_provider
