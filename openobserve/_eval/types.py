"""The values a customer's task and scorers exchange with the SDK."""

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

JSONValue = Any


class Skip(Exception):
    """Raised by a task to decline a slot.

    A skip is a decision, not a failure: it produces a terminal ``skipped``
    record and never counts against the run. Use it when the task legitimately
    has nothing to produce for a case, and let real errors propagate.
    """

    def __init__(self, reason: str = "") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Usage:
    """Token and cost accounting for one task call."""

    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost: Optional[float] = None

    def is_empty(self) -> bool:
        return self.tokens_in is None and self.tokens_out is None and self.cost is None


@dataclass(frozen=True)
class TaskResult:
    """A task's output plus anything the SDK could not infer for itself.

    Returning a bare JSON value is the common case. Reach for this when the
    task knows something the surrounding span does not — usage the SDK cannot
    see, or metadata worth keeping beside the output.
    """

    output: JSONValue
    metadata: Optional[Dict[str, Any]] = None
    usage: Optional[Usage] = None


@dataclass(frozen=True)
class TaskContext:
    """Everything a task is told about the slot it is answering.

    ``row_id`` and ``trial_index`` together identify the slot; ``metadata`` is
    whatever the dataset case carries. A task that behaves differently across
    trials of the same case can branch on ``trial_index``.
    """

    row_id: str
    logical_id: str
    trial_index: int
    metadata: Mapping[str, Any] = field(default_factory=dict)
    expected_output: JSONValue = None
    experiment_id: str = ""


@dataclass(frozen=True)
class SlotRef:
    """One unit of work: a pinned dataset case at one trial position."""

    row_id: str
    logical_id: str
    trial_index: int
    input: JSONValue
    expected_output: JSONValue = None
    metadata: Optional[Dict[str, Any]] = None
    # A slot carries no reference when the dataset case has no expected output.
    # Reference-based dimensions skip it rather than scoring it wrongly.
    has_reference: bool = False

    @classmethod
    def from_api(cls, payload: Mapping[str, Any]) -> "SlotRef":
        return cls(
            row_id=str(payload["rowId"]),
            logical_id=str(payload.get("logicalId", "")),
            trial_index=int(payload.get("trialIndex", 0)),
            input=payload.get("input"),
            expected_output=payload.get("expectedOutput"),
            metadata=payload.get("metadata") or {},
            has_reference="expectedOutput" in payload and payload.get("expectedOutput") is not None,
        )

    def context(self, experiment_id: str) -> TaskContext:
        return TaskContext(
            row_id=self.row_id,
            logical_id=self.logical_id,
            trial_index=self.trial_index,
            metadata=self.metadata or {},
            expected_output=self.expected_output,
            experiment_id=experiment_id,
        )
