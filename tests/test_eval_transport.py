"""Batched reporting: when it flushes, and what it resends."""

from openobserve._eval.errors import APIError, TransportError
from openobserve._eval.transport import RecordBatcher


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def accept_all(records, scores):
    return {
        "records": [{"index": i, "accepted": True} for i in range(len(records))],
        "scores": [{"index": i, "accepted": True} for i in range(len(scores))],
        "acceptedRecords": len(records),
        "acceptedScores": len(scores),
    }


def record(n):
    return {"rowId": f"row-{n}", "trialIndex": 0, "status": "ok"}


def test_a_full_buffer_flushes_without_waiting_for_the_interval():
    sent = []
    batcher = RecordBatcher(
        lambda r, s: (sent.append((len(r), len(s))), accept_all(r, s))[1],
        flush_size=50,
        flush_interval=5.0,
        now=FakeClock(),
        sleep=lambda _: None,
    )

    for n in range(49):
        batcher.add_record(record(n))
    assert sent == []

    batcher.add_record(record(49))
    assert sent == [(50, 0)]


def test_an_aging_buffer_flushes_before_it_is_full():
    clock = FakeClock()
    sent = []
    batcher = RecordBatcher(
        lambda r, s: (sent.append(len(r)), accept_all(r, s))[1],
        flush_size=50,
        flush_interval=5.0,
        now=clock,
        sleep=lambda _: None,
    )

    batcher.add_record(record(0))
    batcher.maybe_flush()
    assert sent == []

    clock.advance(5.0)
    batcher.maybe_flush()
    assert sent == [1]


def test_the_final_flush_sends_whatever_is_left():
    sent = []
    batcher = RecordBatcher(
        lambda r, s: (sent.append((len(r), len(s))), accept_all(r, s))[1],
        now=FakeClock(),
        sleep=lambda _: None,
    )

    batcher.add_record(record(0))
    batcher.add_score({"rowId": "row-0", "trialIndex": 0})
    batcher.flush()

    assert sent == [(1, 1)]
    # A flush with nothing buffered is not a request.
    batcher.flush()
    assert sent == [(1, 1)]


def test_only_the_failed_parts_are_resent():
    attempts = []

    def send(records, scores):
        attempts.append([r["rowId"] for r in records])
        if len(attempts) == 1:
            return {
                "records": [
                    {"index": 0, "accepted": True},
                    {"index": 1, "accepted": False, "error": {"code": "storage_unavailable"}},
                    {"index": 2, "accepted": True},
                ],
                "acceptedRecords": 2,
                "rejectedRecords": 1,
            }
        return accept_all(records, scores)

    batcher = RecordBatcher(send, now=FakeClock(), sleep=lambda _: None)
    for n in range(3):
        batcher.add_record(record(n))
    batcher.flush()

    assert attempts == [["row-0", "row-1", "row-2"], ["row-1"]]


def test_a_rejection_the_server_would_only_repeat_is_never_resent():
    attempts = []

    def send(records, scores):
        attempts.append(len(records))
        return {
            "records": [{"index": 0, "accepted": False, "error": {"code": "unknown_slot"}}],
            "rejectedRecords": 1,
        }

    batcher = RecordBatcher(send, now=FakeClock(), sleep=lambda _: None)
    batcher.add_record(record(0))
    batcher.flush()

    # Resending identical bytes cannot change the verdict, so retrying would
    # only turn a reporting bug into a hang.
    assert attempts == [1]
    assert batcher.report.rejections[0]["code"] == "unknown_slot"


def test_an_immutable_slot_is_reported_once_and_never_resent():
    """A Slot that already concluded answers the same way forever."""
    attempts = []

    def send(records, scores):
        attempts.append(len(records))
        return {
            "records": [
                {
                    "index": 0,
                    "accepted": False,
                    "rowId": "row-1",
                    "error": {"code": "slot_immutable", "message": "already holds a record"},
                }
            ],
            "rejectedRecords": 1,
        }

    batcher = RecordBatcher(send, now=FakeClock(), sleep=lambda _: None)
    batcher.add_record(record(0))
    batcher.flush()

    assert attempts == [1]
    assert len(batcher.report.rejections) == 1
    assert batcher.report.rejections[0]["code"] == "slot_immutable"


def test_a_conflict_is_a_verdict_and_is_not_retried():
    attempts = []

    def send(records, scores):
        attempts.append(1)
        raise APIError(409, "sealed", method="POST", path="/records")

    batcher = RecordBatcher(send, now=FakeClock(), sleep=lambda _: None)
    batcher.add_record(record(0))
    try:
        batcher.flush()
    except APIError as error:
        assert error.is_conflict
    assert attempts == [1]


def test_an_unreachable_server_is_retried():
    attempts = []

    def send(records, scores):
        attempts.append(1)
        if len(attempts) < 3:
            raise TransportError("connection refused")
        return accept_all(records, scores)

    batcher = RecordBatcher(send, now=FakeClock(), sleep=lambda _: None, max_retries=3)
    batcher.add_record(record(0))
    batcher.flush()

    assert len(attempts) == 3


def test_the_report_accumulates_across_flushes():
    batcher = RecordBatcher(accept_all, flush_size=2, now=FakeClock(), sleep=lambda _: None)
    for n in range(4):
        batcher.add_record(record(n))
    batcher.flush()

    assert batcher.report.accepted_records == 4
    assert batcher.report.has_rejections is False
