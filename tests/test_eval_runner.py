"""What one slot's execution turns into."""

from openobserve._eval.runner import TaskRunner
from openobserve._eval.types import Skip, SlotRef, TaskResult, Usage
from openobserve.scorer import scorer


@scorer(config="exact_match")
def exact_match(output, expected_output):
    return 1.0 if str(output) == str(expected_output) else 0.0


@scorer(config="length")
def length(output):
    return float(len(str(output)))


def slot(row="row-1", trial=0, expected="tomorrow"):
    return SlotRef(
        row_id=row,
        logical_id="case-1",
        trial_index=trial,
        input={"question": "when?"},
        expected_output=expected,
        metadata={"difficulty": "hard"},
        has_reference=expected is not None,
    )


def runner(task, scorers=(), attempts=3):
    return TaskRunner(
        task,
        task_fingerprint="sha256:abc",
        local_scorers=scorers,
        experiment_id="exp-1",
        attempts=attempts,
        sleep=lambda _: None,
        clock=iter([0.0, 0.25]).__next__,
    )


def test_a_returned_value_becomes_an_ok_record_carrying_the_fingerprint():
    outcome = runner(lambda input, context: "tomorrow").run_slot(slot())

    assert outcome.record["status"] == "ok"
    assert outcome.record["output"] == "tomorrow"
    assert outcome.record["taskFingerprint"] == "sha256:abc"
    assert outcome.record["latencyMs"] == 250


def test_the_task_is_told_which_slot_it_is_answering():
    seen = {}

    def task(input, context):
        seen["input"] = input
        seen["row_id"] = context.row_id
        seen["trial_index"] = context.trial_index
        seen["metadata"] = dict(context.metadata)
        return "answer"

    runner(task).run_slot(slot(trial=2))

    assert seen["input"] == {"question": "when?"}
    assert seen["row_id"] == "row-1"
    assert seen["trial_index"] == 2
    assert seen["metadata"] == {"difficulty": "hard"}


def test_task_result_usage_overrides_what_the_sdk_would_have_inferred():
    def task(input, context):
        return TaskResult(output="answer", usage=Usage(tokens_in=11, tokens_out=3, cost=0.02))

    record = runner(task).run_slot(slot()).record

    assert record["tokensIn"] == 11
    assert record["tokensOut"] == 3
    assert record["cost"] == 0.02


def test_unknown_usage_is_reported_as_absent_rather_than_zero():
    record = runner(lambda input, context: "answer").run_slot(slot()).record

    # Zero cost and unknown cost mean different things to a summary.
    assert "tokensIn" not in record
    assert "cost" not in record


def test_a_skip_is_terminal_and_is_never_retried():
    calls = []

    def task(input, context):
        calls.append(1)
        raise Skip("no reference for this locale")

    outcome = runner(task).run_slot(slot())

    assert calls == [1]
    assert outcome.record["status"] == "skipped"
    assert outcome.record["skipMessage"] == "no reference for this locale"
    assert outcome.scores == []


def test_a_raising_task_retries_then_records_an_error_and_moves_on():
    calls = []

    def task(input, context):
        calls.append(1)
        raise RuntimeError("provider exploded")

    outcome = runner(task).run_slot(slot())

    assert len(calls) == 3
    assert outcome.record["status"] == "error"
    assert outcome.record["errorAttemptCount"] == 3
    assert "provider exploded" in outcome.record["errorMessage"]


def test_a_task_that_recovers_before_exhausting_its_attempts_succeeds():
    calls = []

    def task(input, context):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("flaky")
        return "tomorrow"

    outcome = runner(task).run_slot(slot())

    assert len(calls) == 3
    assert outcome.record["status"] == "ok"


def test_local_scores_are_reported_beside_the_record():
    outcome = runner(lambda input, context: "tomorrow", scorers=[exact_match, length]).run_slot(
        slot()
    )

    by_key = {s["clientScorerKey"]: s for s in outcome.scores}
    assert by_key["exact_match"]["value"] == 1.0
    assert by_key["exact_match"]["scoreConfig"] == "exact_match"
    assert by_key["length"]["value"] == 8.0


def test_a_case_without_a_reference_skips_that_dimension_and_is_counted():
    outcome = runner(lambda input, context: "tomorrow", scorers=[exact_match, length]).run_slot(
        slot(expected=None)
    )

    assert [s["clientScorerKey"] for s in outcome.scores] == ["length"]
    # The gap is reported as coverage, not silently dropped.
    assert outcome.not_applicable == {"exact_match": 1}


def test_a_scorer_that_raises_does_not_lose_the_execution_record():
    @scorer(config="broken")
    def broken(output):
        raise ValueError("bad scorer")

    outcome = runner(lambda input, context: "tomorrow", scorers=[broken]).run_slot(slot())

    assert outcome.record["status"] == "ok"
    assert outcome.scores == []
    assert outcome.not_applicable == {"broken": 1}


def test_returning_none_is_an_error_because_it_cannot_be_told_from_a_mistake():
    outcome = runner(lambda input, context: None, attempts=1).run_slot(slot())

    assert outcome.record["status"] == "error"
    assert "None" in outcome.record["errorMessage"]
