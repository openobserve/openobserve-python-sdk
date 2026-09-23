"""Declare the score configs a run depends on.

``ensure`` is safe to call on every run. Identical parameters change nothing,
which matters because experiments pin the exact version they scored against —
churning versions on every CI run would fragment a dimension's history for no
reason.
"""

from typing import Any, Dict, Optional, Sequence

from ._eval.errors import ValidationError
from ._eval.http import HTTPClient
from ._eval.session import client_for

DATA_TYPES = ("numeric", "categorical", "boolean")


def ensure(
    name: str,
    *,
    type: str = "numeric",
    min: Optional[float] = None,
    max: Optional[float] = None,
    categories: Optional[Sequence[str]] = None,
    description: Optional[str] = None,
    healthy_threshold: Optional[Dict[str, Any]] = None,
    client: Optional[HTTPClient] = None,
) -> Dict[str, Any]:
    """Declare that a score config with these parameters exists.

    Creates it when absent, does nothing when every parameter already matches,
    and appends a new version when the range, categories, or health policy
    differ. Changing ``type`` is refused: a dimension that changes what it
    measures is a different dimension, and needs a different name.

    ``healthy_threshold`` is what makes a dimension able to decide a verdict.
    Without one the dimension stays descriptive — visible in results, but
    unable to mark a regression or fail an assertion.
    """
    http = client or client_for()
    name = (name or "").strip()
    if not name:
        raise ValidationError("score config name cannot be empty")
    if type not in DATA_TYPES:
        raise ValidationError(f"score config type must be one of {', '.join(DATA_TYPES)}")

    body: Dict[str, Any] = {"name": name, "dataType": type}
    if description is not None:
        body["description"] = description
    if min is not None or max is not None:
        body["numericRange"] = {"min": min, "max": max}
    if categories is not None:
        body["categories"] = list(categories)
    if healthy_threshold is not None:
        body["healthyThreshold"] = healthy_threshold
    response: Dict[str, Any] = http.put("/score_configs", body)
    return response


def list_all(*, client: Optional[HTTPClient] = None) -> list:
    """Every score config visible to the configured credentials."""
    http = client or client_for()
    return list((http.get("/score_configs") or {}).get("list", []))


def resolve(name: str, *, client: Optional[HTTPClient] = None) -> Optional[Dict[str, Any]]:
    """Find one score config by name, or ``None``."""
    for config in list_all(client=client):
        if config.get("name") == name:
            return dict(config)
    return None


__all__ = ["DATA_TYPES", "ensure", "list_all", "resolve"]
