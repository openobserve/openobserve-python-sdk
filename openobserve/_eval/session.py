"""How the evaluation surface finds its credentials.

It reuses the same environment variables and the same
:class:`~openobserve.config.OpenObserveConfig` as telemetry export, so a
process that already exports traces needs no second configuration to run an
experiment.
"""

from typing import Optional

from ..config import OpenObserveConfig
from .errors import ConfigurationError
from .http import HTTPClient

_CLIENT: Optional[HTTPClient] = None


def configure(config: Optional[OpenObserveConfig] = None, **overrides: object) -> HTTPClient:
    """Set the client every evaluation call uses by default."""
    global _CLIENT
    resolved = config or OpenObserveConfig.from_env(**overrides)
    _CLIENT = HTTPClient(resolved)
    return _CLIENT


def client_for() -> HTTPClient:
    """The configured client, built from the environment on first use."""
    global _CLIENT
    if _CLIENT is None:
        try:
            _CLIENT = HTTPClient(OpenObserveConfig.from_env())
        except ValueError as error:
            raise ConfigurationError(
                f"{error}. Set OPENOBSERVE_URL, OPENOBSERVE_ORG, and OPENOBSERVE_AUTH_TOKEN, "
                "or call openobserve.experiment.configure(...)."
            ) from error
    return _CLIENT


def reset() -> None:
    """Drop the cached client. Intended for tests."""
    global _CLIENT
    _CLIENT = None
