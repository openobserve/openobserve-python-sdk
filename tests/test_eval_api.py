"""The companion APIs and the run loop, against a fake server."""

import pytest

from openobserve import datasets, experiment, score_configs
from openobserve._eval.errors import ValidationError
from openobserve._eval.types import Skip
from openobserve.config import OpenObserveConfig
from openobserve.scorer import scorer


class FakeClient:
    """Records every call and answers from a canned routing table."""

    def __init__(self, routes=None):
        self.calls = []
        self.routes = routes or {}
        self.config = OpenObserveConfig(
            url="http://localhost:5080",
            org="acme",
            auth_token="Basic dGVzdA==",
        )

    def _answer(self, method, path, body=None, params=None):
        self.calls.append({"method": method, "path": path, "body": body, "params": params})
        handler = self.routes.get((method, path))
        if handler is None:
            raise AssertionError(f"unexpected {method} {path}")
        return handler(body, params) if callable(handler) else handler

    def get(self, path, params=None):
        return self._answer("GET", path, params=params)

    def post(self, path, body, headers=None):
        return self._answer("POST", path, body=body)

    def put(self, path, body, headers=None):
        return self._answer("PUT", path, body=body)

    def calls_to(self, method, path):
        return [c for c in self.calls if c["method"] == method and c["path"] == path]


DATASETS = {"list": [{"id": "ds-1", "name": "rag-qa-golden", "globalVersion": 9}]}


def test_a_bare_dataset_name_pins_the_version_current_at_resolution_time():
    client = FakeClient({("GET", "/datasets"): DATASETS})

    assert datasets.resolve("rag-qa-golden", client=client)["version"] == 9


def test_a_pinned_reference_selects_a_historical_snapshot():
    client = FakeClient({("GET", "/datasets"): DATASETS})

    assert datasets.resolve("rag-qa-golden@4", client=client)["version"] == 4


def test_an_unknown_dataset_names_the_fix():
    client = FakeClient({("GET", "/datasets"): {"list": []}})

    with pytest.raises(ValidationError, match="datasets.upsert"):
        datasets.resolve("missing", client=client)


def test_upsert_sends_identity_and_concurrency_fields_in_wire_shape():
    client = FakeClient(
        {
            ("GET", "/datasets"): DATASETS,
            ("PUT", "/datasets/ds-1/items"): {"items": [], "datasetVersion": 10},
        }
    )

    datasets.upsert(
        "rag-qa-golden",
        [
            {"input": "q1"},
            {
                "logical_id": "case-42",
                "input": "q2",
                "expected_output": "a2",
                "if_row_id": "row-7",
                "restore": True,
            },
        ],
        idempotency_key="run-1",
        client=client,
    )

    body = client.calls_to("PUT", "/datasets/ds-1/items")[0]["body"]
    assert body["idempotencyKey"] == "run-1"
    assert body["items"][0] == {"input": "q1"}
    assert body["items"][1] == {
        "input": "q2",
        "logicalId": "case-42",
        "expectedOutput": "a2",
        "ifRowId": "row-7",
        "restore": True,
    }


def test_upsert_generates_an_idempotency_key_when_the_caller_omits_one():
    client = FakeClient(
        {
            ("GET", "/datasets"): DATASETS,
            ("PUT", "/datasets/ds-1/items"): {"items": []},
        }
    )

    datasets.upsert("rag-qa-golden", [{"input": "q"}], client=client)

    assert client.calls_to("PUT", "/datasets/ds-1/items")[0]["body"]["idempotencyKey"]


def test_ensure_sends_the_declared_bounds():
    client = FakeClient({("PUT", "/score_configs"): {"outcome": "created", "config": {}}})

    score_configs.ensure("tone", type="numeric", min=1, max=5, client=client)

    body = client.calls_to("PUT", "/score_configs")[0]["body"]
    assert body == {"name": "tone", "dataType": "numeric", "numericRange": {"min": 1, "max": 5}}


def test_ensure_refuses_a_type_the_platform_does_not_have():
    client = FakeClient({})

    with pytest.raises(ValidationError, match="must be one of"):
        score_configs.ensure("tone", type="freeform", client=client)


# --- run() ------------------------------------------------------------------


@scorer(config="exact_match")
def exact_match(output, expected_output):
    return 1.0 if str(output) == str(expected_output) else 0.0


def slot_payload(row, trial, expected="tomorrow"):
    payload = {
        "rowId": row,
        "logicalId": f"case-{row}",
        "trialIndex": trial,
        "input": {"question": "when?"},
    }
    if expected is not None:
        payload["expectedOutput"] = expected
    return payload


def run_client(slots, extra=None):
    routes = {
        ("GET", "/datasets"): DATASETS,
        ("GET", "/score_configs"): {"list": [{"name": "exact_match", "entityId": "sc-1"}]},
        ("GET", "/scorers"): {"list": [{"name": "answer_correctness", "entityId": "sco-1"}]},
        ("POST", "/experiments"): {"experiment": {"id": "exp-1", "status": "running"}},
        ("GET", "/experiments/exp-1/slots"): {
            "slots": slots,
            "hasMore": False,
            "total": len(slots),
        },
        ("POST", "/experiments/exp-1/records"): lambda body, _: {
            "records": [{"index": i, "accepted": True} for i in range(len(body["records"]))],
            "scores": [{"index": i, "accepted": True} for i in range(len(body["scores"]))],
            "acceptedRecords": len(body["records"]),
            "acceptedScores": len(body["scores"]),
        },
        ("POST", "/experiments/exp-1/finalize"): {"id": "exp-1", "status": "completed"},
    }
    routes.update(extra or {})
    return FakeClient(routes)


def test_run_creates_an_sdk_experiment_pinned_to_the_dataset_and_fingerprint():
    client = run_client([slot_payload("row-1", 0)])

    experiment.run(
        "prompt-v3",
        dataset="rag-qa-golden",
        task=lambda input, context: "tomorrow",
        scorers=[exact_match],
        client=client,
    )

    body = client.calls_to("POST", "/experiments")[0]["body"]
    assert body["datasetId"] == "ds-1"
    assert body["datasetVersion"] == 9
    assert body["task"]["type"] == "sdk"
    assert body["task"]["taskFingerprint"].startswith("sha256:")
    assert body["idempotencyKey"]


def test_run_has_no_data_parameter():
    import inspect

    assert "data" not in inspect.signature(experiment.run).parameters


def test_run_reports_every_slot_and_then_finalizes():
    client = run_client([slot_payload("row-1", 0), slot_payload("row-2", 0)])

    experiment.run(
        "prompt-v3",
        dataset="rag-qa-golden",
        task=lambda input, context: "tomorrow",
        scorers=[exact_match],
        max_concurrency=1,
        client=client,
    )

    reported = client.calls_to("POST", "/experiments/exp-1/records")
    rows = [r["rowId"] for call in reported for r in call["body"]["records"]]
    assert sorted(rows) == ["row-1", "row-2"]
    assert len(client.calls_to("POST", "/experiments/exp-1/finalize")) == 1


def test_run_reports_a_skip_and_an_error_without_stopping():
    client = run_client(
        [slot_payload("row-1", 0), slot_payload("row-2", 0), slot_payload("row-3", 0)]
    )

    def task(input, context):
        if context.row_id == "row-2":
            raise Skip("nothing to answer")
        if context.row_id == "row-3":
            raise RuntimeError("boom")
        return "tomorrow"

    experiment.run(
        "prompt-v3",
        dataset="rag-qa-golden",
        task=task,
        scorers=[exact_match],
        max_concurrency=1,
        client=client,
    )

    records = {
        r["rowId"]: r
        for call in client.calls_to("POST", "/experiments/exp-1/records")
        for r in call["body"]["records"]
    }
    assert records["row-1"]["status"] == "ok"
    assert records["row-2"]["status"] == "skipped"
    assert records["row-3"]["status"] == "error"


def test_run_validates_a_missing_score_config_before_doing_any_work():
    client = run_client(
        [slot_payload("row-1", 0)],
        extra={("GET", "/score_configs"): {"list": []}},
    )

    with pytest.raises(ValidationError, match="score_configs.ensure"):
        experiment.run(
            "prompt-v3",
            dataset="rag-qa-golden",
            task=lambda input, context: "tomorrow",
            scorers=[exact_match],
            client=client,
        )

    # Nothing was created, so nothing has to be cleaned up.
    assert client.calls_to("POST", "/experiments") == []


def test_run_validates_a_missing_platform_scorer_before_doing_any_work():
    client = run_client([slot_payload("row-1", 0)])

    with pytest.raises(ValidationError, match="scorer 'nope' was not found"):
        experiment.run(
            "prompt-v3",
            dataset="rag-qa-golden",
            task=lambda input, context: "tomorrow",
            scorers=["nope"],
            client=client,
        )
    assert client.calls_to("POST", "/experiments") == []


def test_run_needs_at_least_one_scorer():
    with pytest.raises(ValidationError, match="at least one scorer"):
        experiment.run(
            "prompt-v3",
            dataset="rag-qa-golden",
            task=lambda input, context: "x",
            scorers=[],
            client=run_client([]),
        )


def test_resume_refuses_an_experiment_that_is_not_failed():
    client = FakeClient(
        {
            ("GET", "/datasets"): DATASETS,
            ("GET", "/score_configs"): {"list": [{"name": "exact_match"}]},
            ("GET", "/experiments/exp-1"): {
                "experiment": {"id": "exp-1", "status": "completed", "task": {}}
            },
        }
    )

    with pytest.raises(ValidationError, match="only a failed experiment"):
        experiment.run(
            "prompt-v3",
            dataset="rag-qa-golden",
            task=lambda input, context: "x",
            scorers=[exact_match],
            resume="exp-1",
            client=client,
        )


def test_resume_refuses_when_the_task_has_changed():
    client = FakeClient(
        {
            ("GET", "/datasets"): DATASETS,
            ("GET", "/score_configs"): {"list": [{"name": "exact_match"}]},
            ("GET", "/experiments/exp-1"): {
                "experiment": {
                    "id": "exp-1",
                    "status": "failed",
                    "task": {"taskFingerprint": "sha256:something-else"},
                }
            },
        }
    )

    with pytest.raises(ValidationError, match="task has changed"):
        experiment.run(
            "prompt-v3",
            dataset="rag-qa-golden",
            task=lambda input, context: "x",
            scorers=[exact_match],
            resume="exp-1",
            client=client,
        )
