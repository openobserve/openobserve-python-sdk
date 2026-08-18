"""The result of a run, and the assertions CI makes about it.

Everything here is built from endpoints the platform already exposes. The
assertion surface adds no server-side concept: it reads the same comparison a
person would read in the UI and turns it into an exit code.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from .errors import RegressionError, ValidationError
from .http import HTTPClient

# Scoring states in which every applicable score has reached a terminal
# outcome. Only then can a comparison be trusted to be final.
TERMINAL_SCORING = ("completed", "completed_with_errors")

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0
DEFAULT_POLL_INTERVAL_SECONDS = 5.0


class ExperimentResult:
    """A finished (or still-running) experiment, and what can be asked of it."""

    def __init__(
        self,
        client: HTTPClient,
        experiment_id: str,
        *,
        rejections: Optional[List[Dict[str, Any]]] = None,
        not_applicable: Optional[Dict[str, int]] = None,
    ) -> None:
        self._client = client
        self.experiment_id = experiment_id
        self.rejections = rejections or []
        self.not_applicable = not_applicable or {}
        self._detail: Optional[Dict[str, Any]] = None

    @property
    def url(self) -> str:
        """Where a person can look at this run."""
        base = self._client.config.url
        org = self._client.config.org
        return f"{base}/web/{org}/experiments/{self.experiment_id}"

    def refresh(self) -> Dict[str, Any]:
        self._detail = self._client.get(f"/experiments/{self.experiment_id}")
        return self._detail

    @property
    def detail(self) -> Dict[str, Any]:
        if self._detail is None:
            self.refresh()
        return self._detail or {}

    @property
    def status(self) -> str:
        return str((self.detail.get("experiment") or {}).get("status", "unknown"))

    @property
    def scoring_status(self) -> str:
        """Derived state of every applicable score dimension.

        The server derives this rather than the SDK: it is defined over the
        score evidence, and a second implementation here could only drift from
        the one the UI shows.
        """
        results = self.detail.get("results") or {}
        return str(results.get("scoringStatus", "pending"))

    @property
    def summary(self) -> Dict[str, Any]:
        """Per-dimension aggregates, cost, and latency for this run."""
        results = self.detail.get("results") or {}
        aggregate = results.get("aggregateSummary") or {}
        return {
            "dimensions": results.get("scoreSummaries") or [],
            "cost": aggregate.get("totalCost"),
            "p50_latency_ms": aggregate.get("p50LatencyMs"),
            "incomplete": aggregate.get("incomplete", False),
            "incomplete_task_slots": aggregate.get("incompleteTaskSlots", 0),
            "incomplete_score_dimensions": aggregate.get("incompleteScoreDimensions", 0),
            "task_progress": results.get("taskProgress") or {},
            "scoring_progress": results.get("scoringProgress") or {},
        }

    def wait_for_scoring(
        self,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> str:
        """Block until scoring reaches a terminal state.

        Platform scoring is asynchronous, so a run that has finished executing
        has usually not finished being judged. Every final comparison needs this
        first, which is why the assertion below refuses to guess without it.
        """
        deadline = clock() + timeout
        while True:
            status = self.scoring_status
            if status in TERMINAL_SCORING:
                return status
            if clock() >= deadline:
                raise TimeoutError(
                    f"scoring for {self.experiment_id} was still {status!r} after {timeout:.0f}s"
                )
            sleep(poll_interval)
            self.refresh()

    def compare(self, baseline: str, *, threshold: float = 0.05) -> Dict[str, Any]:
        """Compare this run against a baseline experiment.

        The result stays partial until scoring is terminal; it is labelled as
        such rather than being withheld, because a partial comparison is still
        useful to look at — just not to conclude from.
        """
        comparison: Dict[str, Any] = self._client.get(
            "/experiments/compare",
            params={
                "baselineId": baseline,
                "candidateId": self.experiment_id,
                "threshold": threshold,
            },
        )
        comparison["partial"] = self.scoring_status not in TERMINAL_SCORING
        return comparison

    def assert_no_regression(
        self,
        baseline: str,
        *,
        dimensions: Optional[Sequence[str]] = None,
        threshold: float = 0.05,
        allow_inconclusive: bool = False,
        allow_scoring_errors: bool = False,
    ) -> Dict[str, Any]:
        """Fail the process if this run regressed against ``baseline``.

        Inconclusive cases fail by default. That default is the whole point of
        the check: a comparison that could not reach a verdict is not evidence
        of safety, and treating it as a pass is how a regression ships. Set
        ``allow_inconclusive`` when you have decided the risk is acceptable.
        """
        scoring = self.scoring_status
        if scoring not in TERMINAL_SCORING:
            raise ValidationError(
                f"scoring is {scoring!r}; call wait_for_scoring() before asserting on results"
            )
        if scoring == "completed_with_errors" and not allow_scoring_errors:
            raise RegressionError(
                f"{self.experiment_id}: scoring finished with errors; "
                "pass allow_scoring_errors=True to accept that"
            )

        comparison = self.compare(baseline, threshold=threshold)
        selected = _select_dimensions(comparison, dimensions)
        failures = [
            f"{name}: {_describe(entry)}"
            for name, entry in selected.items()
            if _is_regression(entry)
        ]
        inconclusive = [name for name, entry in selected.items() if _is_inconclusive(entry)]
        if inconclusive and not allow_inconclusive:
            failures.extend(f"{name}: inconclusive" for name in inconclusive)
        inconclusive_rows = int((comparison.get("counts") or {}).get("inconclusive", 0))
        if inconclusive_rows and not allow_inconclusive:
            failures.append(
                f"{inconclusive_rows} case(s) inconclusive; "
                "pass allow_inconclusive=True to accept that"
            )

        if failures:
            raise RegressionError(
                f"{self.experiment_id} regressed against {baseline}:\n  "
                + "\n  ".join(sorted(failures))
                + f"\n{self.url}"
            )
        return comparison


def _select_dimensions(
    comparison: Dict[str, Any],
    dimensions: Optional[Sequence[str]],
) -> Dict[str, Dict[str, Any]]:
    entries = comparison.get("dimensions") or []
    by_name = {str(entry.get("name", "")): entry for entry in entries}
    if dimensions is None:
        return by_name
    missing = [name for name in dimensions if name not in by_name]
    if missing:
        raise ValidationError(
            f"comparison has no dimension(s) {', '.join(sorted(missing))}; "
            f"available: {', '.join(sorted(by_name)) or 'none'}"
        )
    return {name: by_name[name] for name in dimensions}


def _is_regression(entry: Dict[str, Any]) -> bool:
    """Whether this dimension got worse in the direction it declared.

    Only a gating dimension can say so. A descriptive one has no comparison
    policy to orient its change, and there are no implicit defaults — numeric
    is not assumed higher-is-better, boolean is not assumed true-is-better.
    """
    return str(entry.get("assignment", "")) == "regressed"


def _is_inconclusive(entry: Dict[str, Any]) -> bool:
    """Whether the dimension could not reach a verdict it was expected to reach.

    ``unavailable`` on a gating dimension means the common cohort produced too
    little successful evidence to compare. A descriptive or one-sided dimension
    is not inconclusive — it was never going to decide anything.
    """
    return bool(entry.get("gating")) and str(entry.get("assignment", "")) == "unavailable"


def _describe(entry: Dict[str, Any]) -> str:
    baseline = entry.get("baseline")
    candidate = entry.get("candidate")
    delta = entry.get("delta")
    described = f"{baseline} -> {candidate}"
    if delta is not None:
        described += f" (delta {delta})"
    return described
