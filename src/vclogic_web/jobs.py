"""Serialized local job execution and public rehearsal event streams."""

from __future__ import annotations

from collections import defaultdict, deque
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from threading import Condition, RLock
import time
from typing import Any, Callable, Iterator

from .models import PublicEvent


class SessionBusyError(RuntimeError):
    pass


_PRIVATE_FRAGMENTS = (
    "authorization",
    "api_key",
    "api-key",
    "prompt",
    "raw_response",
    "chain_of_thought",
)
_TERMINAL = {"complete", "failed"}


def _public(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _public(nested)
            for key, nested in value.items()
            if not any(fragment in str(key).casefold() for fragment in _PRIVATE_FRAGMENTS)
        }
    if isinstance(value, (list, tuple)):
        return [_public(row) for row in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class JobCoordinator:
    def __init__(self, *, executor: Executor | None = None, max_events: int = 500) -> None:
        self.executor = executor or ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="vc-rehearsal-web"
        )
        self.max_events = max_events
        self._guard = RLock()
        self._condition = Condition(self._guard)
        self._active: set[str] = set()
        self._events: dict[str, deque[PublicEvent]] = defaultdict(
            lambda: deque(maxlen=self.max_events)
        )
        self._next_event_id: dict[str, int] = defaultdict(lambda: 1)

    def _emit(self, session_id: str, stage: str, payload: dict[str, Any]) -> PublicEvent:
        with self._condition:
            event = PublicEvent(
                event_id=self._next_event_id[session_id],
                session_id=session_id,
                stage=stage,
                payload=_public(payload),
            )
            self._next_event_id[session_id] += 1
            self._events[session_id].append(event)
            self._condition.notify_all()
            return event

    def submit(
        self,
        session_id: str,
        operation: str,
        action: Callable[[Callable[[str, dict[str, Any]], PublicEvent]], Any],
    ) -> Future[Any]:
        with self._guard:
            if session_id in self._active:
                raise SessionBusyError(f"session mutation already active: {session_id}")
            self._active.add(session_id)
        self._emit(session_id, "queued", {"operation": operation})

        def run() -> Any:
            try:
                result = action(
                    lambda stage, payload: self._emit(session_id, stage, payload)
                )
                self._emit(session_id, "complete", {"operation": operation})
                return result
            except Exception as exc:
                self._emit(
                    session_id,
                    "failed",
                    {
                        "operation": operation,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                        "recoverable": True,
                    },
                )
                raise
            finally:
                with self._condition:
                    self._active.discard(session_id)
                    self._condition.notify_all()

        return self.executor.submit(run)

    def events(self, session_id: str, *, after: int = 0) -> tuple[PublicEvent, ...]:
        with self._guard:
            return tuple(
                row for row in self._events.get(session_id, ()) if row.event_id > after
            )

    def is_busy(self, session_id: str) -> bool:
        with self._guard:
            return session_id in self._active

    def stream(
        self, session_id: str, *, after: int = 0, timeout: float = 30.0
    ) -> Iterator[PublicEvent]:
        cursor = after
        while True:
            with self._condition:
                available = [
                    row
                    for row in self._events.get(session_id, ())
                    if row.event_id > cursor
                ]
                if not available:
                    self._condition.wait(timeout=timeout)
                    available = [
                        row
                        for row in self._events.get(session_id, ())
                        if row.event_id > cursor
                    ]
                    if not available:
                        return
            for event in available:
                cursor = event.event_id
                yield event
            if available[-1].stage in _TERMINAL:
                return
