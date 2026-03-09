"""
OpenObserve SDK Configuration Module

This module handles configuration management for the OpenObserve SDK,
including environment variables and default values.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Environment variable names
ENV_OPENOBSERVE_URL = "OPENOBSERVE_URL"
ENV_OPENOBSERVE_ORG = "OPENOBSERVE_ORG"
ENV_OPENOBSERVE_AUTH_TOKEN = "OPENOBSERVE_AUTH_TOKEN"
ENV_OPENOBSERVE_TIMEOUT = "OPENOBSERVE_TIMEOUT"
ENV_OPENOBSERVE_ENABLED = "OPENOBSERVE_ENABLED"
ENV_OPENOBSERVE_PROTOCOL = "OPENOBSERVE_PROTOCOL"
ENV_OPENOBSERVE_TRACES_STREAM_NAME = "OPENOBSERVE_TRACES_STREAM_NAME"
ENV_OPENOBSERVE_LOGS_STREAM_NAME = "OPENOBSERVE_LOGS_STREAM_NAME"


@dataclass
class OpenObserveConfig:
    """
    Configuration for OpenObserve SDK.

    Attributes:
        url: OpenObserve base URL (default: "http://localhost:5080")
        org: OpenObserve organization name (default: "default")
        auth_token: Authorization token (e.g., "Basic <base64-encoded-credentials>")
        timeout: Request timeout in seconds (default: 30)
        enabled: Enable/disable tracing (default: True)
        protocol: Protocol to use for sending traces: "grpc" or "http/protobuf" (default: "http/protobuf")
        stream_name: Stream name for traces (default: "default")
        logs_stream_name: Stream name for logs (default: "default")
        additional_headers: Additional HTTP headers to send with requests
        resource_attributes: Additional resource attributes for the service
    """

    url: str
    org: str
    auth_token: Optional[str]
    timeout: int = 30
    enabled: bool = True
    protocol: str = "http/protobuf"
    stream_name: str = "default"
    logs_stream_name: str = "default"
    additional_headers: Optional[Dict[str, str]] = None
    resource_attributes: Optional[Dict[str, str]] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.url:
            raise ValueError("OpenObserve URL is required")
        if not self.org:
            raise ValueError("OpenObserve organization is required")
        if not self.auth_token:
            raise ValueError("OpenObserve auth token is required")

        # Remove trailing slash from URL
        self.url = self.url.rstrip("/")

        # Validate timeout
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")

        # Validate protocol
        if self.protocol not in ("grpc", "http/protobuf"):
            raise ValueError("Protocol must be either 'grpc' or 'http/protobuf'")

    @classmethod
    def from_env(cls, **overrides) -> "OpenObserveConfig":
        """
        Create configuration from environment variables.

        Args:
            **overrides: Override specific configuration values

        Returns:
            OpenObserveConfig instance

        Raises:
            ValueError: If required environment variables are missing
        """
        # Read from environment with overrides taking precedence
        url_value: Any = overrides.get("url") or os.getenv(
            ENV_OPENOBSERVE_URL, "http://localhost:5080"
        )
        url: str = url_value if isinstance(url_value, str) else "http://localhost:5080"

        org_value: Any = overrides.get("org") or os.getenv(ENV_OPENOBSERVE_ORG, "default")
        org: str = org_value if isinstance(org_value, str) else "default"

        auth_token: Optional[str] = overrides.get("auth_token") or os.getenv(
            ENV_OPENOBSERVE_AUTH_TOKEN
        )

        # Parse timeout from env (default to 30)
        timeout_str = os.getenv(ENV_OPENOBSERVE_TIMEOUT, "30")
        timeout = overrides.get("timeout", int(timeout_str))

        # Parse enabled flag from env (default to True)
        enabled_str = os.getenv(ENV_OPENOBSERVE_ENABLED, "true").lower()
        enabled = overrides.get("enabled", enabled_str in ("true", "1", "yes"))

        # Parse protocol from env (default to "http/protobuf")
        protocol_value: Any = overrides.get("protocol") or os.getenv(
            ENV_OPENOBSERVE_PROTOCOL, "http/protobuf"
        )
        protocol: str = protocol_value if isinstance(protocol_value, str) else "http/protobuf"

        # Parse stream_name from env (default to "default")
        stream_name_value: Any = overrides.get("stream_name") or os.getenv(
            ENV_OPENOBSERVE_TRACES_STREAM_NAME, "default"
        )
        stream_name: str = stream_name_value if isinstance(stream_name_value, str) else "default"

        # Parse logs_stream_name from env (default to "default")
        logs_stream_name_value: Any = overrides.get("logs_stream_name") or os.getenv(
            ENV_OPENOBSERVE_LOGS_STREAM_NAME, "default"
        )
        logs_stream_name: str = (
            logs_stream_name_value if isinstance(logs_stream_name_value, str) else "default"
        )

        return cls(
            url=url,
            org=org,
            auth_token=auth_token,
            timeout=timeout,
            enabled=enabled,
            protocol=protocol,
            stream_name=stream_name,
            logs_stream_name=logs_stream_name,
            additional_headers=overrides.get("additional_headers"),
            resource_attributes=overrides.get("resource_attributes"),
        )

    def _get_grpc_endpoint(self) -> str:
        """Get host:port for gRPC from URL."""
        return self.url.replace("https://", "").replace("http://", "")

    def get_otlp_endpoint(self) -> str:
        """Get the OTLP traces endpoint URL."""
        if self.protocol == "grpc":
            return self._get_grpc_endpoint()
        return f"{self.url}/api/{self.org}/v1/traces"

    def get_otlp_logs_endpoint(self) -> str:
        """Get the OTLP logs endpoint URL."""
        if self.protocol == "grpc":
            return self._get_grpc_endpoint()
        return f"{self.url}/api/{self.org}/v1/logs"

    def get_otlp_metrics_endpoint(self) -> str:
        """Get the OTLP metrics endpoint URL."""
        if self.protocol == "grpc":
            return self._get_grpc_endpoint()
        return f"{self.url}/api/{self.org}/v1/metrics"
