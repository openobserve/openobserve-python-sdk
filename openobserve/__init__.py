"""
OpenObserve Python SDK

A simple SDK for exporting OpenTelemetry traces to OpenObserve.

Usage:
    Set environment variables:
        export OPENOBSERVE_URL="http://localhost:5080"
        export OPENOBSERVE_ORG="default"
        export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="

    Generate auth token:
        echo -n "user@example.com:password" | base64

    Then initialize the SDK:
        >>> from openobserve import openobserve_init
        >>> from opentelemetry import trace
        >>>
        >>> # Initialize from environment variables
        >>> openobserve_init()
        >>>
        >>> # Use OpenTelemetry as usual
        >>> tracer = trace.get_tracer(__name__)
        >>> with tracer.start_as_current_span("my-operation"):
        ...     # Your code here
        ...     pass
"""

__version__ = "0.1.0"

from .client import (
    OpenObserveClient,
    get_tracer_provider,
    is_initialized,
    openobserve_flush,
    openobserve_init,
    openobserve_shutdown,
)
from .config import OpenObserveConfig

__all__ = [
    # Main API
    "openobserve_init",
    "openobserve_shutdown",
    "openobserve_flush",
    "is_initialized",
    "get_tracer_provider",
    # Advanced API
    "OpenObserveClient",
    "OpenObserveConfig",
    # Version
    "__version__",
]
