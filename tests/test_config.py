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
        user="test@example.com",
        password="testpass",
    )

    assert config.url == "http://localhost:5080"
    assert config.org == "default"
    assert config.user == "test@example.com"
    assert config.password == "testpass"
    assert config.service_name == "openobserve-service"  # default
    assert config.timeout == 30  # default
    assert config.enabled is True  # default


def test_config_removes_trailing_slash():
    """Test that trailing slash is removed from URL."""
    config = OpenObserveConfig(
        url="http://localhost:5080/",
        org="default",
        user="test@example.com",
        password="testpass",
    )

    assert config.url == "http://localhost:5080"


def test_config_validation_missing_url():
    """Test that ValueError is raised when URL is missing."""
    with pytest.raises(ValueError, match="OpenObserve URL is required"):
        OpenObserveConfig(
            url="",
            org="default",
            user="test@example.com",
            password="testpass",
        )


def test_config_validation_missing_org():
    """Test that ValueError is raised when org is missing."""
    with pytest.raises(ValueError, match="OpenObserve organization is required"):
        OpenObserveConfig(
            url="http://localhost:5080",
            org="",
            user="test@example.com",
            password="testpass",
        )


def test_config_validation_invalid_timeout():
    """Test that ValueError is raised for invalid timeout."""
    with pytest.raises(ValueError, match="Timeout must be positive"):
        OpenObserveConfig(
            url="http://localhost:5080",
            org="default",
            user="test@example.com",
            password="testpass",
            timeout=-1,
        )


def test_config_get_otlp_endpoint():
    """Test OTLP endpoint construction."""
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="myorg",
        user="test@example.com",
        password="testpass",
    )

    endpoint = config.get_otlp_endpoint()
    assert endpoint == "http://localhost:5080/api/myorg/v1/traces"


def test_config_from_env(monkeypatch):
    """Test creating config from environment variables."""
    # Set environment variables
    monkeypatch.setenv("OPENOBSERVE_URL", "http://test:5080")
    monkeypatch.setenv("OPENOBSERVE_ORG", "testorg")
    monkeypatch.setenv("OPENOBSERVE_USER", "envuser@example.com")
    monkeypatch.setenv("OPENOBSERVE_PASSWORD", "envpass")
    monkeypatch.setenv("OPENOBSERVE_SERVICE_NAME", "test-service")
    monkeypatch.setenv("OPENOBSERVE_TIMEOUT", "60")
    monkeypatch.setenv("OPENOBSERVE_ENABLED", "true")

    config = OpenObserveConfig.from_env()

    assert config.url == "http://test:5080"
    assert config.org == "testorg"
    assert config.user == "envuser@example.com"
    assert config.password == "envpass"
    assert config.service_name == "test-service"
    assert config.timeout == 60
    assert config.enabled is True


def test_config_from_env_with_overrides(monkeypatch):
    """Test that explicit parameters override environment variables."""
    monkeypatch.setenv("OPENOBSERVE_URL", "http://env:5080")
    monkeypatch.setenv("OPENOBSERVE_ORG", "envorg")
    monkeypatch.setenv("OPENOBSERVE_USER", "envuser@example.com")
    monkeypatch.setenv("OPENOBSERVE_PASSWORD", "envpass")

    config = OpenObserveConfig.from_env(url="http://override:5080", service_name="override-service")

    assert config.url == "http://override:5080"  # overridden
    assert config.org == "envorg"  # from env
    assert config.service_name == "override-service"  # overridden


def test_config_additional_headers():
    """Test additional headers configuration."""
    headers = {"X-Custom-Header": "custom-value"}
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        user="test@example.com",
        password="testpass",
        additional_headers=headers,
    )

    assert config.additional_headers == headers


def test_config_resource_attributes():
    """Test resource attributes configuration."""
    attributes = {"deployment.environment": "production"}
    config = OpenObserveConfig(
        url="http://localhost:5080",
        org="default",
        user="test@example.com",
        password="testpass",
        resource_attributes=attributes,
    )

    assert config.resource_attributes == attributes
