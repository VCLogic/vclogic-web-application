from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vclogic_web.assessment_service import (
    AssessmentBusyError,
    CanonicalAssessmentService,
)
from vclogic_web.project_store import PitchProjectStore


def _baseline(run_root: Path, *, likelihood: float = 0.63):
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "phase1").mkdir(exist_ok=True)
    (run_root / "phase2").mkdir(exist_ok=True)
    (run_root / "state.json").write_text(
        json.dumps(
            {
                "evidence_registry": {
                    "W-cafe": {
                        "evidence_id": "W-cafe",
                        "heading": "Founder judgment",
                        "source_path": "persona.md",
                        "text": "This investor values founders with direct operating experience.",
                    },
                    "H-beef": {
                        "evidence_id": "H-beef",
                        "episode_slug": "12-prior-company",
                        "decision_status": "In",
                        "text": "I backed this because the founder knew the workflow firsthand.",
                    },
                },
                "events": [
                    {"kind": "phase1_frozen", "sequence": 1, "status": "accepted"},
                    {"kind": "phase2_frozen", "sequence": 2, "status": "accepted"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_root / "phase1" / "investigation.json").write_text(
        json.dumps(
            {
                "rationales": [
                    {
                        "taxonomy_label": "founder_market_fit",
                        "direction": "positive",
                        "pitch_evidence_ids": ["P-001"],
                        "wiki_evidence_ids": ["W-cafe"],
                        "historical_evidence_ids": ["H-beef"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (run_root / "phase2" / "decision.json").write_text(
        json.dumps({"decision_justification": "Strong fit (P-001; W-cafe; H-beef)."}),
        encoding="utf-8",
    )
    return SimpleNamespace(
        run_root=run_root,
        contract_version="v4.1",
        phase1_status="accepted",
        phase2_status="provisional",
        investigation=SimpleNamespace(
            rationales=[
                SimpleNamespace(
                    taxonomy_label="founder_market_fit",
                    direction="positive",
                    salience="primary",
                    confidence=0.81,
                ),
                SimpleNamespace(
                    taxonomy_label="traction_repeatability_concern",
                    direction="negative",
                    salience="secondary",
                    confidence=0.72,
                ),
            ]
        ),
        decision=SimpleNamespace(
            decision="In" if likelihood >= 0.5 else "Out",
            investment_likelihood=likelihood,
            decision_confidence=0.74,
            review_priority_score=0.77,
            decision_justification="Domain fit and paid usage outweigh the open questions (P-001; W-cafe; H-beef).",
        ),
    )


def _project(store: PitchProjectStore):
    return store.create_project(
        display_name="ShiftPilot",
        company_aliases=("ShiftPilot",),
        pitch_text="# ShiftPilot",
    )


def test_completed_assessment_is_reused_without_rebuilding(tmp_path) -> None:
    store = PitchProjectStore(tmp_path / "projects")
    project = _project(store)
    calls = []

    def builder(**kwargs):
        calls.append(kwargs)
        return _baseline(kwargs["session_root"] / "run")

    service = CanonicalAssessmentService(
        store=store,
        workspace=tmp_path,
        rehearsal_config=SimpleNamespace(),
        baseline_builder=builder,
    )
    queued = service.ensure_assessment(
        project.project_id,
        project.current_version_id,
        "elizabeth-yin-hustle-fund",
    )
    completed = service.run_assessment(queued.assessment_id)
    reused = service.ensure_assessment(
        project.project_id,
        project.current_version_id,
        "elizabeth-yin-hustle-fund",
    )

    assert completed.status == "complete"
    assert completed.investment_likelihood == 0.63
    assert completed.positive_rationales == ("founder_market_fit",)
    assert reused.assessment_id == completed.assessment_id
    assert len(calls) == 1

    presented = service.get_assessment(completed.assessment_id)
    assert presented.decision_summary == (
        "In at 63% estimated investment likelihood. Strongest signals: Founder Market Fit. "
        "Main concerns: Traction Repeatability Concern."
    )
    assert [row.reference_id for row in presented.citations] == [
        "P-001",
        "W-cafe",
        "H-beef",
    ]
    assert presented.citations[0].excerpt == "# ShiftPilot"
    assert presented.citations[1].source_type == "investment_memory"
    assert presented.citations[2].source_type == "precedent"
    assert presented.citations[2].rationale_labels == ("founder_market_fit",)
    assert presented.activity[-1].stage == "assessment_complete"


def test_legacy_manifest_hydrates_presentation_without_rewriting(tmp_path) -> None:
    store = PitchProjectStore(tmp_path / "projects")
    project = _project(store)
    service = CanonicalAssessmentService(
        store=store,
        workspace=tmp_path,
        rehearsal_config=SimpleNamespace(),
        baseline_builder=lambda **kwargs: _baseline(kwargs["session_root"] / "run"),
    )
    row = service.ensure_assessment(
        project.project_id, project.current_version_id, "phil-nadel"
    )
    before = service._find(row.assessment_id).read_text(encoding="utf-8")
    hydrated = service.get_assessment(row.assessment_id)

    assert hydrated.activity[0].stage == "queued"
    assert hydrated.citations == ()
    assert service._find(row.assessment_id).read_text(encoding="utf-8") == before


def test_failed_assessment_can_retry_in_place(tmp_path) -> None:
    store = PitchProjectStore(tmp_path / "projects")
    project = _project(store)
    attempts = 0

    def builder(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("provider unavailable")
        return _baseline(kwargs["session_root"] / "run", likelihood=0.22)

    service = CanonicalAssessmentService(
        store=store,
        workspace=tmp_path,
        rehearsal_config=SimpleNamespace(),
        baseline_builder=builder,
    )
    row = service.ensure_assessment(
        project.project_id, project.current_version_id, "charles-hudson-precursor-ventures"
    )
    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.run_assessment(row.assessment_id)

    failed = service.get_assessment(row.assessment_id)
    assert failed.status == "failed"
    assert failed.public_error == "provider unavailable"

    recovered = service.run_assessment(row.assessment_id)
    assert recovered.assessment_id == row.assessment_id
    assert recovered.status == "complete"
    assert recovered.decision == "Out"


def test_running_assessment_rejects_duplicate_execution(tmp_path) -> None:
    store = PitchProjectStore(tmp_path / "projects")
    project = _project(store)
    service = CanonicalAssessmentService(
        store=store,
        workspace=tmp_path,
        rehearsal_config=SimpleNamespace(),
        baseline_builder=lambda **kwargs: _baseline(kwargs["session_root"] / "run"),
    )
    row = service.ensure_assessment(
        project.project_id, project.current_version_id, "phil-nadel"
    )
    service._active.add(row.assessment_id)

    with pytest.raises(AssessmentBusyError):
        service.run_assessment(row.assessment_id)
