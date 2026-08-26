"""Minimal JSON-over-HTTP client for the evaluation APIs.

Built on :mod:`urllib` rather than ``requests`` so the evaluation surface adds
no runtime dependency to a package whose whole point is being cheap to install.

Retries live here because every caller wants the same policy: repeat what is
safe to repeat, never repeat a decision the server already made. A 409 is a
decision.
"""

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Optional

from ..config import OpenObserveConfig
from .errors import APIError, TransportError

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0


class HTTPClient:
    """Sends JSON requests to one organization's API."""

    def __init__(
        self,
        config: OpenObserveConfig,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        sleep: Any = time.sleep,
    ) -> None:
        self._config = config
        self._max_attempts = max(1, max_attempts)
        self._sleep = sleep

    @property
    def config(self) -> OpenObserveConfig:
        return self._config

    def base_url(self) -> str:
        return f"{self._config.url}/api/{self._config.org}"

    def get(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: Any, headers: Optional[Mapping[str, str]] = None) -> Any:
        return self.request("POST", path, body=body, headers=headers)

    def put(self, path: str, body: Any, headers: Optional[Mapping[str, str]] = None) -> Any:
        return self.request("PUT", path, body=body, headers=headers)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        url = f"{self.base_url()}{path}"
        if params:
            query = {key: _query_value(value) for key, value in params.items() if value is not None}
            if query:
                url = f"{url}?{urllib.parse.urlencode(query)}"

        payload = None if body is None else json.dumps(body).encode("utf-8")
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._config.auth_token:
            request_headers["Authorization"] = self._config.auth_token
        if self._config.additional_headers:
            request_headers.update(self._config.additional_headers)
        if headers:
            request_headers.update(headers)

        last_error: Optional[Exception] = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._send(method, url, payload, request_headers, path)
            except (APIError, TransportError) as error:
                last_error = error
                if not getattr(error, "is_retryable", False) or attempt == self._max_attempts:
                    raise
                self._sleep(_backoff_seconds(attempt))
        # Unreachable: the loop either returns or raises.
        raise last_error if last_error else TransportError("request failed")

    def _send(
        self,
        method: str,
        url: str,
        payload: Optional[bytes],
        headers: Mapping[str, str],
        path: str,
    ) -> Any:
        request = urllib.request.Request(url, data=payload, method=method)
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:  # noqa: PERF203 - needs the response body
            raw = ""
            try:
                raw = error.read().decode("utf-8")
            except Exception:  # pragma: no cover - body is best-effort detail
                pass
            parsed = _safe_json(raw)
            raise APIError(
                error.code,
                _error_message(parsed, raw),
                method=method,
                path=path,
                body=parsed if isinstance(parsed, dict) else None,
            ) from error
        except urllib.error.URLError as error:
            raise TransportError(
                f"{method} {path} could not reach the server: {error.reason}"
            ) from error
        except TimeoutError as error:
            raise TransportError(f"{method} {path} timed out") from error
        return _safe_json(raw)


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with jitter, so a fleet of workers does not
    synchronise its retries into a second thundering herd."""
    base = float(min(DEFAULT_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS))
    return base * (0.5 + random.random() / 2)


def _query_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _safe_json(raw: str) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"message": raw}


def _error_message(parsed: Any, raw: str) -> str:
    if isinstance(parsed, dict):
        for key in ("message", "error", "error_detail"):
            value = parsed.get(key)
            if isinstance(value, str) and value:
                return value
    return raw or "no response body"
