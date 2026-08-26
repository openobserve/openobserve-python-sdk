"""Batched reporting of execution records and self-reported scores.

The contract is per-part, not per-batch: a run streams results while it works,
so one malformed record must never discard the good ones beside it. The server
answers with a verdict per part; this module resends only what failed.

A part the server already accepted is safe to resend — the server recognises
its own stored evidence and writes nothing — which is what makes retrying a
partially-applied batch a non-event rather than a duplication risk.
"""

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .errors import APIError, TransportError

DEFAULT_FLUSH_SIZE = 50
DEFAULT_FLUSH_INTERVAL_SECONDS = 5.0
DEFAULT_MAX_RETRIES = 3


class BatchReport:
    """What one flush achieved, accumulated across the whole run."""

    def __init__(self) -> None:
        self.accepted_records = 0
        self.rejected_records = 0
        self.accepted_scores = 0
        self.rejected_scores = 0
        self.rejections: List[Dict[str, Any]] = []

    def absorb(self, response: Dict[str, Any], records: List[Any], scores: List[Any]) -> None:
        self.accepted_records += int(response.get("acceptedRecords", 0))
        self.rejected_records += int(response.get("rejectedRecords", 0))
        self.accepted_scores += int(response.get("acceptedScores", 0))
        self.rejected_scores += int(response.get("rejectedScores", 0))
        for part in response.get("records", []) or []:
            if not part.get("accepted"):
                self.rejections.append({"kind": "record", **_rejection(part)})
        for part in response.get("scores", []) or []:
            if not part.get("accepted"):
                self.rejections.append({"kind": "score", **_rejection(part)})

    @property
    def has_rejections(self) -> bool:
        return bool(self.rejections)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"BatchReport(records={self.accepted_records}/{self.accepted_records + self.rejected_records}, "
            f"scores={self.accepted_scores}/{self.accepted_scores + self.rejected_scores})"
        )


class RecordBatcher:
    """Buffers records and scores, flushing on size or age.

    Both thresholds matter for different reasons: size bounds the request, and
    age bounds how stale the progress a watcher sees can be. Whichever comes
    first wins.
    """

    def __init__(
        self,
        send: Callable[[List[Any], List[Any]], Dict[str, Any]],
        *,
        flush_size: int = DEFAULT_FLUSH_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._send = send
        self._flush_size = max(1, flush_size)
        self._flush_interval = max(0.0, flush_interval)
        self._max_retries = max(0, max_retries)
        self._now = now
        self._sleep = sleep
        self._lock = threading.Lock()
        self._records: List[Any] = []
        self._scores: List[Any] = []
        self._opened_at: Optional[float] = None
        self.report = BatchReport()

    def add_record(self, record: Any) -> None:
        with self._lock:
            self._records.append(record)
            self._mark_open()
            due = self._is_due_locked()
        if due:
            self.flush()

    def add_score(self, score: Any) -> None:
        with self._lock:
            self._scores.append(score)
            self._mark_open()
            due = self._is_due_locked()
        if due:
            self.flush()

    def maybe_flush(self) -> None:
        """Flush if the buffer has aged past the interval.

        Called from the run loop so a trickle of slow slots still reports
        progress instead of sitting in the buffer until the end.
        """
        with self._lock:
            due = self._is_due_locked()
        if due:
            self.flush()

    def flush(self) -> None:
        """Send everything buffered, retrying only the parts that failed."""
        with self._lock:
            records, scores = self._records, self._scores
            self._records, self._scores = [], []
            self._opened_at = None
        if not records and not scores:
            return
        self._send_with_retries(records, scores)

    def _send_with_retries(self, records: List[Any], scores: List[Any]) -> None:
        attempt = 0
        while True:
            try:
                response = self._send(records, scores) or {}
            except (APIError, TransportError) as error:
                # A conflict is the server's verdict, not a hiccup: resending
                # cannot change it, and retrying would only delay the failure.
                if not getattr(error, "is_retryable", False) or attempt >= self._max_retries:
                    raise
                attempt += 1
                self._sleep(_retry_delay(attempt))
                continue

            self.report.absorb(response, records, scores)
            records, scores = _failed_parts(response, records, scores)
            if not records and not scores:
                return
            if attempt >= self._max_retries:
                return
            attempt += 1
            self._sleep(_retry_delay(attempt))

    def _mark_open(self) -> None:
        if self._opened_at is None:
            self._opened_at = self._now()

    def _is_due_locked(self) -> bool:
        pending = len(self._records) + len(self._scores)
        if pending == 0:
            return False
        if pending >= self._flush_size:
            return True
        return (
            self._opened_at is not None and (self._now() - self._opened_at) >= self._flush_interval
        )


def _failed_parts(
    response: Dict[str, Any],
    records: List[Any],
    scores: List[Any],
) -> Tuple[List[Any], List[Any]]:
    """Select the parts worth sending again.

    Only parts the server could not durably decide are retried. A rejection it
    can restate identically — an unknown slot, a fingerprint mismatch, an
    invalid score value — is final, and resending it forever would turn a
    reporting bug into a hang.
    """
    return (
        [records[index] for index in _retryable_indexes(response.get("records"), len(records))],
        [scores[index] for index in _retryable_indexes(response.get("scores"), len(scores))],
    )


# Part-level codes that describe the submission itself. Repeating the same
# bytes produces the same verdict, so these never retry.
_FINAL_CODES = frozenset(
    {
        "unknown_slot",
        "fingerprint_mismatch",
        "missing_output",
        "duplicate_slot_in_batch",
        "experiment_sealed",
        # The Slot already holds a terminal record. Resending the same bytes
        # would be a duplicate and resending different ones is refused again,
        # so a retry can only add traffic and repeat the rejection.
        "slot_immutable",
        "missing_client_scorer_key",
        "unknown_score_config",
        "invalid_score_value",
        "no_execution_record",
    }
)


def _retryable_indexes(parts: Any, total: int) -> List[int]:
    if not parts:
        return []
    indexes = []
    for part in parts:
        if part.get("accepted"):
            continue
        code = (part.get("error") or {}).get("code", "")
        if code in _FINAL_CODES:
            continue
        index = int(part.get("index", -1))
        if 0 <= index < total:
            indexes.append(index)
    return indexes


def _rejection(part: Dict[str, Any]) -> Dict[str, Any]:
    error = part.get("error") or {}
    return {
        "row_id": part.get("rowId"),
        "trial_index": part.get("trialIndex"),
        "code": error.get("code", "unknown"),
        "message": error.get("message", ""),
    }


def _retry_delay(attempt: int) -> float:
    return float(min(1.0 * (2 ** (attempt - 1)), 30.0))
