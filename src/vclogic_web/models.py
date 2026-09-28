"""Versioned public schemas for the local founder-rehearsal web API."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class CreateSessionRequest(PublicModel):
    investor_version_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    vc_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    company_aliases: tuple[str, ...] = Field(min_length=1, max_length=8)
    pitch_text: str = Field(min_length=1, max_length=200_000)
    authorize_provider_cost: Literal[True]
    rehearsal_depth: Literal["quick", "standard", "deep"] = "standard"

    @field_validator("company_aliases")
    @classmethod
    def normalize_aliases(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not normalized:
            raise ValueError("at least one company alias is required")
        return normalized

    @field_validator("pitch_text")
    @classmethod
    def normalize_pitch(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("pitch text must not be blank")
        return text + "\n"


class AnswerRequest(PublicModel):
    text: str = Field(min_length=1, max_length=20_000)

    @field_validator("text")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("answer must not be blank")
        return text


class ApiError(PublicModel):
    schema_version: Literal["vc-clone-web-error-v1"] = Field(
        default="vc-clone-web-error-v1", alias="schema"
    )
    code: str
    message: str
    recoverable: bool = False
    session_id: str | None = None


class InvestorCard(PublicModel):
    investor_version_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    vc_slug: str
    display_name: str
    firm: str
    role: str
    disclosure: str
    start_available: bool = True
    summary: str | None = None
    evidence_coverage: float | None = Field(default=None, ge=0, le=1)
    portrait_path: str | None = None
    portrait_alt: str | None = None
    source_profile_url: str | None = None
    photo_attribution: str | None = None
    recurring_positive_rationales: tuple[str, ...] = ()
    recurring_negative_rationales: tuple[str, ...] = ()
    recurring_unresolved_rationales: tuple[str, ...] = ()
    recurring_positive_counts: dict[str, int] = Field(default_factory=dict)
    recurring_negative_counts: dict[str, int] = Field(default_factory=dict)
    recurring_unresolved_counts: dict[str, int] = Field(default_factory=dict)


class InvestorListResponse(PublicModel):
    schema_version: Literal["vc-clone-investor-list-v1"] = Field(
        default="vc-clone-investor-list-v1", alias="schema"
    )
    investors: tuple[InvestorCard, ...]


class ProfileSection(PublicModel):
    section_id: str
    title: str
    body: str
    preview: str = ""
    character_count: int = Field(default=0, ge=0)
    source_paths: tuple[str, ...] = ()


class InvestorProfileResponse(PublicModel):
    schema_version: Literal["vc-clone-investor-profile-v1"] = Field(
        default="vc-clone-investor-profile-v1", alias="schema"
    )
    investor: InvestorCard
    sections: tuple[ProfileSection, ...]


class MemorySearchResponse(PublicModel):
    schema_version: Literal["vc-clone-memory-search-v1"] = Field(
        default="vc-clone-memory-search-v1", alias="schema"
    )
    query: str
    results: tuple["EvidenceView", ...]
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=5, ge=1, le=20)
    total_results: int = Field(default=0, ge=0)
    total_pages: int = Field(default=0, ge=0)


class EvidenceView(PublicModel):
    evidence_id: str
    source_kind: str
    source_path: str
    excerpt: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_title: str | None = None
    rationale_label: str | None = None
    direction: Literal[
        "positive", "negative", "neutral", "mixed", "unresolved"
    ] | None = None
    source_reference: str | None = None


class RationaleNodeView(PublicModel):
    node_id: str
    taxonomy_label: str
    title: str
    direction: Literal["positive", "negative", "neutral", "mixed", "unresolved"]
    salience: Literal["primary", "secondary", "unresolved"] = "unresolved"
    confidence: float = Field(ge=0, le=1)
    evidence_ids: tuple[str, ...] = ()
    initial_direction: str | None = None
    initial_confidence: float | None = Field(default=None, ge=0, le=1)
    definition: str | None = None
    coarse_parent: str | None = None
    occurrence_count: int | None = Field(default=None, ge=0)
    investigation_count: int | None = Field(default=None, ge=0)
    direction_counts: dict[str, int] = Field(default_factory=dict)
    weighted_degree: int | None = Field(default=None, ge=0)


class RationaleEdgeView(PublicModel):
    edge_id: str
    source: str
    target: str
    relationship: Literal["co_occurs_with", "conditions", "overrides", "constrains", "supports"]
    inference_status: Literal["explicit", "observed_cooccurrence", "artifact_link"]
    evidence_ids: tuple[str, ...] = ()
    occurrence_count: int | None = Field(default=None, ge=0)


class RationaleGraphResponse(PublicModel):
    schema_version: Literal["vc-clone-rationale-graph-v1"] = Field(
        default="vc-clone-rationale-graph-v1", alias="schema"
    )
    nodes: tuple[RationaleNodeView, ...]
    edges: tuple[RationaleEdgeView, ...]
    evidence_status: Literal["available", "not_prepared", "invalid"] | None = None
    evidence_note: str | None = None


class AssessmentView(PublicModel):
    decision: Literal["In", "Out"]
    investment_likelihood: float = Field(ge=0, le=1)
    decision_confidence: float = Field(ge=0, le=1)
    review_priority_score: float | None = Field(default=None, ge=0, le=1)
    rationale_counts: dict[str, int] = Field(default_factory=dict)
    decision_justification: str | None = None
    score_reconciliation: str | None = None


class PitchAnnotationView(PublicModel):
    annotation_id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str
    direction: Literal["positive", "negative", "neutral", "unresolved"]
    rationale_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


class QuestionView(PublicModel):
    question_id: str
    text: str
    rationale_labels: tuple[str, ...] = ()
    decision_relevance: str | None = None
    response_comment: str | None = None


class ConversationTurnView(PublicModel):
    question_id: str
    question: str
    response_comment: str | None = None
    rationale_labels: tuple[str, ...] = ()
    founder_answer: str | None = None
    answer_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evidence_effect: Literal[
        "new_positive",
        "new_negative",
        "clarification",
        "unresolved",
        "contradiction",
    ] | None = None
    investment_likelihood_before: float | None = Field(default=None, ge=0, le=1)
    investment_likelihood_after: float | None = Field(default=None, ge=0, le=1)
    likelihood_delta: float | None = Field(default=None, ge=-1, le=1)


class LikelihoodTimelineView(PublicModel):
    turn: int = Field(ge=0)
    label: str
    evidence_effect: Literal[
        "baseline",
        "new_positive",
        "new_negative",
        "clarification",
        "unresolved",
        "contradiction",
        "synthesis",
    ]
    before: float = Field(ge=0, le=1)
    after: float = Field(ge=0, le=1)
    delta: float = Field(ge=-1, le=1)
    answer_excerpt: str | None = None


class DecisionPathView(PublicModel):
    path_id: str
    evidence_id: str
    evidence_origin: Literal["pitch", "founder_answer"]
    evidence_excerpt: str
    rationale_id: str
    rationale_label: str
    direction: Literal["positive", "negative", "unresolved"]
    contribution: str
    baseline_or_rehearsal: Literal["baseline", "rehearsal"]
    supporting_evidence_ids: tuple[str, ...] = ()


class AgentActivityView(PublicModel):
    activity_id: str
    phase: Literal["phase1", "phase2"]
    iteration: int = Field(ge=1)
    kind: Literal["plan", "investigation", "decision"]
    status: Literal["complete", "failed"]
    title: str
    text: str
    details: tuple[str, ...] = ()
    elapsed_seconds: float | None = Field(default=None, ge=0)


class JobResponse(PublicModel):
    schema_version: Literal["vc-clone-job-v1"] = Field(
        default="vc-clone-job-v1", alias="schema"
    )
    session_id: str
    status: str
    event_url: str


class SessionSummary(PublicModel):
    investor_version_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    session_id: str
    vc_slug: str
    investor_display_name: str
    company_aliases: tuple[str, ...]
    status: str
    created_at: str
    initial_decision: Literal["In", "Out"] | None = None
    initial_likelihood: float | None = Field(default=None, ge=0, le=1)
    current_decision: Literal["In", "Out"] | None = None
    current_likelihood: float | None = Field(default=None, ge=0, le=1)
    cost_usd: float | None = Field(default=None, ge=0)
    verification_status: Literal["verified", "verification_failed"]


class SessionListResponse(PublicModel):
    schema_version: Literal["vc-clone-session-list-v1"] = Field(
        default="vc-clone-session-list-v1", alias="schema"
    )
    sessions: tuple[SessionSummary, ...]


class SessionDetailResponse(PublicModel):
    investor_version_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    schema_version: Literal["vc-clone-session-detail-v1"] = Field(
        default="vc-clone-session-detail-v1", alias="schema"
    )
    session_id: str
    vc_slug: str
    investor_display_name: str
    disclosure: str
    status: str
    operation_active: bool = False
    pitch_text: str
    pitch_sha256: str
    initial_assessment: AssessmentView | None = None
    current_assessment: AssessmentView | None = None
    active_question: QuestionView | None = None
    conversation: tuple[ConversationTurnView, ...] = ()
    likelihood_timeline: tuple[LikelihoodTimelineView, ...] = ()
    decision_path: tuple[DecisionPathView, ...] = ()
    rehearsal_depth: Literal["quick", "standard", "deep"] = "standard"
    max_questions: int = Field(default=4, ge=1)
    closing_message: str | None = None
    agent_activity: tuple[AgentActivityView, ...] = ()
    turns: tuple[dict[str, Any], ...] = ()
    annotations: tuple[PitchAnnotationView, ...] = ()
    rationale_graph: RationaleGraphResponse | None = None
    evidence: tuple[EvidenceView, ...] = ()
    usage: dict[str, int | float] = Field(default_factory=dict)
    findings: tuple[str, ...] = ()


class PitchVersionView(PublicModel):
    schema_version: Literal["vc-clone-pitch-version-v1"] = Field(
        default="vc-clone-pitch-version-v1", alias="schema"
    )
    version_id: str
    project_id: str
    created_at: str
    pitch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    character_count: int = Field(ge=1)


class PitchProjectSummary(PublicModel):
    project_id: str
    display_name: str
    company_aliases: tuple[str, ...]
    created_at: str
    updated_at: str
    current_version_id: str
    version_count: int = Field(ge=1)
    assessment_count: int = Field(default=0, ge=0)
    rehearsal_count: int = Field(default=0, ge=0)


class PitchProjectDetail(PitchProjectSummary):
    schema_version: Literal["vc-clone-pitch-project-v1"] = Field(
        default="vc-clone-pitch-project-v1", alias="schema"
    )
    versions: tuple[PitchVersionView, ...]


class PitchProjectListResponse(PublicModel):
    schema_version: Literal["vc-clone-pitch-project-list-v1"] = Field(
        default="vc-clone-pitch-project-list-v1", alias="schema"
    )
    projects: tuple[PitchProjectSummary, ...]


class CreatePitchProjectRequest(PublicModel):
    display_name: str = Field(min_length=1, max_length=200)
    company_aliases: tuple[str, ...] = Field(min_length=1, max_length=8)
    pitch_text: str = Field(min_length=1, max_length=200_000)

    @field_validator("display_name", "pitch_text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("company_aliases")
    @classmethod
    def normalize_project_aliases(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        aliases = tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not aliases:
            raise ValueError("at least one company alias is required")
        return aliases


class CreatePitchVersionRequest(PublicModel):
    pitch_text: str = Field(min_length=1, max_length=200_000)

    @field_validator("pitch_text")
    @classmethod
    def normalize_version_pitch(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("pitch text must not be blank")
        return normalized


class PitchVersionDetail(PitchVersionView):
    pitch_text: str


class AssessmentActivityView(PublicModel):
    stage: str
    title: str
    detail: str
    status: Literal["pending", "active", "complete", "failed"]
    timestamp: str | None = None


class AssessmentCitationView(PublicModel):
    number: int = Field(ge=1)
    reference_id: str
    source_type: Literal[
        "pitch", "investment_memory", "precedent", "rationale", "unavailable"
    ]
    title: str
    excerpt: str | None = None
    source_reference: str | None = None
    episode_slug: str | None = None
    decision_status: str | None = None
    rationale_labels: tuple[str, ...] = ()


class CanonicalAssessmentDetail(PublicModel):
    investor_version_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    schema_version: Literal["vc-clone-canonical-assessment-v1"] = Field(
        default="vc-clone-canonical-assessment-v1", alias="schema"
    )
    assessment_id: str
    project_id: str
    version_id: str
    vc_slug: str
    pitch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["queued", "running", "complete", "failed"]
    created_at: str
    updated_at: str
    canonical_run_path: str | None = None
    contract_version: str | None = None
    phase1_status: str | None = None
    phase2_status: str | None = None
    decision: Literal["In", "Out"] | None = None
    investment_likelihood: float | None = Field(default=None, ge=0, le=1)
    decision_confidence: float | None = Field(default=None, ge=0, le=1)
    review_priority_score: float | None = Field(default=None, ge=0, le=1)
    decision_justification: str | None = None
    positive_rationales: tuple[str, ...] = ()
    negative_rationales: tuple[str, ...] = ()
    unresolved_rationales: tuple[str, ...] = ()
    usage: dict[str, int | float] = Field(default_factory=dict)
    public_error: str | None = None
    rehearsal_session_ids: tuple[str, ...] = ()
    decision_summary: str | None = None
    citations: tuple[AssessmentCitationView, ...] = ()
    activity: tuple[AssessmentActivityView, ...] = ()


class CreateCanonicalAssessmentRequest(PublicModel):
    investor_version_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    vc_slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    authorize_provider_cost: Literal[True]


class CreateMatchRequest(PublicModel):
    investor_versions: dict[str, Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]] = Field(default_factory=dict)
    vc_slugs: tuple[str, ...] = Field(min_length=2, max_length=6)
    authorize_provider_cost: Literal[True]

    @field_validator("vc_slugs")
    @classmethod
    def require_distinct_profiles(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("investor profiles must be distinct")
        return values


class CreateAssessmentRehearsalRequest(PublicModel):
    rehearsal_depth: Literal["quick", "standard", "deep"] = "standard"


class AssessmentJobResponse(PublicModel):
    schema_version: Literal["vc-clone-assessment-job-v1"] = Field(
        default="vc-clone-assessment-job-v1", alias="schema"
    )
    assessment_id: str
    status: str
    event_url: str


class MatchJobResponse(PublicModel):
    schema_version: Literal["vc-clone-match-job-v1"] = Field(
        default="vc-clone-match-job-v1", alias="schema"
    )
    match_id: str
    status: str
    event_url: str


class RelativeFitView(PublicModel):
    percentile: float | None = Field(default=None, ge=0, le=100)
    reference_count: int = Field(ge=0)


class MatchAssessmentRow(PublicModel):
    investor_version_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    assessment_id: str
    vc_slug: str
    status: Literal["queued", "running", "complete", "failed"]
    decision: Literal["In", "Out"] | None = None
    investment_likelihood: float | None = Field(default=None, ge=0, le=1)
    decision_confidence: float | None = Field(default=None, ge=0, le=1)
    positive_rationales: tuple[str, ...] = ()
    negative_rationales: tuple[str, ...] = ()
    unresolved_rationales: tuple[str, ...] = ()
    relative_fit: RelativeFitView
    highest_estimated_fit: bool = False
    leading_group: bool = False
    public_error: str | None = None
    reused: bool = False


class MatchRunDetail(PublicModel):
    schema_version: Literal["vc-clone-investor-match-v1"] = Field(
        default="vc-clone-investor-match-v1", alias="schema"
    )
    match_id: str
    project_id: str
    version_id: str
    selected_vc_slugs: tuple[str, ...] = Field(min_length=2, max_length=6)
    status: Literal["queued", "running", "complete", "partial", "failed"]
    created_at: str
    updated_at: str
    assessments: tuple[MatchAssessmentRow, ...]


class InvestorComparisonDetail(PublicModel):
    schema_version: Literal["vc-clone-investor-comparison-v1"] = Field(
        default="vc-clone-investor-comparison-v1", alias="schema"
    )
    comparison_id: str
    project_id: str
    version_id: str
    selected_vc_slugs: tuple[str, ...] = Field(min_length=1, max_length=6)
    status: Literal["queued", "running", "complete", "partial", "failed"]
    created_at: str
    updated_at: str
    missing_vc_slugs: tuple[str, ...] = ()
    assessments: tuple[MatchAssessmentRow, ...]


class UpdateComparisonRequest(PublicModel):
    investor_versions: dict[str, Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]] = Field(default_factory=dict)
    vc_slugs: tuple[str, ...] = Field(min_length=1, max_length=6)
    authorize_provider_cost: bool = False

    @field_validator("vc_slugs")
    @classmethod
    def require_distinct_comparison_profiles(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("investor profiles must be distinct")
        return values


class PublicEvent(PublicModel):
    schema_version: Literal["vc-clone-public-event-v1"] = Field(
        default="vc-clone-public-event-v1", alias="schema"
    )
    event_id: int = Field(ge=1)
    session_id: str
    stage: str
    payload: dict[str, Any] = Field(default_factory=dict)


class UpdateInvestorSettings(PublicModel):
    enabled: bool
    active_version: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
