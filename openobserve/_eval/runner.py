"""Executes a customer's task across an experiment's slots.

Everything here exists to keep one promise: the run reports what actually
happened. A task that raises is retried locally and then recorded as an error
rather than being dropped; a task that declines is recorded as a skip rather
than an error; and the run keeps going either way, because a conclusion drawn
from a partial cohort is worse than a conclusion that says which slots failed.
"""

import concurrent.futures
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..scorer import LocalScorer
from .types import Skip, SlotRef, TaskResult, Usage

DEFAULT_TASK_ATTEMPTS = 3
DEFAULT_TASK_BACKOFF_SECONDS = 1.0


class SlotOutcome:
    """One slot's result, in the shape the report transport expects."""

    def __init__(
        self,
        record: Dict[str, Any],
        scores: List[Dict[str, Any]],
        *,
        not_applicable: Optional[Dict[str, int]] = None,
    ) -> None:
        self.record = record
        self.scores = scores
        self.not_applicable = not_applicable or {}


class TaskRunner:
    """Runs one task function over slots, with local scoring."""

    def __init__(
        self,
        task_fn: Callable[..., Any],
        *,
        task_fingerprint: str,
        local_scorers: Sequence[LocalScorer],
        experiment_id: str,
        tracer: Any = None,
        attempts: int = DEFAULT_TASK_ATTEMPTS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._task_fn = task_fn
        self._fingerprint = task_fingerprint
        self._local_scorers = list(local_scorers)
        self._experiment_id = experiment_id
        self._tracer = tracer
        self._attempts = max(1, attempts)
        self._sleep = sleep
        self._clock = clock

    def run_slot(self, slot: SlotRef) -> SlotOutcome:
        """Execute one slot and turn whatever happened into evidence."""
        context = slot.context(self._experiment_id)
        started = self._clock()
        span_context = self._start_span(slot)
        trace_id: Optional[str] = None
        try:
            with span_context as span:
                trace_id = _trace_id_of(span)
                outcome = self._attempt_task(slot, context)
        finally:
            latency_ms = int((self._clock() - started) * 1000)

        if isinstance(outcome, _Skipped):
            return SlotOutcome(
                self._record(
                    slot,
                    status="skipped",
                    latency_ms=latency_ms,
                    trace_id=trace_id,
                    skip_message=outcome.reason or None,
                ),
                [],
            )
        if isinstance(outcome, _Failed):
            return SlotOutcome(
                self._record(
                    slot,
                    status="error",
                    latency_ms=latency_ms,
                    trace_id=trace_id,
                    error_message=outcome.message,
                    error_attempt_count=outcome.attempts,
                ),
                [],
            )

        result = outcome.result
        usage = result.usage or _usage_from_span(span_context)
        record = self._record(
            slot,
            status="ok",
            latency_ms=latency_ms,
            trace_id=trace_id,
            output=result.output,
            usage=usage,
        )
        scores, not_applicable = self._score(slot, result.output)
        return SlotOutcome(record, scores, not_applicable=not_applicable)

    def _attempt_task(self, slot: SlotRef, context: Any) -> Any:
        last_error: Optional[BaseException] = None
        for attempt in range(1, self._attempts + 1):
            try:
                # Normalising inside the try means a task that returns
                # something unusable fails the same way one that raises does,
                # instead of escaping the run loop and losing every later slot.
                result = _as_task_result(self._task_fn(slot.input, context))
            except Skip as skip:
                # A decline is a decision, not a failure: never retried.
                return _Skipped(skip.reason)
            except Exception as error:  # noqa: BLE001 - the task owns its failures
                last_error = error
                if attempt < self._attempts:
                    self._sleep(DEFAULT_TASK_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                continue
            return _Succeeded(result)
        return _Failed(f"{type(last_error).__name__}: {last_error}", self._attempts)

    def _score(self, slot: SlotRef, output: Any) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        scores: List[Dict[str, Any]] = []
        not_applicable: Dict[str, int] = {}
        for local in self._local_scorers:
            if not local.applies_to(slot.has_reference):
                # Counted rather than silently omitted: a dimension that could
                # not judge a case is a fact about the run's coverage.
                not_applicable[local.key] = not_applicable.get(local.key, 0) + 1
                continue
            try:
                value = local.invoke(
                    output=output,
                    expected_output=slot.expected_output,
                    input=slot.input,
                    metadata=dict(slot.metadata or {}),
                    context=slot.context(self._experiment_id),
                )
            except Exception as error:  # noqa: BLE001 - a scorer bug must not lose the record
                not_applicable[local.key] = not_applicable.get(local.key, 0) + 1
                _warn(f"local scorer {local.key!r} raised on row {slot.row_id}: {error}")
                continue
            if value is None:
                continue
            scores.append(
                {
                    "rowId": slot.row_id,
                    "trialIndex": slot.trial_index,
                    "clientScorerKey": local.key,
                    "scoreConfig": local.config,
                    "value": value,
                }
            )
        return scores, not_applicable

    def _record(
        self,
        slot: SlotRef,
        *,
        status: str,
        latency_ms: int,
        trace_id: Optional[str],
        output: Any = None,
        usage: Optional[Usage] = None,
        error_message: Optional[str] = None,
        error_attempt_count: Optional[int] = None,
        skip_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "rowId": slot.row_id,
            "trialIndex": slot.trial_index,
            "status": status,
            "taskFingerprint": self._fingerprint,
            "latencyMs": latency_ms,
            "executedAt": int(time.time() * 1000),
        }
        if status == "ok":
            record["output"] = output
        if trace_id:
            record["traceId"] = trace_id
        if usage and not usage.is_empty():
            if usage.tokens_in is not None:
                record["tokensIn"] = usage.tokens_in
            if usage.tokens_out is not None:
                record["tokensOut"] = usage.tokens_out
            if usage.cost is not None:
                record["cost"] = usage.cost
        if error_message:
            record["errorMessage"] = error_message
        if error_attempt_count:
            record["errorAttemptCount"] = error_attempt_count
        if skip_message:
            record["skipMessage"] = skip_message
        return record

    def _start_span(self, slot: SlotRef) -> Any:
        if self._tracer is None:
            return _NullSpan()
        return _SpanScope(
            self._tracer,
            "openobserve.experiment.task",
            {
                "openobserve.experiment.id": self._experiment_id,
                "openobserve.experiment.row_id": slot.row_id,
                "openobserve.experiment.trial_index": slot.trial_index,
            },
        )


class _Succeeded:
    def __init__(self, result: TaskResult) -> None:
        self.result = result


class _Skipped:
    def __init__(self, reason: str) -> None:
        self.reason = reason


class _Failed:
    def __init__(self, message: str, attempts: int) -> None:
        self.message = message
        self.attempts = attempts


class _NullSpan:
    """Stands in when no tracer is configured, so the run loop has no branch."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: Any) -> None:
        return None


class _SpanScope:
    """Wraps a task call in a span so latency and trace id come for free."""

    def __init__(self, tracer: Any, name: str, attributes: Dict[str, Any]) -> None:
        self._tracer = tracer
        self._name = name
        self._attributes = attributes
        self._cm: Any = None
        self.span: Any = None

    def __enter__(self) -> Any:
        self._cm = self._tracer.start_as_current_span(self._name, attributes=self._attributes)
        self.span = self._cm.__enter__()
        return self.span

    def __exit__(self, *exc: Any) -> None:
        if self._cm is not None:
            self._cm.__exit__(*exc)


def _trace_id_of(span: Any) -> Optional[str]:
    """Read the trace id so records join up with the spans the task emitted."""
    if span is None:
        return None
    try:
        context = span.get_span_context()
    except Exception:  # pragma: no cover - defensive against exotic span impls
        return None
    trace_id = getattr(context, "trace_id", 0)
    if not trace_id:
        return None
    return format(trace_id, "032x")


def _usage_from_span(span_context: Any) -> Optional[Usage]:
    """Usage the SDK could observe on its own.

    Instrumented client libraries record tokens on their own spans; when
    nothing did, the run reports no usage rather than guessing at zero, because
    zero and unknown mean different things to a cost summary.
    """
    span = getattr(span_context, "span", None)
    if span is None:
        return None
    attributes = getattr(span, "attributes", None) or {}
    tokens_in = attributes.get("gen_ai.usage.input_tokens")
    tokens_out = attributes.get("gen_ai.usage.output_tokens")
    cost = attributes.get("gen_ai.usage.cost")
    usage = Usage(
        tokens_in=int(tokens_in) if tokens_in is not None else None,
        tokens_out=int(tokens_out) if tokens_out is not None else None,
        cost=float(cost) if cost is not None else None,
    )
    return None if usage.is_empty() else usage


def _as_task_result(value: Any) -> TaskResult:
    if isinstance(value, TaskResult):
        return value
    if value is None:
        # `None` is the one JSON value an ok record may not carry: it is
        # indistinguishable from "the task returned nothing by accident".
        raise ValueError(
            "task returned None; return a JSON value, a TaskResult, or raise Skip(...)"
        )
    return TaskResult(output=value)


def run_slots(
    runner: TaskRunner,
    slots: Sequence[SlotRef],
    *,
    max_concurrency: int,
    on_outcome: Callable[[SlotOutcome], None],
) -> None:
    """Run every slot, handing each outcome to ``on_outcome`` as it lands."""
    if max_concurrency <= 1:
        for slot in slots:
            on_outcome(runner.run_slot(slot))
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as pool:
        for outcome in pool.map(runner.run_slot, slots):
            on_outcome(outcome)


def _warn(message: str) -> None:
    logging.getLogger("openobserve.experiment").warning(message)
