"""The CI assertion surface: what passes, what fails, and what refuses to guess."""

import pytest

from openobserve._eval.errors import RegressionError, ValidationError
from openobserve._eval.results import ExperimentResult
from openobserve.config import OpenObserveConfig


class FakeClient:
    def __init__(self, detail, comparison=None):
        self.config = OpenObserveConfig(
            url="http://localhost:5080", org="acme", auth_token="Basic dGVzdA=="
        )
        self._detail = detail
        self._comparison = comparison or {"dimensions": []}
        self.detail_reads = 0

    def get(self, path, params=None):
        if path.endswith("/compare"):
            return dict(self._comparison)
        self.detail_reads += 1
        if callable(self._detail):
            return self._detail(self.detail_reads)
        return self._detail


def detail(scoring="completed", status="completed"):
    return {
        "experiment": {"id": "exp-1", "status": status},
        "results": {
            "scoringStatus": scoring,
            "scoreSummaries": [{"scorerId": "answer_correctness", "sampleCount": 10}],
            "aggregateSummary": {
                "totalCost": 1.25,
                "p50LatencyMs": 240,
                "incomplete": False,
                "incompleteTaskSlots": 0,
                "incompleteScoreDimensions": 0,
            },
            "taskProgress": {"completed": 10, "total": 10, "skipped": 0},
            "scoringProgress": {"completed": 10, "total": 10, "skipped": 0},
        },
    }


def comparison(*dimensions, inconclusive_rows=0):
    return {
        "dimensions": list(dimensions),
        "counts": {"inconclusive": inconclusive_rows},
    }


def dimension(name, assignment, delta=0.0, gating=True):
    return {
        "name": name,
        "assignment": assignment,
        "gating": gating,
        "delta": delta,
        "baseline": 0.9,
        "candidate": 0.9 + delta,
    }


def result(detail_payload, comparison_payload=None):
    return ExperimentResult(FakeClient(detail_payload, comparison_payload), "exp-1")


def test_summary_exposes_per_dimension_aggregates_cost_and_latency():
    summary = result(detail()).summary

    assert summary["dimensions"][0]["scorerId"] == "answer_correctness"
    assert summary["cost"] == 1.25
    assert summary["p50_latency_ms"] == 240
    assert summary["incomplete"] is False


def test_url_points_at_the_run():
    assert result(detail()).url.endswith("/acme/experiments/exp-1")


def test_a_comparison_is_labelled_partial_until_scoring_is_terminal():
    running = result(detail(scoring="running"), comparison(dimension("d", "unchanged")))
    assert running.compare("exp-0")["partial"] is True

    done = result(detail(scoring="completed"), comparison(dimension("d", "unchanged")))
    assert done.compare("exp-0")["partial"] is False


def test_wait_for_scoring_blocks_until_a_terminal_state():
    states = ["pending", "running", "completed"]

    def detail_at(read):
        return detail(scoring=states[min(read - 1, len(states) - 1)])

    outcome = result(detail_at).wait_for_scoring(sleep=lambda _: None, poll_interval=0)
    assert outcome == "completed"


def test_wait_for_scoring_gives_up_rather_than_hanging_forever():
    clock = iter([0.0, 0.0, 100.0, 100.0]).__next__
    with pytest.raises(TimeoutError, match="still 'running'"):
        result(detail(scoring="running")).wait_for_scoring(
            timeout=10, sleep=lambda _: None, clock=clock
        )


def test_an_assertion_refuses_to_run_before_scoring_is_terminal():
    with pytest.raises(ValidationError, match="wait_for_scoring"):
        result(detail(scoring="running")).assert_no_regression("exp-0")


def test_an_unchanged_run_passes():
    outcome = result(
        detail(), comparison(dimension("answer_correctness", "unchanged"))
    ).assert_no_regression("exp-0")
    assert outcome["partial"] is False


def test_a_regressed_dimension_fails_and_names_itself():
    with pytest.raises(RegressionError, match="answer_correctness"):
        result(
            detail(), comparison(dimension("answer_correctness", "regressed", -0.2))
        ).assert_no_regression("exp-0")


def test_an_inconclusive_case_fails_by_default():
    # A comparison that could not reach a verdict is not evidence of safety.
    with pytest.raises(RegressionError, match="inconclusive"):
        result(
            detail(), comparison(dimension("answer_correctness", "unavailable"))
        ).assert_no_regression("exp-0")


def test_inconclusive_can_be_accepted_explicitly():
    outcome = result(
        detail(), comparison(dimension("answer_correctness", "unavailable"))
    ).assert_no_regression("exp-0", allow_inconclusive=True)
    assert outcome["dimensions"][0]["assignment"] == "unavailable"


def test_scoring_errors_fail_by_default_and_can_be_accepted_explicitly():
    with pytest.raises(RegressionError, match="scoring finished with errors"):
        result(detail(scoring="completed_with_errors")).assert_no_regression("exp-0")

    outcome = result(
        detail(scoring="completed_with_errors"),
        comparison(dimension("answer_correctness", "unchanged")),
    ).assert_no_regression("exp-0", allow_scoring_errors=True)
    assert outcome["partial"] is False


def test_selecting_dimensions_ignores_the_ones_not_asked_about():
    outcome = result(
        detail(),
        comparison(
            dimension("answer_correctness", "unchanged"),
            dimension("tone", "regressed", -0.3),
        ),
    ).assert_no_regression("exp-0", dimensions=["answer_correctness"])
    assert list(outcome["dimensions"])


def test_asking_about_a_dimension_that_is_not_there_is_an_error_not_a_pass():
    # Silently passing because a dimension vanished is how a broken gate looks
    # exactly like a working one.
    with pytest.raises(ValidationError, match="no dimension"):
        result(
            detail(), comparison(dimension("answer_correctness", "unchanged"))
        ).assert_no_regression("exp-0", dimensions=["tone"])


def test_a_descriptive_dimension_cannot_fail_an_assertion():
    # Without a declared comparison policy a dimension is visible but not
    # directional, so a large change is reported and decides nothing.
    outcome = result(
        detail(),
        comparison(dimension("length", "descriptive", delta=30.0, gating=False)),
    ).assert_no_regression("exp-0")
    assert outcome["dimensions"][0]["name"] == "length"


def test_a_non_gating_dimension_with_no_verdict_is_not_inconclusive():
    # It was never going to decide anything, so it cannot be the reason a gate
    # fails.
    outcome = result(
        detail(),
        comparison(dimension("length", "unavailable", gating=False)),
    ).assert_no_regression("exp-0")
    assert outcome["dimensions"][0]["name"] == "length"


def test_inconclusive_cases_counted_by_the_server_also_fail_the_gate():
    with pytest.raises(RegressionError, match="3 case\\(s\\) inconclusive"):
        result(
            detail(),
            comparison(dimension("answer_correctness", "unchanged"), inconclusive_rows=3),
        ).assert_no_regression("exp-0")

    outcome = result(
        detail(),
        comparison(dimension("answer_correctness", "unchanged"), inconclusive_rows=3),
    ).assert_no_regression("exp-0", allow_inconclusive=True)
    assert outcome["counts"]["inconclusive"] == 3


def test_a_regression_error_is_an_assertion_error_so_ci_exits_non_zero():
    assert issubclass(RegressionError, AssertionError)
