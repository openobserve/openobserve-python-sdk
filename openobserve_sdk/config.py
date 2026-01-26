"""
OpenObserve SDK Configuration Module

This module handles configuration management for the OpenObserve SDK,
including environment variables and default values.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict


# Environment variable names
ENV_OPENOBSERVE_URL = "OPENOBSERVE_URL"
ENV_OPENOBSERVE_ORG = "OPENOBSERVE_ORG"
ENV_OPENOBSERVE_AUTH_TOKEN = "OPENOBSERVE_AUTH_TOKEN"
ENV_OPENOBSERVE_TIMEOUT = "OPENOBSERVE_TIMEOUT"
ENV_OPENOBSERVE_ENABLED = "OPENOBSERVE_ENABLED"


@dataclass
class OpenObserveConfig:
    """
    Configuration for OpenObserve SDK.

    Attributes:
        url: OpenObserve base URL (e.g., "https://api.openobserve.ai" or "http://localhost:5080")
        org: OpenObserve organization name
        auth_token: Authorization token (e.g., "Basic <base64-encoded-credentials>")
        timeout: Request timeout in seconds (default: 30)
        enabled: Enable/disable tracing (default: True)
        additional_headers: Additional HTTP headers to send with requests
        resource_attributes: Additional resource attributes for the service
    """

    url: str
    org: str
    auth_token: str
    timeout: int = 30
    enabled: bool = True
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
        url = overrides.get("url") or os.getenv(ENV_OPENOBSERVE_URL)
        org = overrides.get("org") or os.getenv(ENV_OPENOBSERVE_ORG, "default")
        auth_token = overrides.get("auth_token") or os.getenv(ENV_OPENOBSERVE_AUTH_TOKEN)

        # Parse timeout from env (default to 30)
        timeout_str = os.getenv(ENV_OPENOBSERVE_TIMEOUT, "30")
        timeout = overrides.get("timeout", int(timeout_str))

        # Parse enabled flag from env (default to True)
        enabled_str = os.getenv(ENV_OPENOBSERVE_ENABLED, "true").lower()
        enabled = overrides.get("enabled", enabled_str in ("true", "1", "yes"))

        return cls(
            url=url,
            org=org,
            auth_token=auth_token,
            timeout=timeout,
            enabled=enabled,
            additional_headers=overrides.get("additional_headers"),
            resource_attributes=overrides.get("resource_attributes"),
        )

    def get_otlp_endpoint(self) -> str:
        """
        Get the OTLP traces endpoint URL.

        Returns:
            Full OTLP endpoint URL
        """
        return f"{self.url}/api/{self.org}/v1/traces"
