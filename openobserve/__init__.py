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

    Run an experiment against your own code:
        >>> from openobserve import experiment, scorer, datasets, score_configs
        >>>
        >>> score_configs.ensure("exact_match", type="numeric", min=0, max=1)
        >>>
        >>> @scorer(config="exact_match")
        ... def exact_match(output, expected_output):
        ...     return 1.0 if output.strip() == expected_output.strip() else 0.0
        >>>
        >>> result = experiment.run(
        ...     "prompt-v3",
        ...     dataset="rag-qa-golden",
        ...     task=my_task,
        ...     scorers=["answer_correctness@2", exact_match],
        ... )
        >>> print(result.url)
"""

__version__ = "0.1.1"

from . import datasets, experiment, score_configs
from ._eval.errors import (
    APIError,
    ConfigurationError,
    OpenObserveEvalError,
    RegressionError,
    TransportError,
    ValidationError,
)
from ._eval.types import Skip, TaskContext, TaskResult, Usage
from .agent import openobserve_agent
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
from .scorer import scorer

__all__ = [
    # Main API
    "openobserve_init",
    "openobserve_init_logs",
    "openobserve_init_metrics",
    "openobserve_init_traces",
    "openobserve_shutdown",
    "openobserve_flush",
    "openobserve_agent",
    "is_initialized",
    "get_tracer_provider",
    "get_meter_provider",
    "get_logger_provider",
    # Advanced API
    "OpenObserveClient",
    "OpenObserveConfig",
    # Evaluation API
    "experiment",
    "datasets",
    "score_configs",
    "scorer",
    "Skip",
    "TaskResult",
    "TaskContext",
    "Usage",
    "OpenObserveEvalError",
    "APIError",
    "ConfigurationError",
    "RegressionError",
    "TransportError",
    "ValidationError",
    # Version
    "__version__",
]
