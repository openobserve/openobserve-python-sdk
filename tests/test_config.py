"""
Tests for configuration module
"""

import pytest

from openobserve.config import OpenObserveConfig


def test_config_creation_with_required_params():
    """Test creating config with required parameters."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
    )

    assert config.url == "http://localhost:5080"
    assert config.org == "default"
    assert config.auth_token == "Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw=="
    assert config.timeout == 30  # default
    assert config.enabled is True  # default
    assert config.protocol == "http/protobuf"  # default


def test_config_removes_trailing_slash():
    """Test that trailing slash is removed from URL."""
    config = OpenObserveConfig(
        url="http://localhost:5080/",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
    )

    assert config.url == "http://localhost:5080"


def test_config_validation_missing_url():
    """Test that ValueError is raised when URL is missing."""
    with pytest.raises(ValueError, match="OpenObserve URL is required"):
        OpenObserveConfig(
            url="",
            org="default",
            auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        )


def test_config_validation_missing_org():
    """Test that ValueError is raised when org is missing."""
    with pytest.raises(ValueError, match="OpenObserve organization is required"):
        OpenObserveConfig(
            url="http://localhost:5080",
            org="",
            auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        )


def test_config_validation_invalid_timeout():
    """Test that ValueError is raised for invalid timeout."""
    with pytest.raises(ValueError, match="Timeout must be positive"):
        OpenObserveConfig(
            url="http://localhost:5080",
            org="default",
            auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
            timeout=-1,
        )


def test_config_get_otlp_endpoint():
    """Test OTLP endpoint construction for HTTP."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="myorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
    )

    endpoint = config.get_otlp_endpoint()
    assert endpoint == "http://localhost:5080/api/myorg/v1/traces"


def test_config_get_otlp_endpoint_grpc():
    """Test OTLP endpoint construction for gRPC."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="myorg",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="grpc",
    )

    endpoint = config.get_otlp_endpoint()
    assert endpoint == "localhost:5080"


def test_config_from_env(monkeypatch):
    """Test creating config from environment variables."""
    # Set environment variables
    monkeypatch.setenv("OPENOBSERVE_URL", "http://test:5080")
    monkeypatch.setenv("OPENOBSERVE_ORG", "testorg")
    monkeypatch.setenv("OPENOBSERVE_AUTH_TOKEN", "Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==")
    monkeypatch.setenv("OPENOBSERVE_TIMEOUT", "60")
    monkeypatch.setenv("OPENOBSERVE_ENABLED", "true")
    monkeypatch.setenv("OPENOBSERVE_PROTOCOL", "grpc")

    config = OpenObserveConfig.from_env()

    assert config.url == "http://test:5080"
    assert config.org == "testorg"
    assert config.auth_token == "Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw=="
    assert config.timeout == 60
    assert config.enabled is True
    assert config.protocol == "grpc"


def test_config_from_env_with_overrides(monkeypatch):
    """Test that explicit parameters override environment variables."""
    monkeypatch.setenv("OPENOBSERVE_URL", "http://env:5080")
    monkeypatch.setenv("OPENOBSERVE_ORG", "envorg")
    monkeypatch.setenv("OPENOBSERVE_AUTH_TOKEN", "Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==")
    monkeypatch.setenv("OPENOBSERVE_PROTOCOL", "http/protobuf")

    config = OpenObserveConfig.from_env(url="http://override:5080", protocol="grpc")

    assert config.url == "http://override:5080"  # overridden
    assert config.org == "envorg"  # from env
    assert config.protocol == "grpc"  # overridden


def test_config_additional_headers():
    """Test additional headers configuration."""
    headers = {"X-Custom-Header": "custom-value"}
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        additional_headers=headers,
    )

    assert config.additional_headers == headers


def test_config_resource_attributes():
    """Test resource attributes configuration."""
    attributes = {"deployment.environment": "production"}
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        resource_attributes=attributes,
    )

    assert config.resource_attributes == attributes


def test_config_protocol_validation():
    """Test that invalid protocol raises ValueError."""
    with pytest.raises(ValueError, match="Protocol must be either 'grpc' or 'http/protobuf'"):
        OpenObserveConfig(
            url="http://localhost:5080",
            org="default",
            auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
            protocol="invalid",
        )


def test_config_protocol_default():
    """Test that default protocol is http/protobuf."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
    )

    assert config.protocol == "http/protobuf"


def test_config_protocol_grpc():
    """Test that grpc protocol can be set."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="grpc",
    )

    assert config.protocol == "grpc"


def test_config_protocol_http_protobuf():
    """Test that http/protobuf protocol can be set."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        protocol="http/protobuf",
    )

    assert config.protocol == "http/protobuf"


def test_config_stream_name_default():
    """Test that default stream_name is 'default'."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
    )

    assert config.stream_name == "default"


def test_config_stream_name_custom():
    """Test that custom stream_name can be set."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        auth_token="Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==",
        stream_name="custom-stream",
    )

    assert config.stream_name == "custom-stream"


def test_config_stream_name_from_env(monkeypatch):
    """Test creating config with stream_name from environment variables."""
    monkeypatch.setenv("OPENOBSERVE_URL", "http://test:5080")
    monkeypatch.setenv("OPENOBSERVE_ORG", "testorg")
    monkeypatch.setenv("OPENOBSERVE_AUTH_TOKEN", "Basic dGVzdEB0ZXN0LmNvbTp0ZXN0cGFzcw==")
    monkeypatch.setenv("OPENOBSERVE_STREAM_NAME", "my-stream")

    config = OpenObserveConfig.from_env()

    assert config.stream_name == "my-stream"
