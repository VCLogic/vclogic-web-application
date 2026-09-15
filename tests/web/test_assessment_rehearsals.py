from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import pytest

from vclogic_web.jobs import JobCoordinator, SessionBusyError
from vclogic_web.models import CanonicalAssessmentDetail, SessionDetailResponse
from vclogic_web.service import RehearsalWebService


class InlineExecutor:
    def submit(self, function):
        future = Future()
        try:
            future.set_result(function())
        except Exception as exc:
            future.set_exception(exc)
        return future


class ManualExecutor:
    def __init__(self) -> None:
        self.calls = []

    def submit(self, function):
        self.calls.append(function)
        return Future()


class FakeAssessmentService:
    def __init__(self, assessment):
        self.assessment = assessment
        self.registered = []

    def get_assessment(self, assessment_id):
        assert assessment_id == self.assessment.assessment_id
        return self.assessment

    def register_rehearsal(self, assessment_id, session_id):
        self.registered.append((assessment_id, session_id))


class RecordingStore:
    def __init__(self) -> None:
        self.accepted = []

    def read_json(self, _path):
        return {"current_question": {"question_id": "q4"}}

    def accept_answer_submission(self, question_id, text):
        self.accepted.append((question_id, text))


def test_two_rehearsals_import_one_completed_assessment_without_rebuilding(
    tmp_path, monkeypatch
) -> None:
    run_root = tmp_path / "canonical-run"
    run_root.mkdir()
    assessment = CanonicalAssessmentDetail(
        assessment_id="assessment-1",
        project_id="project-1",
        version_id="version-1",
        vc_slug="elizabeth-yin-hustle-fund",
        pitch_sha256="a" * 64,
        status="complete",
        created_at="2026-09-01T00:00:00Z",
        updated_at="2026-09-01T00:00:00Z",
        canonical_run_path=str(run_root),
        decision="In",
        investment_likelihood=0.63,
        decision_confidence=0.7,
    )
    assessment_service = FakeAssessmentService(assessment)
    calls = []

    def command_start(_config, args, progress_callback=None):
        calls.append(args)

    monkeypatch.setattr("vclogic_web.service.rehearsal_cli.command_start", command_start)
    service = object.__new__(RehearsalWebService)
    service.config = SimpleNamespace()
    service.output_root = tmp_path / "rehearsals"
    service.coordinator = JobCoordinator(executor=InlineExecutor())
    service.assessment_service = assessment_service
    service.project_store = SimpleNamespace(
        read_pitch=lambda _project, _version: "# ShiftPilot\n",
        get_project=lambda _project: SimpleNamespace(company_aliases=("ShiftPilot",)),
    )
    service.get_session = lambda _session: SimpleNamespace(
        status="awaiting_answer", current_assessment=None
    )

    first = service.create_rehearsal_from_assessment("assessment-1", "quick")
    second = service.create_rehearsal_from_assessment("assessment-1", "deep")

    assert first.session_id != second.session_id
    assert [row.rehearsal_depth for row in calls] == ["quick", "deep"]
    assert all(row.build_canonical_baseline is False for row in calls)
    assert all(row.canonical_baseline == run_root for row in calls)
    assert len(assessment_service.registered) == 2


def test_rehearsal_requires_completed_usable_assessment(tmp_path) -> None:
    assessment = CanonicalAssessmentDetail(
        assessment_id="assessment-1",
        project_id="project-1",
        version_id="version-1",
        vc_slug="phil-nadel",
        pitch_sha256="a" * 64,
        status="failed",
        created_at="2026-09-01T00:00:00Z",
        updated_at="2026-09-01T00:00:00Z",
    )
    service = object.__new__(RehearsalWebService)
    service.assessment_service = FakeAssessmentService(assessment)

    try:
        service.create_rehearsal_from_assessment("assessment-1", "standard")
    except ValueError as exc:
        assert "completed canonical assessment" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("failed assessment unexpectedly started rehearsal")


def test_session_view_reports_an_active_server_operation(tmp_path, monkeypatch) -> None:
    coordinator = JobCoordinator(executor=ManualExecutor())
    coordinator.submit("session-1", "answer", lambda _emit: None)
    view = SessionDetailResponse(
        session_id="session-1",
        vc_slug="cyan-banister-long-journey-ventures",
        investor_display_name="Cyan Banister-like Investor",
        disclosure="Simulation",
        status="awaiting_answer",
        pitch_text="Pitch",
        pitch_sha256="a" * 64,
    )
    monkeypatch.setattr(
        "vclogic_web.service.SessionViewBuilder",
        lambda _store: SimpleNamespace(build=lambda: view),
    )
    service = object.__new__(RehearsalWebService)
    service.coordinator = coordinator
    service._store = lambda _session_id: object()

    result = service.get_session("session-1")

    assert result.operation_active is True


def test_busy_answer_is_rejected_before_submission_artifact_changes() -> None:
    coordinator = JobCoordinator(executor=ManualExecutor())
    coordinator.submit("session-1", "answer", lambda _emit: None)
    store = RecordingStore()
    service = object.__new__(RehearsalWebService)
    service.coordinator = coordinator
    service._store = lambda _session_id: store

    with pytest.raises(SessionBusyError):
        service.answer("session-1", "A repeated answer")

    assert store.accepted == []
