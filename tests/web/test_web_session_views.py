from pathlib import Path
import os
import pytest

from vc_clone_graph.rehearsal_artifacts import RehearsalArtifactStore
from vclogic_web.session_views import (
    _assessment,
    _agent_activity,
    _canonical_failure_status,
    _effective_session_status,
    SessionViewBuilder,
    list_sessions,
)


ROOT = Path(os.environ.get("VCLOGIC_PIPELINE_WORKSPACE",
    str(Path(__file__).resolve().parents[3] / "vclogic-vc-agentic-assessment"))).resolve()
CANARY = (
    ROOT
    / "outputs/rehearsal-v41-grounded-charles-canaries-2026-08-24"
    / "charles-hudson-precursor-ventures"
    / "panel-replay-39-this-pitch-is-damn-near-perfect-4eafbd5f"
)


@pytest.mark.skipif(not (CANARY / "manifest.json").is_file(), reason="requires archived rehearsal canary outputs")
def test_session_view_preserves_initial_and_current_assessments() -> None:
    store = RehearsalArtifactStore.open(CANARY)

    view = SessionViewBuilder(store).build()

    assert view.initial_assessment is not None
    assert view.current_assessment is not None
    assert view.initial_assessment.decision == "In"
    assert view.current_assessment.decision == "In"
    assert view.pitch_sha256 == store.verify()["pitch_sha256"]
    assert "simulation" in view.disclosure.lower()


def test_assessment_projects_score_reconciliation_explanation() -> None:
    explanation = (
        "The final synthesis decreased likelihood by 4 percentage points after "
        "balancing the new evidence against remaining concerns."
    )

    assessment = _assessment(
        {
            "decision": "Out",
            "investment_likelihood": 0.46,
            "decision_confidence": 0.72,
            "score_reconciliation": {
                "before": 0.50,
                "after": 0.46,
                "direction": "decreased",
                "explanation": explanation,
            },
        }
    )

    assert assessment is not None
    assert assessment.score_reconciliation == explanation
    assert _assessment(
        {
            "decision": "Out",
            "investment_likelihood": 0.46,
            "decision_confidence": 0.72,
        }
    ).score_reconciliation is None


@pytest.mark.skipif(not (CANARY / "manifest.json").is_file(), reason="requires archived rehearsal canary outputs")
def test_annotations_require_exact_pitch_spans() -> None:
    store = RehearsalArtifactStore.open(CANARY)

    view = SessionViewBuilder(store).build()
    pitch = store.pitch_path.read_text(encoding="utf-8")

    assert view.annotations
    assert all(pitch[row.start : row.end] == row.text for row in view.annotations)


@pytest.mark.skipif(not (CANARY / "manifest.json").is_file(), reason="requires archived rehearsal canary outputs")
def test_session_listing_uses_verified_artifacts() -> None:
    output_root = ROOT / "outputs/rehearsal-v41-grounded-charles-canaries-2026-08-24"

    rows = list_sessions(output_root)

    assert rows
    assert any(row.session_id == CANARY.name for row in rows)
    assert all(row.verification_status == "verified" for row in rows)
    canary = next(row for row in rows if row.session_id == CANARY.name)
    assert canary.initial_likelihood == 0.63


def test_agent_activity_exposes_only_sanitized_structured_response_text(tmp_path: Path) -> None:
    turn = tmp_path / "canonical-bootstrap/runs/live-test/phase1/turn-01"
    turn.mkdir(parents=True)
    (turn / "plan-model-response.json").write_text(
        """{
          "prompt": "SECRET PROMPT",
          "elapsed_seconds": 1.25,
          "parsed": {
            "continuation_focus": "Test whether retention changes the decision.",
            "questions": ["What is cohort retention?"],
            "wiki_queries": ["retention hard rules"],
            "precedent_queries": ["retention precedents"]
          }
        }""",
        encoding="utf-8",
    )
    (turn / "investigation-model-response.json").write_text(
        """{
          "prompt": "ANOTHER SECRET",
          "elapsed_seconds": 2.5,
          "parsed": {
            "summary": "Retention remains unresolved.",
            "rationales": [{
              "label": "traction_repeatability_concern",
              "direction": "negative",
              "salience": "primary",
              "interpretation": "No cohort evidence was supplied."
            }],
            "unanswered_questions": ["What is twelve-month retention?"]
          }
        }""",
        encoding="utf-8",
    )
    failed = tmp_path / "canonical-bootstrap/runs/live-test/phase1/turn-02"
    failed.mkdir(parents=True)
    (failed / "investigation-model-response.json").write_text(
        '{"content":"","parsed":null,"usage":{"output_tokens":578}}',
        encoding="utf-8",
    )

    activity = _agent_activity(tmp_path)

    assert [row.kind for row in activity] == ["plan", "investigation", "investigation"]
    assert activity[0].text == "Test whether retention changes the decision."
    assert "Question: What is cohort retention?" in activity[0].details
    assert activity[1].text == "Retention remains unresolved."
    assert "Negative · primary · traction repeatability concern — No cohort evidence was supplied." in activity[1].details
    assert activity[2].status == "failed"
    assert "578 output tokens" in activity[2].text
    assert "SECRET" not in repr(activity)


def test_agent_activity_uses_successful_plan_repair_instead_of_failed_attempt(
    tmp_path: Path,
) -> None:
    turn = tmp_path / "canonical-bootstrap/runs/live-test/phase1/turn-01"
    turn.mkdir(parents=True)
    (turn / "plan-model-response.json").write_text(
        '{"content":"truncated","parsed":null,"elapsed_seconds":58.2}',
        encoding="utf-8",
    )
    (turn / "plan-retry-model-response.json").write_text(
        """{
          "elapsed_seconds": 3.1,
          "parsed": {
            "continuation_focus": "Resolve the investor's healthcare boundary.",
            "questions": ["What makes this software rather than a care provider?"],
            "wiki_queries": ["healthcare exclusions"],
            "precedent_queries": []
          }
        }""",
        encoding="utf-8",
    )

    activity = _agent_activity(tmp_path)

    assert len(activity) == 1
    assert activity[0].status == "complete"
    assert activity[0].text == "Resolve the investor's healthcare boundary."
    assert activity[0].elapsed_seconds == 3.1


def test_canonical_failure_status_survives_process_restart(tmp_path: Path) -> None:
    run = tmp_path / "canonical-bootstrap/runs/live-test"
    run.mkdir(parents=True)
    (run / "state.json").write_text(
        '{"phase1_status":"failed","phase2_status":"pending"}', encoding="utf-8"
    )

    assert _canonical_failure_status(tmp_path) == "failed"


def test_interrupted_graph_state_with_question_is_publicly_awaiting_answer(
    tmp_path: Path,
) -> None:
    state = {
        "status": "running",
        "current_question": {"question_id": "Q-001", "text": "What changed?"},
    }

    assert _effective_session_status(state, tmp_path) == "awaiting_answer"


def test_session_view_projects_chat_transcript_and_turn_budget(tmp_path: Path) -> None:
    store = RehearsalArtifactStore.create(tmp_path, "test-investor", "chat-session", "Pitch text")
    store.write_accepted(
        "session-config.json",
        {
            "investor_name": "Test Investor",
            "max_questions": 3,
            "rehearsal_depth": "quick",
        },
    )
    store.write_accepted(
        "turns/turn-01/question.json",
        {
            "question_id": "Q-001",
            "text": "What is retention?",
            "dimension": "traction",
            "rationale_labels": ["traction_validation"],
            "expected_decision_value": 0.8,
            "why_now": "Retention is unresolved.",
            "response_comment": "I want to start with evidence of repeat use.",
        },
    )
    store.write_accepted(
        "state.json",
        {
            "status": "running",
            "answers": [
                {
                    "answer_id": "A-001",
                    "question_id": "Q-001",
                    "question": "What is retention?",
                    "text_verbatim": "Eighty-two percent renew annually.",
                    "received_at": "2026-08-28T00:00:00Z",
                }
            ],
            "current_question": {
                "question_id": "Q-002",
                "text": "What drives those renewals?",
                "dimension": "traction",
                "rationale_labels": ["traction_validation"],
                "expected_decision_value": 0.7,
                "why_now": "The mechanism is unresolved.",
                "response_comment": "That renewal rate is encouraging; I now want to understand what makes it durable.",
            },
            "current_rationales": [],
            "question_count": 1,
        },
    )

    view = SessionViewBuilder(store).build()

    assert view.max_questions == 3
    assert view.rehearsal_depth == "quick"
    assert view.active_question is not None
    assert view.active_question.response_comment.startswith("That renewal rate")
    assert view.conversation[0].question == "What is retention?"
    assert view.conversation[0].response_comment == "I want to start with evidence of repeat use."
    assert view.conversation[0].founder_answer == "Eighty-two percent renew annually."
    assert view.conversation[0].rationale_labels == ("traction_validation",)


def test_complete_session_exposes_natural_closing_without_inventing_legacy_comments(
    tmp_path: Path,
) -> None:
    store = RehearsalArtifactStore.create(tmp_path, "test-investor", "complete-session", "Pitch text")
    store.write_accepted("session-config.json", {"investor_name": "Test Investor", "max_questions": 3})
    store.write_accepted(
        "state.json",
        {
            "status": "complete",
            "answers": [{"answer_id": "A-001", "question_id": "Q-001", "question": "What is retention?", "text_verbatim": "Unknown.", "received_at": "now"}],
            "current_rationales": [],
            "stopping_reason": "information_sufficient",
        },
    )

    view = SessionViewBuilder(store).build()

    assert view.conversation[0].response_comment is None
    assert "enough information" in view.closing_message.lower()


def test_legacy_session_defaults_depth_without_rewriting_its_question_limit(
    tmp_path: Path,
) -> None:
    store = RehearsalArtifactStore.create(
        tmp_path, "test-investor", "legacy-session", "Pitch text"
    )
    store.write_accepted(
        "session-config.json",
        {"investor_name": "Test Investor", "max_questions": 4},
    )
    store.write_accepted("state.json", {"status": "running"})

    view = SessionViewBuilder(store).build()

    assert view.rehearsal_depth == "standard"
    assert view.max_questions == 4


def test_session_view_exposes_verified_effect_timeline_and_decision_path(
    tmp_path: Path,
) -> None:
    store = RehearsalArtifactStore.create(
        tmp_path, "test-investor", "auditable-session", "Eight paying agencies."
    )
    store.write_accepted(
        "session-config.json",
        {
            "investor_name": "Test Investor",
            "max_questions": 5,
            "rehearsal_depth": "standard",
        },
    )
    initial_rationale = {
        "rationale_id": "R-001",
        "taxonomy_label": "product_adoption",
        "direction": "positive",
        "salience": "primary",
        "confidence": 0.7,
        "assessment": "Paying agencies show early adoption.",
        "evidence_refs": [
            {
                "evidence_id": "P-001",
                "source_kind": "pitch",
                "source_path": "pitch.txt",
                "excerpt": "Eight paying agencies.",
            }
        ],
    }
    rehearsal_rationale = {
        "rationale_id": "R-002",
        "taxonomy_label": "unit_economics_assessment",
        "direction": "neutral",
        "salience": "secondary",
        "confidence": 0.6,
        "assessment": "Implementation cost remains unresolved.",
        "evidence_refs": [
            {
                "evidence_id": "A-002",
                "source_kind": "founder_answer",
                "source_path": "turns/turn-02/answer.json",
                "excerpt": "We have not calculated the fully loaded cost.",
            },
            {
                "evidence_id": "W-001",
                "source_kind": "wiki",
                "source_path": "economics.md",
                "excerpt": "Implementation burden matters.",
            },
        ],
    }
    for number, question in enumerate(
        ("How many target agencies are customers?", "What does implementation cost?"),
        start=1,
    ):
        store.write_accepted(
            f"turns/turn-{number:02d}/question.json",
            {
                "question_id": f"Q-{number:03d}",
                "text": question,
                "dimension": "economics",
                "rationale_labels": ["unit_economics_assessment"],
                "expected_decision_value": 0.5,
                "why_now": "The evidence is incomplete.",
            },
        )
    store.write_accepted(
        "turns/turn-01/update.json",
        {
            "answer_id": "A-001",
            "evidence_effect": "clarification",
            "investment_likelihood_before": 0.24,
            "investment_likelihood_after": 0.24,
            "supporting_answer_excerpt": None,
        },
    )
    store.write_accepted(
        "turns/turn-02/update.json",
        {
            "answer_id": "A-002",
            "evidence_effect": "new_negative",
            "investment_likelihood_before": 0.24,
            "investment_likelihood_after": 0.20,
            "supporting_answer_excerpt": "We have not calculated the fully loaded cost.",
        },
    )
    answers = [
        {
            "answer_id": "A-001",
            "question_id": "Q-001",
            "text_verbatim": "The eight accounts are not segmented yet.",
            "submission_sha256": "a" * 64,
            "received_at": "2026-08-31T00:00:00Z",
        },
        {
            "answer_id": "A-002",
            "question_id": "Q-002",
            "text_verbatim": "We have not calculated the fully loaded cost.",
            "submission_sha256": "b" * 64,
            "received_at": "2026-08-31T00:01:00Z",
        },
    ]
    store.write_accepted(
        "state.json",
        {
            "status": "complete",
            "initial_assessment": {
                "decision": "Out",
                "investment_likelihood": 0.24,
                "decision_confidence": 0.7,
                "rationales": [initial_rationale],
            },
            "final_assessment": {
                "decision": "Out",
                "investment_likelihood": 0.18,
                "decision_confidence": 0.75,
                "rationale_state": [initial_rationale, rehearsal_rationale],
            },
            "current_rationales": [initial_rationale, rehearsal_rationale],
            "answers": answers,
            "stopping_reason": "information_sufficient",
        },
    )

    view = SessionViewBuilder(store).build()

    assert [row.evidence_effect for row in view.likelihood_timeline] == [
        "baseline",
        "clarification",
        "new_negative",
        "synthesis",
    ]
    assert view.likelihood_timeline[1].delta == 0
    assert view.likelihood_timeline[2].delta == -0.04
    assert view.likelihood_timeline[3].before == 0.20
    assert view.likelihood_timeline[3].after == 0.18
    assert view.conversation[1].answer_sha256 == "b" * 64
    assert {row.evidence_origin for row in view.decision_path} == {
        "pitch",
        "founder_answer",
    }
    assert {row.evidence_id for row in view.decision_path if row.evidence_origin == "founder_answer"} == {
        "A-001",
        "A-002",
    }
    founder_path = next(
        row for row in view.decision_path if row.evidence_origin == "founder_answer"
    )
    assert founder_path.baseline_or_rehearsal == "rehearsal"
    assert founder_path.supporting_evidence_ids == ("W-001",)
