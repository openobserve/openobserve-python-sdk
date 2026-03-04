"""
Tests for client module
"""

from unittest.mock import Mock, patch

from openobserve import client as client_module
from openobserve.client import OpenObserveClient
from openobserve.config import OpenObserveConfig


def test_grpc_exporter_headers_are_lowercase():
    """Test that gRPC exporter normalizes headers to lowercase."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="myorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="grpc",
        additional_headers={"X-Custom-Header": "value"},
    )

    client = OpenObserveClient(config)

    with patch("openobserve.client.GRPCSpanExporter") as mock_grpc_exporter:
        mock_grpc_exporter.return_value = Mock()
        client.initialize_traces()

        # Verify GRPCSpanExporter was called
        mock_grpc_exporter.assert_called_once()

        # Get the headers argument
        call_kwargs = mock_grpc_exporter.call_args[1]
        headers = dict(call_kwargs["headers"])

        # All keys should be lowercase
        assert "authorization" in headers
        assert "x-custom-header" in headers
        assert "organization" in headers
        assert "stream-name" in headers
        assert "Authorization" not in headers
        assert "X-Custom-Header" not in headers

        # Values should be unchanged
        assert headers["authorization"] == "Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw=="
        assert headers["x-custom-header"] == "value"
        assert headers["organization"] == "myorg"
        assert headers["stream-name"] == "default"

        # HTTP URL should use insecure=True
        assert call_kwargs["insecure"] is True


def test_http_exporter_headers_preserve_case():
    """Test that HTTP exporter preserves header case and includes stream-name."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="myorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="http/protobuf",
        additional_headers={"X-Custom-Header": "value"},
    )

    client = OpenObserveClient(config)

    with patch("openobserve.client.HTTPProtobufSpanExporter") as mock_http_exporter:
        mock_http_exporter.return_value = Mock()
        client.initialize_traces()

        # Verify HTTPProtobufSpanExporter was called
        mock_http_exporter.assert_called_once()

        # Get the headers argument
        call_kwargs = mock_http_exporter.call_args[1]
        headers = call_kwargs["headers"]

        # HTTP headers should preserve case
        assert "Authorization" in headers
        assert "X-Custom-Header" in headers
        assert "stream-name" in headers

        # Organization should NOT be in headers (it's in the URL path for HTTP)
        assert "organization" not in headers

        # Values should be unchanged
        assert headers["Authorization"] == "Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw=="
        assert headers["X-Custom-Header"] == "value"
        assert headers["stream-name"] == "default"


def test_grpc_exporter_endpoint():
    """Test gRPC exporter uses correct endpoint format."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="grpc",
    )

    client = OpenObserveClient(config)

    with patch("openobserve.client.GRPCSpanExporter") as mock_grpc_exporter:
        mock_grpc_exporter.return_value = Mock()
        client.initialize_traces()

        # Verify endpoint is host:port format for gRPC
        call_kwargs = mock_grpc_exporter.call_args[1]
        assert call_kwargs["endpoint"] == "localhost:5080"


def test_http_exporter_endpoint():
    """Test HTTP exporter uses correct endpoint format."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="testorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="http/protobuf",
    )

    client = OpenObserveClient(config)

    with patch("openobserve.client.HTTPProtobufSpanExporter") as mock_http_exporter:
        mock_http_exporter.return_value = Mock()
        client.initialize_traces()

        # Verify endpoint is full URL with path for HTTP
        call_kwargs = mock_http_exporter.call_args[1]
        assert call_kwargs["endpoint"] == "http://localhost:5080/api/testorg/v1/traces"


def test_grpc_exporter_insecure_for_http():
    """Test gRPC exporter uses insecure=True for HTTP URLs."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="grpc",
    )

    client = OpenObserveClient(config)

    with patch("openobserve.client.GRPCSpanExporter") as mock_grpc_exporter:
        mock_grpc_exporter.return_value = Mock()
        client.initialize_traces()

        # Verify insecure=True for HTTP URLs
        call_kwargs = mock_grpc_exporter.call_args[1]
        assert call_kwargs["insecure"] is True


def test_grpc_exporter_secure_for_https():
    """Test gRPC exporter uses insecure=False for HTTPS URLs."""
    config = OpenObserveConfig(
        url="https://api.openobserve.ai",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="grpc",
    )

    client = OpenObserveClient(config)

    with patch("openobserve.client.GRPCSpanExporter") as mock_grpc_exporter:
        mock_grpc_exporter.return_value = Mock()
        client.initialize_traces()

        # Verify insecure=False for HTTPS URLs
        call_kwargs = mock_grpc_exporter.call_args[1]
        assert call_kwargs["insecure"] is False


def test_grpc_exporter_includes_organization_header():
    """Test gRPC exporter includes organization and stream-name headers."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="testorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="grpc",
    )

    client = OpenObserveClient(config)

    with patch("openobserve.client.GRPCSpanExporter") as mock_grpc_exporter:
        mock_grpc_exporter.return_value = Mock()
        client.initialize_traces()

        # Get the headers argument
        call_kwargs = mock_grpc_exporter.call_args[1]
        headers = dict(call_kwargs["headers"])

        # Verify OpenObserve-specific gRPC headers
        assert headers["organization"] == "testorg"
        assert headers["stream-name"] == "default"


def test_grpc_exporter_custom_stream_name():
    """Test gRPC exporter uses custom stream-name from config."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="testorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="grpc",
        stream_name="custom-traces",
    )

    client = OpenObserveClient(config)

    with patch("openobserve.client.GRPCSpanExporter") as mock_grpc_exporter:
        mock_grpc_exporter.return_value = Mock()
        client.initialize_traces()

        # Get the headers argument
        call_kwargs = mock_grpc_exporter.call_args[1]
        headers = dict(call_kwargs["headers"])

        # Verify custom stream-name is used
        assert headers["stream-name"] == "custom-traces"


def test_http_exporter_custom_stream_name():
    """Test HTTP exporter uses custom stream-name from config."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="testorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="http/protobuf",
        stream_name="custom-http-traces",
    )

    client = OpenObserveClient(config)

    with patch("openobserve.client.HTTPProtobufSpanExporter") as mock_http_exporter:
        mock_http_exporter.return_value = Mock()
        client.initialize_traces()

        # Get the headers argument
        call_kwargs = mock_http_exporter.call_args[1]
        headers = call_kwargs["headers"]

        # Verify custom stream-name is used
        assert headers["stream-name"] == "custom-http-traces"
        # Organization should be in URL path, not headers
        assert "organization" not in headers


def test_openobserve_init_defaults_enable_all():
    """Calling openobserve_init() without signal flags should initialize all signals."""
    with patch("openobserve.client._init_traces") as mock_traces, \
        patch("openobserve.client._init_logs") as mock_logs, \
        patch("openobserve.client._init_metrics") as mock_metrics, \
        patch("openobserve.client._ensure_atexit"):
        client_module.openobserve_init(auth_token="token")

    mock_traces.assert_called_once()
    mock_logs.assert_called_once()
    mock_metrics.assert_called_once()


def test_openobserve_init_only_logs_when_flag_set():
    """Passing logs=True should disable other signals by default."""
    with patch("openobserve.client._init_traces") as mock_traces, \
        patch("openobserve.client._init_logs") as mock_logs, \
        patch("openobserve.client._init_metrics") as mock_metrics, \
        patch("openobserve.client._ensure_atexit"):
        client_module.openobserve_init(auth_token="token", logs=True)

    mock_logs.assert_called_once()
    mock_traces.assert_not_called()
    mock_metrics.assert_not_called()


def test_openobserve_init_combines_selected_signals():
    """Multiple explicit flags should only initialize the selected signals."""
    with patch("openobserve.client._init_traces") as mock_traces, \
        patch("openobserve.client._init_logs") as mock_logs, \
        patch("openobserve.client._init_metrics") as mock_metrics, \
        patch("openobserve.client._ensure_atexit"):
        client_module.openobserve_init(auth_token="token", logs=True, metrics=True)

    mock_logs.assert_called_once()
    mock_metrics.assert_called_once()
    mock_traces.assert_not_called()
