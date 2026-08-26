"""Retry policy: what the client repeats, and what it refuses to."""

import pytest

from openobserve._eval.errors import APIError, TransportError
from openobserve._eval.http import HTTPClient
from openobserve.config import OpenObserveConfig


def config():
    return OpenObserveConfig(url="http://localhost:5080/", org="acme", auth_token="Basic dGVzdA==")


def client(responses, max_attempts=3):
    http = HTTPClient(config(), max_attempts=max_attempts, sleep=lambda _: None)
    calls = []

    def send(method, url, payload, headers, path):
        calls.append({"method": method, "url": url, "headers": dict(headers)})
        outcome = responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    http._send = send  # noqa: SLF001 - the seam under test
    http.calls = calls
    return http


def test_the_base_url_is_scoped_to_the_configured_organization():
    assert HTTPClient(config()).base_url() == "http://localhost:5080/api/acme"


def test_query_parameters_are_encoded_and_booleans_become_words():
    http = client([{}])
    http.get("/datasets/ds-1/items", params={"from": 0, "size": 100, "includeDeleted": True})

    assert http.calls[0]["url"].endswith("?from=0&size=100&includeDeleted=true")


def test_none_valued_parameters_are_omitted_rather_than_sent_as_null():
    http = client([{}])
    http.get("/datasets", params={"size": None})

    assert "?" not in http.calls[0]["url"]


def test_the_auth_token_travels_on_every_request():
    http = client([{}])
    http.get("/datasets")

    assert http.calls[0]["headers"]["Authorization"] == "Basic dGVzdA=="


def test_a_server_error_is_retried():
    http = client([APIError(503, "unavailable"), APIError(503, "unavailable"), {"ok": True}])

    assert http.get("/datasets") == {"ok": True}
    assert len(http.calls) == 3


def test_a_conflict_is_never_retried():
    http = client([APIError(409, "sealed")])

    with pytest.raises(APIError) as raised:
        http.post("/experiments/exp-1/records", {})

    assert raised.value.is_conflict
    assert len(http.calls) == 1


def test_a_bad_request_is_never_retried():
    http = client([APIError(400, "malformed")])

    with pytest.raises(APIError):
        http.post("/experiments", {})
    assert len(http.calls) == 1


def test_rate_limiting_is_retried():
    http = client([APIError(429, "slow down"), {"ok": True}])

    assert http.get("/datasets") == {"ok": True}


def test_an_unreachable_server_is_retried_then_surfaces():
    http = client([TransportError("refused")] * 3)

    with pytest.raises(TransportError):
        http.get("/datasets")
    assert len(http.calls) == 3
