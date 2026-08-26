"""Prepare the exam paper before taking the exam.

Local data has to become a dataset before an experiment can reference it.
There is deliberately no way to hand data straight to a run: a dataset is the
thing two experiments have in common, and a run that invented its own would be
comparable to nothing.
"""

import uuid
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ._eval.errors import ValidationError
from ._eval.http import HTTPClient
from ._eval.session import client_for

# The server accepts at most this many cases per request.
MAX_ITEMS_PER_REQUEST = 1000


def upsert(
    dataset: str,
    items: Sequence[Mapping[str, Any]],
    *,
    idempotency_key: Optional[str] = None,
    client: Optional[HTTPClient] = None,
) -> Dict[str, Any]:
    """Create or update dataset cases under identity you control.

    ``dataset`` is a dataset name. Each item may carry:

    ``logical_id``
        The case's stable identity. Omit it to append a new case and let the
        server generate one; supply it to address a specific case across runs.
    ``if_row_id``
        The revision you read. Required whenever ``logical_id`` names a case
        that already exists — it is how the server tells your update apart from
        one that raced you.
    ``restore``
        Bring a deleted case back rather than conflicting on it.

    A batch is all-or-nothing: either every case lands or none does, so a
    failed call never leaves half a dataset behind.
    """
    http = client or client_for()
    items = list(items)
    if not items:
        raise ValidationError("upsert requires at least one item")
    if len(items) > MAX_ITEMS_PER_REQUEST:
        raise ValidationError(
            f"upsert accepts at most {MAX_ITEMS_PER_REQUEST} items per call; "
            f"got {len(items)} — send them in batches"
        )

    dataset_id = resolve(dataset, client=http)["id"]
    body: Dict[str, Any] = {
        "idempotencyKey": idempotency_key or uuid.uuid4().hex,
        "items": [_item_body(item) for item in items],
    }
    response: Dict[str, Any] = http.put(f"/datasets/{dataset_id}/items", body)
    return response


def resolve(reference: str, *, client: Optional[HTTPClient] = None) -> Dict[str, Any]:
    """Resolve ``name`` or ``name@version`` to a dataset and a pinned version.

    A bare name pins whatever the dataset's current version is at resolution
    time, so a run always evaluates a fixed snapshot even if the dataset moves
    underneath it.
    """
    http = client or client_for()
    name, version = parse_reference(reference)
    for dataset in list_all(client=http):
        if dataset.get("name") == name:
            pinned = version if version is not None else dataset.get("globalVersion", 0)
            return {
                "id": dataset["id"],
                "name": name,
                "version": int(pinned),
                "currentVersion": int(dataset.get("globalVersion", 0)),
            }
    raise ValidationError(
        f"dataset {name!r} was not found; create it, or run datasets.upsert() first"
    )


def parse_reference(reference: str) -> Tuple[str, Optional[int]]:
    """Split ``name`` or ``name@version``."""
    text = (reference or "").strip()
    if not text:
        raise ValidationError("dataset reference cannot be empty")
    if "@" not in text:
        return text, None
    name, _, version = text.rpartition("@")
    if not name:
        raise ValidationError(f"dataset reference {reference!r} is missing a name")
    version = version.lstrip("v")
    try:
        return name, int(version)
    except ValueError as error:
        raise ValidationError(
            f"dataset reference {reference!r} has a non-numeric version"
        ) from error


def list_all(*, client: Optional[HTTPClient] = None) -> List[Dict[str, Any]]:
    """Every dataset visible to the configured credentials."""
    http = client or client_for()
    response = http.get("/datasets")
    return list(response.get("list", []))


def items(
    dataset: str,
    *,
    include_deleted: bool = False,
    client: Optional[HTTPClient] = None,
) -> Iterable[Dict[str, Any]]:
    """Page through a dataset's current cases."""
    http = client or client_for()
    dataset_id = resolve(dataset, client=http)["id"]
    offset = 0
    while True:
        page = http.get(
            f"/datasets/{dataset_id}/items",
            params={"from": offset, "size": 100, "includeDeleted": include_deleted},
        )
        batch = page.get("list", [])
        yield from batch
        if not page.get("hasMore") or not batch:
            return
        offset += len(batch)


def _item_body(item: Mapping[str, Any]) -> Dict[str, Any]:
    if "input" not in item:
        raise ValidationError(f"dataset item {item!r} is missing 'input'")
    body: Dict[str, Any] = {"input": item["input"]}
    if item.get("logical_id") is not None:
        body["logicalId"] = item["logical_id"]
    if item.get("expected_output") is not None:
        body["expectedOutput"] = item["expected_output"]
    if item.get("metadata") is not None:
        body["metadata"] = item["metadata"]
    if item.get("tags"):
        body["tags"] = list(item["tags"])
    if item.get("if_row_id") is not None:
        body["ifRowId"] = item["if_row_id"]
    if item.get("restore"):
        body["restore"] = True
    return body


__all__ = ["items", "list_all", "parse_reference", "resolve", "upsert"]
