from concurrent.futures import Future

import pytest

from vclogic_web.jobs import JobCoordinator, SessionBusyError


class ManualExecutor:
    def __init__(self) -> None:
        self.calls = []

    def submit(self, function):
        self.calls.append(function)
        return Future()


class InlineExecutor:
    def submit(self, function):
        future = Future()
        try:
            future.set_result(function())
        except Exception as exc:  # pragma: no cover - test helper
            future.set_exception(exc)
        return future


def test_coordinator_rejects_parallel_mutation() -> None:
    coordinator = JobCoordinator(executor=ManualExecutor())
    coordinator.submit("session-1", "start", lambda emit: None)

    with pytest.raises(SessionBusyError):
        coordinator.submit("session-1", "answer", lambda emit: None)


def test_events_have_monotonic_ids_and_public_payloads() -> None:
    coordinator = JobCoordinator(executor=InlineExecutor())

    coordinator.submit(
        "session-1",
        "start",
        lambda emit: emit(
            "phase1_running", {"status": "working", "prompt": "private"}
        ),
    )
    rows = coordinator.events("session-1", after=0)

    assert [row.event_id for row in rows] == sorted(
        {row.event_id for row in rows}
    )
    assert all("prompt" not in row.payload for row in rows)
    assert rows[-1].stage == "complete"


def test_failed_job_is_recoverable_and_releases_lock() -> None:
    coordinator = JobCoordinator(executor=InlineExecutor())

    coordinator.submit(
        "session-1",
        "start",
        lambda emit: (_ for _ in ()).throw(RuntimeError("provider interrupted")),
    )

    assert coordinator.events("session-1", after=0)[-1].stage == "failed"
    coordinator.submit("session-1", "retry", lambda emit: None)
    assert coordinator.events("session-1", after=0)[-1].stage == "complete"
