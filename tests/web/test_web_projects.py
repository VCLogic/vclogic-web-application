from __future__ import annotations

from fastapi.testclient import TestClient

from vclogic_web.app import create_app
from vclogic_web.models import (
    CanonicalAssessmentDetail,
    MatchRunDetail,
    PitchProjectDetail,
    PitchProjectListResponse,
    PitchProjectSummary,
    PitchVersionView,
    RelativeFitView,
    InvestorComparisonDetail,
)


VERSION = PitchVersionView(
    version_id="version-1",
    project_id="project-1",
    created_at="2026-09-01T00:00:00Z",
    pitch_sha256="a" * 64,
    character_count=12,
)
PROJECT = PitchProjectDetail(
    project_id="project-1",
    display_name="ShiftPilot",
    company_aliases=("ShiftPilot",),
    created_at="2026-09-01T00:00:00Z",
    updated_at="2026-09-01T00:00:00Z",
    current_version_id="version-1",
    version_count=1,
    versions=(VERSION,),
)


class FakeProjectService:
    def __init__(self):
        self.assessment_requests = []
        self.match_requests = []

    def list_projects(self):
        return PitchProjectListResponse(
            projects=(PitchProjectSummary(**PROJECT.model_dump(exclude={"schema_version", "versions"})),)
        )

    def create_project(self, request):
        return PROJECT

    def get_project(self, project_id):
        if project_id != "project-1":
            raise ValueError("unknown pitch project")
        return PROJECT

    def create_version(self, project_id, request):
        return VERSION

    def get_version(self, project_id, version_id):
        return {**VERSION.model_dump(by_alias=True), "pitch_text": "# ShiftPilot\n"}

    def start_assessment(self, project_id, version_id, request):
        self.assessment_requests.append((project_id, version_id, request))
        return {"schema": "vc-clone-assessment-job-v1", "assessment_id": "assessment-1", "status": "queued", "event_url": "/api/assessments/assessment-1/events"}

    def get_assessment(self, assessment_id):
        return CanonicalAssessmentDetail(
            assessment_id=assessment_id,
            project_id="project-1",
            version_id="version-1",
            vc_slug="elizabeth-yin-hustle-fund",
            pitch_sha256="a" * 64,
            status="complete",
            created_at="2026-09-01T00:00:00Z",
            updated_at="2026-09-01T00:00:00Z",
            decision="In",
            investment_likelihood=0.63,
            decision_confidence=0.7,
        )

    def list_assessments(self, project_id, version_id):
        return {"assessments": [self.get_assessment("assessment-1")]}

    def start_match(self, project_id, version_id, request):
        self.match_requests.append((project_id, version_id, request))
        return {"schema": "vc-clone-match-job-v1", "match_id": "match-1", "status": "queued", "event_url": "/api/matches/match-1/events"}

    def get_match(self, match_id):
        return MatchRunDetail(
            match_id=match_id,
            project_id="project-1",
            version_id="version-1",
            selected_vc_slugs=("elizabeth-yin-hustle-fund", "phil-nadel"),
            status="running",
            created_at="2026-09-01T00:00:00Z",
            updated_at="2026-09-01T00:00:00Z",
            assessments=(),
        )

    def list_matches(self, project_id, version_id):
        return {"matches": [self.get_match("match-1")]}

    def get_comparison(self, project_id, version_id):
        return InvestorComparisonDetail(
            comparison_id="comparison-version-1",
            project_id=project_id,
            version_id=version_id,
            selected_vc_slugs=("elizabeth-yin-hustle-fund",),
            status="complete",
            created_at="2026-09-01T00:00:00Z",
            updated_at="2026-09-01T00:00:00Z",
            assessments=(),
        )

    def update_comparison(self, project_id, version_id, request):
        self.match_requests.append((project_id, version_id, request))
        return self.get_comparison(project_id, version_id)

    def retry_match(self, match_id, vc_slug):
        return self.get_match(match_id)

    def project_events(self, job_id, after=0):
        return iter(())

    def create_rehearsal_from_assessment(self, assessment_id, rehearsal_depth):
        return {"schema": "vc-clone-job-v1", "session_id": "session-1", "status": "queued", "event_url": "/api/sessions/session-1/events"}


def test_project_and_version_routes_are_additive() -> None:
    client = TestClient(create_app(testing=True, rehearsal_service=FakeProjectService()))

    created = client.post(
        "/api/projects",
        json={"display_name": "ShiftPilot", "company_aliases": ["ShiftPilot"], "pitch_text": "# ShiftPilot"},
    )
    listing = client.get("/api/projects")
    version = client.get("/api/projects/project-1/versions/version-1")
    assessments = client.get("/api/projects/project-1/versions/version-1/assessments")
    matches = client.get("/api/projects/project-1/versions/version-1/matches")
    comparison = client.get("/api/projects/project-1/versions/version-1/comparison")

    assert created.status_code == 201
    assert listing.json()["projects"][0]["display_name"] == "ShiftPilot"
    assert version.json()["pitch_text"] == "# ShiftPilot\n"
    assert assessments.json()["assessments"][0]["assessment_id"] == "assessment-1"
    assert matches.json()["matches"][0]["match_id"] == "match-1"
    assert comparison.json()["comparison_id"] == "comparison-version-1"


def test_assessment_match_and_rehearsal_routes_require_cost_authorization() -> None:
    service = FakeProjectService()
    client = TestClient(create_app(testing=True, rehearsal_service=service))

    assessment = client.post(
        "/api/projects/project-1/versions/version-1/assessments",
        json={"vc_slug": "elizabeth-yin-hustle-fund", "authorize_provider_cost": True},
    )
    match = client.post(
        "/api/projects/project-1/versions/version-1/matches",
        json={"vc_slugs": ["elizabeth-yin-hustle-fund", "phil-nadel"], "authorize_provider_cost": True},
    )
    rehearsal = client.post(
        "/api/assessments/assessment-1/rehearsals",
        json={"rehearsal_depth": "quick"},
    )

    assert assessment.status_code == 202
    assert match.status_code == 202
    assert rehearsal.status_code == 202
    assert service.assessment_requests[0][2].authorize_provider_cost is True


def test_comparison_route_accepts_one_or_more_profiles() -> None:
    service = FakeProjectService()
    client = TestClient(create_app(testing=True, rehearsal_service=service))

    response = client.post(
        "/api/projects/project-1/versions/version-1/comparison",
        json={"vc_slugs": ["elizabeth-yin-hustle-fund"], "authorize_provider_cost": True},
    )

    assert response.status_code == 202
    assert response.json()["comparison_id"] == "comparison-version-1"
    assert service.match_requests[-1][2].vc_slugs == ("elizabeth-yin-hustle-fund",)


def test_duplicate_match_profiles_and_missing_authorization_are_rejected() -> None:
    client = TestClient(create_app(testing=True, rehearsal_service=FakeProjectService()))

    duplicate = client.post(
        "/api/projects/project-1/versions/version-1/matches",
        json={"vc_slugs": ["phil-nadel", "phil-nadel"], "authorize_provider_cost": True},
    )
    unauthorized = client.post(
        "/api/projects/project-1/versions/version-1/assessments",
        json={"vc_slug": "phil-nadel", "authorize_provider_cost": False},
    )

    assert duplicate.status_code == 422
    assert unauthorized.status_code == 422
