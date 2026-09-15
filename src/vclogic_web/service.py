"""Application service connecting the web API to canonical rehearsal runtime."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from vc_clone_graph import rehearsal_cli
from vc_clone_graph.rehearsal_artifacts import RehearsalArtifactStore
from vc_clone_graph.rehearsal_config import RehearsalConfig, load_rehearsal_config
from vc_clone_graph.rehearsal_runtime import list_investors
from .assessment_service import CanonicalAssessmentService
from .matching import MatchingService, load_reference_scores
from .jobs import JobCoordinator, SessionBusyError
from .models import (
    CreateSessionRequest,
    CreatePitchProjectRequest,
    CreatePitchVersionRequest,
    CreateCanonicalAssessmentRequest,
    CreateMatchRequest,
    AssessmentJobResponse,
    MatchJobResponse,
    UpdateComparisonRequest,
    PitchProjectDetail,
    PitchProjectListResponse,
    PitchVersionDetail,
    JobResponse,
    PublicEvent,
    SessionDetailResponse,
    SessionListResponse,
)
from .session_views import SessionViewBuilder, list_sessions
from .project_store import PitchProjectStore


class RehearsalWebService:
    """Serialized façade over the existing auditable CLI/runtime functions."""

    def __init__(
        self,
        config_path: Path,
        *,
        workspace: Path | None = None,
        coordinator: JobCoordinator | None = None,
        project_store: PitchProjectStore | None = None,
        assessment_service: CanonicalAssessmentService | None = None,
        matching_service: MatchingService | None = None,
    ) -> None:
        self.workspace = (workspace or Path.cwd()).resolve()
        candidate = Path(config_path)
        if not candidate.is_absolute():
            candidate = self.workspace / candidate
        self.config_path = candidate.resolve()
        self.config: RehearsalConfig = load_rehearsal_config(self.config_path, workspace=self.workspace)
        output = Path(self.config.rehearsal.output_root)
        self.output_root = (self.workspace / output).resolve() if not output.is_absolute() else output
        self.coordinator = coordinator or JobCoordinator()
        self.project_store = project_store or PitchProjectStore(
            self.output_root.parent / "pitch-projects"
        )
        self.assessment_service = assessment_service or CanonicalAssessmentService(
            store=self.project_store,
            workspace=self.workspace,
            rehearsal_config=self.config,
        )
        input_root = Path(self.config.rehearsal.input_root)
        if not input_root.is_absolute():
            input_root = self.workspace / input_root
        self.available_vc_slugs = {
            row.vc_slug for row in list_investors(input_root)
        }
        reference_path = (
            self.workspace
            / "reports/evaluation/canonical-v4-v41-portfolio-2026-08-15/phase2/predictions.csv"
        )
        self.matching_service = matching_service or MatchingService(
            store=self.project_store,
            assessments=self.assessment_service,
            reference_scores=load_reference_scores(
                reference_path, self.available_vc_slugs
            ),
        )

    @staticmethod
    def _job(session_id: str, status: str = "queued") -> JobResponse:
        return JobResponse(
            session_id=session_id,
            status=status,
            event_url=f"/api/sessions/{session_id}/events",
        )

    def _root(self, session_id: str) -> Path:
        return rehearsal_cli.locate_session(self.output_root, session_id)

    def _store(self, session_id: str) -> RehearsalArtifactStore:
        return RehearsalArtifactStore.open(self._root(session_id))

    def create_session(self, request: CreateSessionRequest) -> JobResponse:
        session_id = str(uuid4())

        def run(emit):
            emit("preparing_inputs", {"vc_slug": request.vc_slug})
            emit("phase1_running", {"message": "Building canonical rationale baseline"})
            args = argparse.Namespace(
                pitch=None,
                text=request.pitch_text,
                session=session_id,
                company=list(request.company_aliases),
                vc=request.vc_slug,
                rehearsal_depth=request.rehearsal_depth,
                build_canonical_baseline=True,
                canonical_baseline=None,
            )
            with redirect_stdout(StringIO()):
                rehearsal_cli.command_start(
                    self.config, args, progress_callback=emit
                )
            view = self.get_session(session_id)
            emit(view.status, {"decision": view.current_assessment.decision if view.current_assessment else None})
            return view

        self.coordinator.submit(session_id, "start", run)
        return self._job(session_id)

    def create_rehearsal_from_assessment(
        self, assessment_id: str, rehearsal_depth: str
    ) -> JobResponse:
        if rehearsal_depth not in {"quick", "standard", "deep"}:
            raise ValueError("invalid rehearsal depth")
        assessment = self.assessment_service.get_assessment(assessment_id)
        if assessment.status != "complete" or not assessment.canonical_run_path:
            raise ValueError("rehearsal requires a completed canonical assessment")
        canonical_run = Path(assessment.canonical_run_path).resolve(strict=True)
        pitch = self.project_store.read_pitch(
            assessment.project_id, assessment.version_id
        )
        project = self.project_store.get_project(assessment.project_id)
        session_id = str(uuid4())

        def run(emit):
            emit(
                "preparing_inputs",
                {
                    "vc_slug": assessment.vc_slug,
                    "message": "Reusing the verified canonical assessment",
                },
            )
            args = argparse.Namespace(
                pitch=None,
                text=pitch,
                session=session_id,
                company=list(project.company_aliases),
                vc=assessment.vc_slug,
                rehearsal_depth=rehearsal_depth,
                build_canonical_baseline=False,
                canonical_baseline=canonical_run,
            )
            with redirect_stdout(StringIO()):
                rehearsal_cli.command_start(
                    self.config, args, progress_callback=emit
                )
            try:
                store = self._store(session_id)
                config = store.read_json("session-config.json")
                config.update(
                    {
                        "project_id": assessment.project_id,
                        "pitch_version_id": assessment.version_id,
                        "assessment_id": assessment.assessment_id,
                    }
                )
                store.write_accepted("session-config.json", config)
            except (OSError, ValueError):
                # A completed session remains valid even if optional project-link
                # metadata cannot be attached; the assessment index is authoritative.
                pass
            self.assessment_service.register_rehearsal(assessment_id, session_id)
            view = self.get_session(session_id)
            emit(view.status, {"assessment_id": assessment_id})
            return view

        self.coordinator.submit(session_id, "start_rehearsal", run)
        return self._job(session_id)

    def list_projects(self) -> PitchProjectListResponse:
        return PitchProjectListResponse(projects=self.project_store.list_projects())

    def create_project(self, request: CreatePitchProjectRequest) -> PitchProjectDetail:
        return self.project_store.create_project(
            display_name=request.display_name,
            company_aliases=request.company_aliases,
            pitch_text=request.pitch_text,
        )

    def get_project(self, project_id: str) -> PitchProjectDetail:
        return self.project_store.get_project(project_id)

    def create_version(self, project_id: str, request: CreatePitchVersionRequest):
        return self.project_store.create_version(project_id, pitch_text=request.pitch_text)

    def get_version(self, project_id: str, version_id: str) -> PitchVersionDetail:
        version = self.project_store.get_version(project_id, version_id)
        return PitchVersionDetail(
            **version.model_dump(),
            pitch_text=self.project_store.read_pitch(project_id, version_id),
        )

    def _validate_vc(self, vc_slug: str) -> None:
        if vc_slug not in self.available_vc_slugs:
            raise ValueError(f"unknown investor profile: {vc_slug}")

    def start_assessment(
        self,
        project_id: str,
        version_id: str,
        request: CreateCanonicalAssessmentRequest,
    ) -> AssessmentJobResponse:
        self._validate_vc(request.vc_slug)
        assessment = self.assessment_service.ensure_assessment(
            project_id, version_id, request.vc_slug
        )
        if assessment.status != "complete" and not self.coordinator.is_busy(
            assessment.assessment_id
        ):
            self.coordinator.submit(
                assessment.assessment_id,
                "canonical_assessment",
                lambda emit: self.assessment_service.run_assessment(
                    assessment.assessment_id, emit=emit
                ),
            )
        return AssessmentJobResponse(
            assessment_id=assessment.assessment_id,
            status="complete" if assessment.status == "complete" else "queued",
            event_url=f"/api/assessments/{assessment.assessment_id}/events",
        )

    def get_comparison(self, project_id: str, version_id: str):
        return self.matching_service.get_comparison(project_id, version_id)

    def update_comparison(
        self, project_id: str, version_id: str, request: UpdateComparisonRequest
    ):
        for vc_slug in request.vc_slugs:
            self._validate_vc(vc_slug)
        comparison = self.matching_service.update_comparison(
            project_id, version_id, request.vc_slugs
        )
        pending = [
            row
            for row in comparison.assessments
            if row.status != "complete"
            and not self.coordinator.is_busy(row.assessment_id)
        ]
        if pending and not request.authorize_provider_cost:
            raise ValueError(
                "provider cost authorization is required for missing assessments"
            )
        for row in pending:
            self.coordinator.submit(
                row.assessment_id,
                "canonical_assessment",
                lambda emit, assessment_id=row.assessment_id: self.assessment_service.run_assessment(
                    assessment_id, emit=emit
                ),
            )
        return self.matching_service.get_comparison(project_id, version_id)

    def get_assessment(self, assessment_id: str):
        return self.assessment_service.get_assessment(assessment_id)

    def list_assessments(self, project_id: str, version_id: str):
        return {
            "schema": "vc-clone-canonical-assessment-list-v1",
            "assessments": self.assessment_service.list_for_version(
                project_id, version_id
            ),
        }

    def start_match(
        self, project_id: str, version_id: str, request: CreateMatchRequest
    ) -> MatchJobResponse:
        for vc_slug in request.vc_slugs:
            self._validate_vc(vc_slug)
        match = self.matching_service.create_match(project_id, version_id, request.vc_slugs)
        self.coordinator.submit(
            match.match_id,
            "investor_match",
            lambda emit: self.matching_service.run_match(match.match_id, emit=emit),
        )
        return MatchJobResponse(
            match_id=match.match_id,
            status="queued",
            event_url=f"/api/matches/{match.match_id}/events",
        )

    def get_match(self, match_id: str):
        return self.matching_service.get_match(match_id)

    def list_matches(self, project_id: str, version_id: str):
        return {
            "schema": "vc-clone-investor-match-list-v1",
            "matches": self.matching_service.list_for_version(project_id, version_id),
        }

    def retry_match(self, match_id: str, vc_slug: str):
        return self.matching_service.retry(match_id, vc_slug)

    def project_events(self, job_id: str, after: int = 0) -> Iterator[PublicEvent]:
        return self.coordinator.stream(job_id, after=after)

    def list_sessions(self) -> SessionListResponse:
        return SessionListResponse(sessions=list_sessions(self.output_root))

    def get_session(self, session_id: str) -> SessionDetailResponse:
        view = SessionViewBuilder(self._store(session_id)).build()
        return view.model_copy(
            update={"operation_active": self.coordinator.is_busy(session_id)}
        )

    def _resume(self, session_id: str, action: str, text: str | None = None) -> JobResponse:
        self._root(session_id)

        def run(emit):
            emit("rehearsal_running", {"action": action})
            with redirect_stdout(StringIO()):
                rehearsal_cli._resume(
                    self.config,
                    session_id,
                    action,
                    text,
                    progress_callback=emit,
                )
            view = self.get_session(session_id)
            emit(view.status, {"decision": view.current_assessment.decision if view.current_assessment else None})
            return view

        self.coordinator.submit(session_id, action, run)
        return self._job(session_id)

    def answer(self, session_id: str, text: str) -> JobResponse:
        if self.coordinator.is_busy(session_id):
            raise SessionBusyError(f"session mutation already active: {session_id}")
        store = self._store(session_id)
        state = store.read_json("state.json")
        question = state.get("current_question")
        if not isinstance(question, dict) or not question.get("question_id"):
            raise ValueError("session is not awaiting a founder answer")
        store.accept_answer_submission(str(question["question_id"]), text)
        return self._resume(session_id, "answer", text)

    def finish(self, session_id: str) -> JobResponse:
        return self._resume(session_id, "finish")

    def retry(self, session_id: str) -> JobResponse:
        return self._resume(session_id, "retry")

    def events(self, session_id: str, after: int = 0) -> Iterator[PublicEvent]:
        if not self.coordinator.events(session_id) and not self.coordinator.is_busy(session_id):
            self._root(session_id)
        return self.coordinator.stream(session_id, after=after)

    def report(self, session_id: str) -> dict[str, Any]:
        store = self._store(session_id)
        report_path = store.session_root / "founder-report.json"
        if report_path.is_file():
            return store.read_json("founder-report.json")
        return SessionViewBuilder(store).build().model_dump(by_alias=True, mode="json")

    def verify(self, session_id: str) -> dict[str, object]:
        return self._store(session_id).verify()

    def export(self, session_id: str) -> bytes:
        store = self._store(session_id)
        verification = store.verify()
        public_view = SessionViewBuilder(store).build().model_dump(
            by_alias=True, mode="json"
        )
        report = self.report(session_id)
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("pitch.txt", store.pitch_path.read_text(encoding="utf-8"))
            archive.writestr("session.json", json.dumps(public_view, indent=2) + "\n")
            archive.writestr("report.json", json.dumps(report, indent=2) + "\n")
            archive.writestr(
                "verification.json", json.dumps(verification, indent=2) + "\n"
            )
        return buffer.getvalue()
