"""
OpenObserve Python SDK

A simple SDK for exporting OpenTelemetry logs, metrics, and traces to OpenObserve.

Usage:
    Set environment variables:
        export OPENOBSERVE_URL="http://localhost:5080"
        export OPENOBSERVE_ORG="default"
        export OPENOBSERVE_AUTH_TOKEN="Basic cm9vdEBleGFtcGxlLmNvbTpDb21wbGV4cGFzczEyMz=="

    Then initialize the SDK:
        >>> from openobserve import openobserve_init
        >>>
        >>> # Initialize all signals (logs, metrics, traces)
        >>> openobserve_init()
        >>>
        >>> # Or selectively initialize
        >>> openobserve_init(logs=True)  # only logs
        >>>
        >>> # Or use individual init functions
        >>> from openobserve import openobserve_init_traces
        >>> openobserve_init_traces()
"""

__version__ = "0.1.0"

from .client import (
    OpenObserveClient,
    get_logger_provider,
    get_meter_provider,
    get_tracer_provider,
    is_initialized,
    openobserve_flush,
    openobserve_init,
    openobserve_init_logs,
    openobserve_init_metrics,
    openobserve_init_traces,
    openobserve_shutdown,
)
from .config import OpenObserveConfig

__all__ = [
    # Main API
    "openobserve_init",
    "openobserve_init_logs",
    "openobserve_init_metrics",
    "openobserve_init_traces",
    "openobserve_shutdown",
    "openobserve_flush",
    "is_initialized",
    "get_tracer_provider",
    "get_meter_provider",
    "get_logger_provider",
    # Advanced API
    "OpenObserveClient",
    "OpenObserveConfig",
    # Version
    "__version__",
]
