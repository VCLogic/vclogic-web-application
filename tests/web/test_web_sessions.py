from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient

from vclogic_web.app import create_app
from vc_clone_graph.rehearsal_artifacts import PendingAnswerConflict
from vclogic_web.jobs import SessionBusyError
from vclogic_web.models import JobResponse, SessionListResponse


class FakeRehearsalService:
    def __init__(self) -> None:
        self.created = []
        self.answers = []
        self.busy = False

    def create_session(self, request):
        self.created.append(request)
        return JobResponse(
            session_id="session-1",
            status="queued",
            event_url="/api/sessions/session-1/events",
        )

    def list_sessions(self):
        return SessionListResponse(sessions=())

    def get_session(self, session_id):
        raise ValueError(f"unknown rehearsal session: {session_id}")

    def answer(self, session_id, text):
        if self.busy:
            raise SessionBusyError(session_id)
        self.answers.append((session_id, text))
        return JobResponse(
            session_id=session_id,
            status="queued",
            event_url=f"/api/sessions/{session_id}/events",
        )

    def finish(self, session_id):
        if self.busy:
            raise SessionBusyError(session_id)
        return self.answer(session_id, "finish")

    def retry(self, session_id):
        return self.answer(session_id, "retry")

    def events(self, session_id, after=0):
        return iter(())

    def report(self, session_id):
        return {"session_id": session_id}

    def export(self, session_id):
        return b"PK-export"

    def verify(self, session_id):
        return {"session_id": session_id, "verified": True}


def test_create_session_authorizes_and_queues_canonical_pipeline() -> None:
    service = FakeRehearsalService()
    client = TestClient(create_app(testing=True, rehearsal_service=service))

    response = client.post(
        "/api/sessions",
        json={
            "vc_slug": "charles-hudson-precursor-ventures",
            "company_aliases": ["TargetCo"],
            "pitch_text": "Founder pitch",
            "authorize_provider_cost": True,
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert service.created[0].pitch_text == "Founder pitch\n"


def test_missing_cost_authorization_is_rejected() -> None:
    client = TestClient(
        create_app(testing=True, rehearsal_service=FakeRehearsalService())
    )

    response = client.post(
        "/api/sessions",
        json={
            "vc_slug": "charles-hudson-precursor-ventures",
            "company_aliases": ["TargetCo"],
            "pitch_text": "Founder pitch",
            "authorize_provider_cost": False,
        },
    )

    assert response.status_code == 422


def test_answer_and_finish_are_serialized() -> None:
    service = FakeRehearsalService()
    service.busy = True
    client = TestClient(create_app(testing=True, rehearsal_service=service))

    response = client.post(
        "/api/sessions/session-1/answers", json={"text": "82% renewed."}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "session_busy"


def test_conflicting_pending_answer_is_a_recoverable_conflict() -> None:
    service = FakeRehearsalService()

    def conflict(_session_id, _text):
        raise PendingAnswerConflict("a different answer is already pending")

    service.answer = conflict
    client = TestClient(create_app(testing=True, rehearsal_service=service))

    response = client.post(
        "/api/sessions/session-1/answers", json={"text": "Stale answer"}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "answer_conflict"
    assert response.json()["recoverable"] is True


def test_unknown_session_is_404() -> None:
    client = TestClient(
        create_app(testing=True, rehearsal_service=FakeRehearsalService())
    )

    response = client.get("/api/sessions/missing")

    assert response.status_code == 404


def test_export_is_downloadable_zip() -> None:
    client = TestClient(
        create_app(testing=True, rehearsal_service=FakeRehearsalService())
    )

    response = client.get("/api/sessions/session-1/export")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content == b"PK-export"
