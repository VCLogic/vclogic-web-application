"""FastAPI application factory for the local founder-rehearsal UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from vc_clone_graph.rehearsal_artifacts import PendingAnswerConflict
from .jobs import SessionBusyError
from .models import (
    AnswerRequest,
    UpdateInvestorSettings,
    ApiError,
    CreateSessionRequest,
    InvestorListResponse,
    CreatePitchProjectRequest,
    CreatePitchVersionRequest,
    CreateCanonicalAssessmentRequest,
    CreateMatchRequest,
    UpdateComparisonRequest,
    CreateAssessmentRehearsalRequest,
)
from .profiles import ProfileService
from .investor_catalog import InvestorCatalog
from .catalog_profiles import CatalogProfiles
from vc_clone_graph.rehearsal_config import load_rehearsal_config
from .service import RehearsalWebService


def create_app(
    *,
    testing: bool = False,
    investor_catalog: InvestorCatalog | None = None,
    investor_bundle_roots: list[Path] | None = None,
    profile_service: ProfileService | None = None,
    rehearsal_service: RehearsalWebService | None = None,
    rehearsal_config: Path | None = None,
    static_root: Path | None = None,
    pipeline_workspace: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="VC Rehearsal", version="0.1.0")
    app.state.testing = testing
    workspace = (pipeline_workspace or Path.cwd()).resolve()
    profile_backend = profile_service
    session_backend = rehearsal_service
    if investor_catalog is None and not testing:
        config_path = workspace / (rehearsal_config or Path("configs/rehearsal-charles-v41-grounded.toml"))
        investor_catalog = InvestorCatalog(workspace=workspace,
            config=load_rehearsal_config(config_path, workspace=workspace), bundle_roots=investor_bundle_roots)
    if profile_backend is None and investor_catalog is not None:
        profile_backend = CatalogProfiles(investor_catalog)
    if session_backend is None and not testing:
        session_backend = RehearsalWebService(
            workspace / (rehearsal_config or Path("configs/rehearsal-charles-v41-grounded.toml")),
            workspace=workspace,
            investor_catalog=investor_catalog,
        )

    def catalog() -> InvestorCatalog:
        if investor_catalog is None:
            raise HTTPException(status_code=503, detail="investor settings unavailable")
        return investor_catalog

    @app.get("/api/settings/investors")
    def investor_settings():
        return catalog().settings()

    @app.post("/api/settings/investors/refresh")
    def refresh_investors():
        return catalog().refresh()

    @app.put("/api/settings/investors/{vc_slug}")
    def update_investor(vc_slug: str, request: UpdateInvestorSettings):
        try:
            return catalog().update(vc_slug, enabled=request.enabled, active_version=request.active_version)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"schema": "vc-clone-web-health-v1", "status": "ok"}

    def profiles() -> ProfileService:
        if profile_backend is None:
            raise HTTPException(status_code=503, detail="profile service unavailable")
        return profile_backend

    def sessions() -> RehearsalWebService:
        if session_backend is None:
            raise HTTPException(status_code=503, detail="rehearsal service unavailable")
        return session_backend

    def _event_stream(events):
        def encode():
            for event in events:
                yield (
                    f"id: {event.event_id}\nevent: {event.stage}\n"
                    f"data: {event.model_dump_json(by_alias=True)}\n\n"
                )

        return StreamingResponse(encode(), media_type="text/event-stream")

    @app.exception_handler(SessionBusyError)
    async def busy_session(_request: Request, exc: SessionBusyError) -> JSONResponse:
        session_id = str(exc).rsplit(":", maxsplit=1)[-1].strip()
        payload = ApiError(
            code="session_busy",
            message=str(exc),
            recoverable=True,
            session_id=session_id,
        )
        return JSONResponse(status_code=409, content=payload.model_dump(by_alias=True))

    @app.exception_handler(PendingAnswerConflict)
    async def pending_answer_conflict(
        _request: Request, exc: PendingAnswerConflict
    ) -> JSONResponse:
        payload = ApiError(
            code="answer_conflict",
            message=str(exc),
            recoverable=True,
        )
        return JSONResponse(
            status_code=409, content=payload.model_dump(by_alias=True)
        )

    @app.get("/api/investors", response_model=InvestorListResponse)
    def investors() -> InvestorListResponse:
        return InvestorListResponse(investors=profiles().list_profiles())

    @app.get("/api/investors/{vc_slug}")
    def investor(vc_slug: str):
        try:
            return profiles().profile(vc_slug)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/investors/{vc_slug}/memory/search")
    def memory_search(
        vc_slug: str,
        q: str = Query(min_length=2, max_length=200),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=5, ge=1, le=20),
    ):
        try:
            return profiles().search_memory(
                vc_slug, q, page=page, page_size=page_size
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/investors/{vc_slug}/rationale-graph")
    def rationale_graph(vc_slug: str):
        try:
            return profiles().rationale_graph(vc_slug)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/sessions")
    def rehearsal_sessions():
        return sessions().list_sessions()

    @app.get("/api/projects")
    def pitch_projects():
        return sessions().list_projects()

    @app.post("/api/projects", status_code=201)
    def create_pitch_project(request: CreatePitchProjectRequest):
        return sessions().create_project(request)

    @app.get("/api/projects/{project_id}")
    def pitch_project(project_id: str):
        try:
            return sessions().get_project(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/versions", status_code=201)
    def create_pitch_version(project_id: str, request: CreatePitchVersionRequest):
        try:
            return sessions().create_version(project_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/versions/{version_id}")
    def pitch_version(project_id: str, version_id: str):
        try:
            return sessions().get_version(project_id, version_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/projects/{project_id}/versions/{version_id}/assessments",
        status_code=202,
    )
    def start_project_assessment(
        project_id: str, version_id: str, request: CreateCanonicalAssessmentRequest
    ):
        try:
            return sessions().start_assessment(project_id, version_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/assessments/{assessment_id}")
    def project_assessment(assessment_id: str):
        try:
            return sessions().get_assessment(assessment_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/versions/{version_id}/assessments")
    def project_assessments(project_id: str, version_id: str):
        try:
            return sessions().list_assessments(project_id, version_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/assessments/{assessment_id}/events")
    def assessment_events(assessment_id: str, after: int = Query(default=0, ge=0)):
        return _event_stream(sessions().project_events(assessment_id, after))

    @app.post("/api/assessments/{assessment_id}/rehearsals", status_code=202)
    def start_assessment_rehearsal(
        assessment_id: str, request: CreateAssessmentRehearsalRequest
    ):
        try:
            return sessions().create_rehearsal_from_assessment(
                assessment_id, request.rehearsal_depth
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/projects/{project_id}/versions/{version_id}/matches", status_code=202
    )
    def start_investor_match(
        project_id: str, version_id: str, request: CreateMatchRequest
    ):
        try:
            return sessions().start_match(project_id, version_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/matches/{match_id}")
    def investor_match(match_id: str):
        try:
            return sessions().get_match(match_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/versions/{version_id}/matches")
    def project_matches(project_id: str, version_id: str):
        try:
            return sessions().list_matches(project_id, version_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/versions/{version_id}/comparison")
    def project_comparison(project_id: str, version_id: str):
        try:
            comparison = sessions().get_comparison(project_id, version_id)
            if comparison is None:
                raise HTTPException(status_code=404, detail="comparison has not been created")
            return comparison
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/projects/{project_id}/versions/{version_id}/comparison",
        status_code=202,
    )
    def update_project_comparison(
        project_id: str, version_id: str, request: UpdateComparisonRequest
    ):
        try:
            return sessions().update_comparison(project_id, version_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/matches/{match_id}/events")
    def match_events(match_id: str, after: int = Query(default=0, ge=0)):
        return _event_stream(sessions().project_events(match_id, after))

    @app.post("/api/matches/{match_id}/retry/{vc_slug}")
    def retry_investor_match(match_id: str, vc_slug: str):
        try:
            return sessions().retry_match(match_id, vc_slug)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/sessions", status_code=202)
    def create_session(request: CreateSessionRequest):
        try:
            return sessions().create_session(request)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}")
    def session(session_id: str):
        try:
            return sessions().get_session(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}/events")
    def session_events(session_id: str, after: int = Query(default=0, ge=0)):
        try:
            events = sessions().events(session_id, after)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        def encode():
            for event in events:
                yield f"id: {event.event_id}\nevent: {event.stage}\ndata: {event.model_dump_json(by_alias=True)}\n\n"

        return StreamingResponse(encode(), media_type="text/event-stream")

    @app.post("/api/sessions/{session_id}/answers", status_code=202)
    def answer(session_id: str, request: AnswerRequest):
        try:
            return sessions().answer(session_id, request.text)
        except PendingAnswerConflict:
            raise
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/finish", status_code=202)
    def finish(session_id: str):
        try:
            return sessions().finish(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/retry", status_code=202)
    def retry(session_id: str):
        try:
            return sessions().retry(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}/report")
    def report(session_id: str):
        try:
            return sessions().report(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}/export")
    def export(session_id: str):
        try:
            content = sessions().export(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content=content,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{session_id}.zip"'},
        )

    @app.post("/api/sessions/{session_id}/verify")
    def verify(session_id: str):
        try:
            return sessions().verify(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    if static_root is not None:
        frontend = Path(static_root).resolve()

        @app.get("/{path:path}", include_in_schema=False)
        def frontend_route(path: str):
            if path == "api" or path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            candidate = (frontend / path).resolve()
            if path and candidate.is_relative_to(frontend) and candidate.is_file():
                return FileResponse(candidate)
            index = frontend / "index.html"
            if not index.is_file():
                raise HTTPException(status_code=404, detail="frontend not built")
            return FileResponse(index)

    return app
