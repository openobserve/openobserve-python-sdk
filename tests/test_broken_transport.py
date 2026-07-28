"""
Tests that a broken or version-drifted OTLP transport that is NOT in use can
never break the SDK.

Regression for the 2026-05 incident where opentelemetry-exporter-otlp-proto-grpc
drifted to a version incompatible with the installed opentelemetry-sdk and the
module-level import killed the whole package — including http/protobuf users.
"""

import importlib
import sys
from unittest.mock import Mock, patch

import pytest

from openobserve.client import OpenObserveClient
from openobserve.config import OpenObserveConfig

GRPC_EXPORTER_MODULES = [
    "opentelemetry.exporter.otlp.proto.grpc",
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    "opentelemetry.exporter.otlp.proto.grpc._log_exporter",
    "opentelemetry.exporter.otlp.proto.grpc.metric_exporter",
]


@pytest.fixture
def broken_grpc_exporter():
    """Simulate a broken gRPC exporter install: any import of it raises ImportError."""
    saved = {name: sys.modules.get(name) for name in GRPC_EXPORTER_MODULES}
    for name in GRPC_EXPORTER_MODULES:
        # None in sys.modules makes `import name` raise ImportError
        sys.modules[name] = None
    yield
    for name, mod in saved.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


def _http_config():
    return OpenObserveConfig(
        url="http://localhost:5080",
        org="myorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="http/protobuf",
    )


def _grpc_config():
    return OpenObserveConfig(
        url="http://localhost:5080",
        org="myorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="grpc",
    )


def test_package_imports_with_broken_grpc_exporter(broken_grpc_exporter):
    """`import openobserve` must not touch the gRPC exporter at all."""
    saved = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "openobserve" or name.startswith("openobserve.")
    }
    try:
        importlib.import_module("openobserve")
    finally:
        sys.modules.update(saved)


def test_http_traces_work_with_broken_grpc_exporter(broken_grpc_exporter):
    """http/protobuf users must be unaffected by a broken gRPC exporter."""
    client = OpenObserveClient(_http_config())
    with patch(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
    ) as mock_exporter:
        mock_exporter.return_value = Mock()
        client.initialize_traces()
        mock_exporter.assert_called_once()


def test_grpc_protocol_raises_actionable_error(broken_grpc_exporter):
    """grpc users get a clear ImportError pointing at the [grpc] extra, not a deep traceback."""
    client = OpenObserveClient(_grpc_config())
    with pytest.raises(ImportError, match=r"openobserve-telemetry-sdk\[grpc\]"):
        client.initialize_traces()
