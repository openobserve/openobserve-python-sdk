"""Errors the evaluation surface raises.

The split is deliberate: a caller almost always wants to handle "the server
refused this because of a conflict I can resolve" differently from "the server
is unreachable", and neither is the same as "you configured this wrong".
"""

from typing import Any, Dict, Optional


class OpenObserveEvalError(Exception):
    """Base class for every error the evaluation surface raises."""


class ConfigurationError(OpenObserveEvalError):
    """The SDK was not given enough, or was given contradictory, configuration."""


class ValidationError(OpenObserveEvalError):
    """A run was described in a way that cannot be executed.

    Raised before any work starts — a missing dataset, an unknown scorer, a
    local scorer with no score config bound to it.
    """


class APIError(OpenObserveEvalError):
    """The server returned a non-success status."""

    def __init__(
        self,
        status: int,
        message: str,
        *,
        method: str = "",
        path: str = "",
        body: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(f"{method} {path} failed with {status}: {message}".strip())
        self.status = status
        self.message = message
        self.method = method
        self.path = path
        self.body = body or {}

    @property
    def is_conflict(self) -> bool:
        """A 409: the request collided with durable state.

        Sealed evidence, a stale dataset revision, and an idempotency key reused
        with different content all land here.
        """
        return self.status == 409

    @property
    def is_retryable(self) -> bool:
        """Whether repeating the identical request could plausibly succeed.

        A conflict never is: the server already decided, and resending cannot
        change its mind. Nor is any other 4xx, which describes the request
        itself.
        """
        if self.status == 429:
            return True
        return self.status >= 500


class TransportError(OpenObserveEvalError):
    """The request never produced a response — DNS, connection, or timeout."""

    @property
    def is_retryable(self) -> bool:
        return True


class RegressionError(AssertionError, OpenObserveEvalError):
    """A CI assertion failed.

    Inherits :class:`AssertionError` so an unhandled one exits non-zero and
    reads naturally in a test runner.
    """
