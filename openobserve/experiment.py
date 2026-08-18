"""Run your own code as the subject under evaluation.

``run()`` anchors to a dataset that already exists, executes your task once per
slot, reports what happened in batches, and concludes the run. It deliberately
has no ``data=`` parameter: an experiment that carried its own inline data
would be comparable to no other experiment, which defeats the purpose of
running one.
"""

import os
import subprocess
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import datasets as _datasets
from . import score_configs as _score_configs
from ._eval.errors import ValidationError
from ._eval.fingerprint import task_fingerprint
from ._eval.http import HTTPClient
from ._eval.results import ExperimentResult
from ._eval.runner import TaskRunner, run_slots
from ._eval.session import client_for, configure
from ._eval.transport import (
    DEFAULT_FLUSH_INTERVAL_SECONDS,
    DEFAULT_FLUSH_SIZE,
    RecordBatcher,
)
from ._eval.types import SlotRef
from .scorer import LocalScorer, PlatformScorerRef, split_scorers

DEFAULT_MAX_CONCURRENCY = 8
SLOT_PAGE_SIZE = 200


def run(
    name: str,
    *,
    dataset: str,
    task: Callable[..., Any],
    scorers: Sequence[Any] = (),
    trial_count: int = 1,
    filter: Optional[Dict[str, Any]] = None,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    metadata: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    resume: Optional[str] = None,
    flush_size: int = DEFAULT_FLUSH_SIZE,
    flush_interval: float = DEFAULT_FLUSH_INTERVAL_SECONDS,
    idempotency_key: Optional[str] = None,
    tracer: Any = None,
    client: Optional[HTTPClient] = None,
) -> ExperimentResult:
    """Evaluate ``task`` over ``dataset`` and return the finished run.

    ``dataset`` is a name, or ``name@version`` to pin a historical snapshot; a
    bare name pins whatever is current when the run starts.

    ``scorers`` may mix platform references (``"answer_correctness@2"``) with
    ``@scorer``-decorated local functions. The two are split automatically: the
    platform kind is evaluated server-side, the local kind runs here and is
    self-reported.

    ``resume`` continues a failed experiment instead of starting a new one. It
    reruns the slots that never reached a terminal state and retries the ones
    that errored, leaving successes untouched.
    """
    http = client or client_for()
    platform_scorers, local_scorers = split_scorers(scorers)
    if not platform_scorers and not local_scorers:
        raise ValidationError("a run needs at least one scorer")

    fingerprint = task_fingerprint(task, scorer_keys=[s.key for s in local_scorers])

    if resume:
        experiment = _resume_experiment(http, resume, fingerprint)
        slots = _pending_slots(http, experiment["id"])
    else:
        _validate_references(http, dataset, platform_scorers, local_scorers)
        experiment = _create_experiment(
            http,
            name=name,
            dataset=dataset,
            description=description,
            fingerprint=fingerprint,
            platform_scorers=platform_scorers,
            trial_count=trial_count,
            filter=filter,
            metadata=_collected_metadata(metadata),
            idempotency_key=idempotency_key,
        )
        slots = _all_slots(http, experiment["id"])

    experiment_id = experiment["id"]
    batcher = RecordBatcher(
        lambda records, scores: http.post(
            f"/experiments/{experiment_id}/records",
            {"records": records, "scores": scores},
        ),
        flush_size=flush_size,
        flush_interval=flush_interval,
    )
    runner = TaskRunner(
        task,
        task_fingerprint=fingerprint,
        local_scorers=local_scorers,
        experiment_id=experiment_id,
        tracer=tracer or _default_tracer(),
    )

    not_applicable: Dict[str, int] = {}

    def absorb(outcome: Any) -> None:
        batcher.add_record(outcome.record)
        for score in outcome.scores:
            batcher.add_score(score)
        for key, count in outcome.not_applicable.items():
            not_applicable[key] = not_applicable.get(key, 0) + count
        batcher.maybe_flush()

    run_slots(runner, slots, max_concurrency=max(1, max_concurrency), on_outcome=absorb)
    batcher.flush()

    # Only a run that completed normally concludes itself. A crashed script
    # deliberately leaves the experiment open for the server's deadline
    # backstop, so an interrupted run is visibly unfinished rather than being
    # sealed as if it had finished.
    http.post(f"/experiments/{experiment_id}/finalize", {})

    return ExperimentResult(
        http,
        experiment_id,
        rejections=batcher.report.rejections,
        not_applicable=not_applicable,
    )


def _create_experiment(
    http: HTTPClient,
    *,
    name: str,
    dataset: str,
    description: Optional[str],
    fingerprint: str,
    platform_scorers: Sequence[PlatformScorerRef],
    trial_count: int,
    filter: Optional[Dict[str, Any]],
    metadata: Dict[str, Any],
    idempotency_key: Optional[str],
) -> Dict[str, Any]:
    pinned = _datasets.resolve(dataset, client=http)
    body: Dict[str, Any] = {
        "name": name,
        "datasetId": pinned["id"],
        "datasetVersion": pinned["version"],
        "task": {"type": "sdk", "taskFingerprint": fingerprint},
        "scorers": [_scorer_ref_body(http, ref) for ref in platform_scorers],
        "trialCount": trial_count,
        "metadata": metadata,
        "idempotencyKey": idempotency_key or uuid.uuid4().hex,
    }
    if description:
        body["description"] = description
    if filter:
        body["datasetFilter"] = filter
    response = http.post("/experiments", body)
    created: Dict[str, Any] = response.get("experiment") or response
    return created


def _scorer_ref_body(http: HTTPClient, ref: PlatformScorerRef) -> Dict[str, Any]:
    body: Dict[str, Any] = {"id": _scorer_entity_id(http, ref)}
    if ref.version is not None:
        body["version"] = ref.version
    return body


def _scorer_entity_id(http: HTTPClient, ref: PlatformScorerRef) -> str:
    for scorer in (http.get("/scorers") or {}).get("list", []):
        if scorer.get("name") == ref.name or scorer.get("entityId") == ref.name:
            return str(scorer.get("entityId") or scorer.get("id"))
    raise ValidationError(f"scorer {ref.name!r} was not found")


def _validate_references(
    http: HTTPClient,
    dataset: str,
    platform_scorers: Sequence[PlatformScorerRef],
    local_scorers: Sequence[LocalScorer],
) -> None:
    """Fail before any work starts.

    A run that discovers a missing scorer on its last slot has burned the whole
    cohort to learn something it could have been told immediately.
    """
    _datasets.resolve(dataset, client=http)
    for ref in platform_scorers:
        _scorer_entity_id(http, ref)
    known = {config.get("name") for config in _score_configs.list_all(client=http)}
    missing = sorted({s.config for s in local_scorers if s.config not in known})
    if missing:
        raise ValidationError(
            f"score config(s) {', '.join(missing)} do not exist; "
            "call score_configs.ensure(...) first"
        )


def _resume_experiment(http: HTTPClient, experiment_id: str, fingerprint: str) -> Dict[str, Any]:
    response = http.get(f"/experiments/{experiment_id}")
    experiment = response.get("experiment") or response
    status = str(experiment.get("status", ""))
    if status != "failed":
        raise ValidationError(
            f"only a failed experiment can be resumed; {experiment_id} is {status!r}"
        )
    stored = (experiment.get("task") or {}).get("taskFingerprint")
    if stored != fingerprint:
        raise ValidationError(
            "the task has changed since this experiment ran, so resuming it would mix two "
            "versions of the code in one cohort. Start a new experiment instead."
        )
    http.post(f"/experiments/{experiment_id}/retry", {})
    resumed: Dict[str, Any] = experiment
    return resumed


def _all_slots(http: HTTPClient, experiment_id: str) -> List[SlotRef]:
    return list(_iter_slots(http, experiment_id))


def _pending_slots(http: HTTPClient, experiment_id: str) -> List[SlotRef]:
    """Slots a resume still owes: never run, or run and errored.

    Successes and skips are left exactly as they are — re-running them would
    replace evidence that is already final.
    """
    done = _terminal_slot_keys(http, experiment_id)
    return [
        slot
        for slot in _iter_slots(http, experiment_id)
        if (slot.row_id, slot.trial_index) not in done
    ]


def _terminal_slot_keys(http: HTTPClient, experiment_id: str) -> set:
    keys = set()
    offset = 0
    while True:
        page = http.get(
            f"/experiments/{experiment_id}",
            params={"resultPage": offset // 100, "resultPageSize": 100},
        )
        slots = ((page.get("results") or {}).get("slots")) or []
        for slot in slots:
            if str(slot.get("taskStatus", "")) in ("ok", "skipped"):
                keys.add((str(slot.get("rowId")), int(slot.get("trialIndex", 0))))
        if len(slots) < 100:
            return keys
        offset += len(slots)


def _iter_slots(http: HTTPClient, experiment_id: str) -> Any:
    offset = 0
    while True:
        page = http.get(
            f"/experiments/{experiment_id}/slots",
            params={"from": offset, "size": SLOT_PAGE_SIZE},
        )
        slots = page.get("slots") or []
        for slot in slots:
            yield SlotRef.from_api(slot)
        if not page.get("hasMore") or not slots:
            return
        offset += len(slots)


def _collected_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Stamp the run with where it came from.

    Anything the caller supplies wins: these are conveniences, not policy.
    """
    collected: Dict[str, Any] = {}
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if commit:
        collected["git.commit"] = commit
    if branch and branch != "HEAD":
        collected["git.branch"] = branch
    for key, env in (("ci.run_id", "GITHUB_RUN_ID"), ("ci.workflow", "GITHUB_WORKFLOW")):
        value = os.getenv(env)
        if value:
            collected[key] = value
    collected.update(metadata or {})
    return collected


def _git(*args: str) -> Optional[str]:
    try:
        output = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = output.stdout.strip()
    return value or None


def _default_tracer() -> Any:
    """Reuse the tracer provider the telemetry SDK already configured.

    When the host process is instrumented, task spans nest under whatever it
    emits, and usage aggregates for free. When it is not, runs still work — the
    records simply carry no trace id.
    """
    try:
        from .client import get_tracer_provider

        provider = get_tracer_provider()
    except Exception:  # pragma: no cover - telemetry is optional here
        return None
    if provider is None:
        return None
    try:
        return provider.get_tracer("openobserve.experiment")
    except Exception:  # pragma: no cover - defensive
        return None


__all__ = ["configure", "run"]
