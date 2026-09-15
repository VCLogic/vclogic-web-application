from __future__ import annotations

import pytest

from vclogic_web.matching import MatchingService, relative_fit
from vclogic_web.models import CanonicalAssessmentDetail
from vclogic_web.project_store import PitchProjectStore


def _assessment(assessment_id: str, vc_slug: str, likelihood: float, status="complete"):
    return CanonicalAssessmentDetail(
        assessment_id=assessment_id,
        project_id="00000000-0000-0000-0000-000000000001",
        version_id="00000000-0000-0000-0000-000000000002",
        vc_slug=vc_slug,
        pitch_sha256="a" * 64,
        status=status,
        created_at="2026-09-01T00:00:00Z",
        updated_at="2026-09-01T00:00:00Z",
        decision="In" if likelihood >= 0.5 else "Out",
        investment_likelihood=likelihood,
        decision_confidence=0.7,
        positive_rationales=("founder_market_fit",),
        negative_rationales=("traction_repeatability_concern",),
    )


class FakeAssessments:
    def __init__(self, rows):
        self.rows = {row.vc_slug: row for row in rows}
        self.by_id = {row.assessment_id: row for row in rows}
        self.fail = set()

    def ensure_assessment(self, _project_id, _version_id, vc_slug):
        return self.rows[vc_slug]

    def run_assessment(self, assessment_id, emit=None):
        row = self.by_id[assessment_id]
        if row.vc_slug in self.fail:
            self.by_id[assessment_id] = row.model_copy(
                update={"status": "failed", "public_error": "provider timeout"}
            )
            raise RuntimeError("provider timeout")
        if row.status == "failed":
            row = row.model_copy(update={"status": "complete", "public_error": None})
            self.by_id[assessment_id] = row
        return row

    def get_assessment(self, assessment_id):
        return self.by_id[assessment_id]

    def list_for_version(self, _project_id, _version_id):
        return tuple(self.by_id.values())


def _project(tmp_path):
    store = PitchProjectStore(tmp_path / "projects")
    project = store.create_project(
        display_name="ShiftPilot",
        company_aliases=("ShiftPilot",),
        pitch_text="Pitch",
    )
    return store, project


def test_relative_fit_requires_ten_scores_and_is_empirical_percentile() -> None:
    unavailable = relative_fit(0.63, [0.10] * 9)
    available = relative_fit(0.63, [0.10, 0.20, 0.40, 0.63, 0.80] * 2)

    assert unavailable.percentile is None
    assert unavailable.reference_count == 9
    assert available.percentile == 80.0
    assert available.reference_count == 10


def test_match_ranks_completed_rows_and_marks_near_leaders(tmp_path) -> None:
    store, project = _project(tmp_path)
    rows = [
        _assessment("a-1", "charles-hudson-precursor-ventures", 0.63),
        _assessment("a-2", "elizabeth-yin-hustle-fund", 0.60),
        _assessment("a-3", "phil-nadel", 0.31),
    ]
    service = MatchingService(
        store=store,
        assessments=FakeAssessments(rows),
        reference_scores={row.vc_slug: [0.1] * 10 for row in rows},
    )

    match = service.create_match(
        project.project_id,
        project.current_version_id,
        tuple(row.vc_slug for row in rows),
    )
    completed = service.run_match(match.match_id)

    assert [row.vc_slug for row in completed.assessments] == [
        "charles-hudson-precursor-ventures",
        "elizabeth-yin-hustle-fund",
        "phil-nadel",
    ]
    assert completed.assessments[0].highest_estimated_fit is True
    assert completed.assessments[1].leading_group is True
    assert completed.assessments[2].leading_group is False


def test_partial_failure_preserves_success_and_can_retry_target(tmp_path) -> None:
    store, project = _project(tmp_path)
    rows = [
        _assessment("a-1", "charles-hudson-precursor-ventures", 0.63),
        _assessment("a-2", "elizabeth-yin-hustle-fund", 0.60),
    ]
    assessments = FakeAssessments(rows)
    assessments.fail.add("elizabeth-yin-hustle-fund")
    service = MatchingService(store=store, assessments=assessments)
    match = service.create_match(
        project.project_id,
        project.current_version_id,
        tuple(row.vc_slug for row in rows),
    )

    partial = service.run_match(match.match_id)
    assert partial.status == "partial"
    assert {row.status for row in partial.assessments} == {"complete", "failed"}

    assessments.fail.clear()
    recovered = service.retry(match.match_id, "elizabeth-yin-hustle-fund")
    assert recovered.status == "complete"
    assert all(row.status == "complete" for row in recovered.assessments)


def test_match_requires_two_to_six_unique_investors(tmp_path) -> None:
    store, project = _project(tmp_path)
    service = MatchingService(store=store, assessments=FakeAssessments([]))

    with pytest.raises(ValueError, match="2 to 6"):
        service.create_match(project.project_id, project.current_version_id, ("one",))
    with pytest.raises(ValueError, match="distinct"):
        service.create_match(
            project.project_id, project.current_version_id, ("one", "one")
        )


def test_comparison_is_stable_and_grows_without_duplicate_artifacts(tmp_path) -> None:
    store, project = _project(tmp_path)
    rows = [
        _assessment("a-1", "charles-hudson-precursor-ventures", 0.63),
        _assessment("a-2", "elizabeth-yin-hustle-fund", 0.60),
        _assessment("a-3", "phil-nadel", 0.31, status="queued"),
    ]
    service = MatchingService(store=store, assessments=FakeAssessments(rows))

    first = service.update_comparison(
        project.project_id,
        project.current_version_id,
        ("charles-hudson-precursor-ventures", "elizabeth-yin-hustle-fund"),
    )
    second = service.update_comparison(
        project.project_id,
        project.current_version_id,
        ("charles-hudson-precursor-ventures", "phil-nadel"),
    )

    assert second.comparison_id == first.comparison_id
    assert second.selected_vc_slugs == (
        "charles-hudson-precursor-ventures",
        "elizabeth-yin-hustle-fund",
        "phil-nadel",
    )
    assert second.missing_vc_slugs == ("phil-nadel",)
    assert (
        store.version_root(project.project_id, project.current_version_id)
        / "comparison.json"
    ).is_file()


def test_comparison_supports_single_investor_and_reuses_complete_assessment(tmp_path) -> None:
    store, project = _project(tmp_path)
    row = _assessment("a-1", "charles-hudson-precursor-ventures", 0.63)
    service = MatchingService(store=store, assessments=FakeAssessments([row]))

    comparison = service.update_comparison(
        project.project_id,
        project.current_version_id,
        (row.vc_slug,),
    )

    assert comparison.status == "complete"
    assert comparison.missing_vc_slugs == ()
    assert comparison.assessments[0].reused is True
