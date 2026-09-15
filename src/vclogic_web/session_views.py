"""Deterministic public views derived from verified rehearsal artifacts."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

from vc_clone_graph.rehearsal_artifacts import RehearsalArtifactStore
from .models import (
    AgentActivityView,
    AssessmentView,
    ConversationTurnView,
    DecisionPathView,
    EvidenceView,
    LikelihoodTimelineView,
    PitchAnnotationView,
    QuestionView,
    RationaleGraphResponse,
    RationaleNodeView,
    SessionDetailResponse,
    SessionSummary,
)


_EVIDENCE_EFFECTS = {
    "new_positive",
    "new_negative",
    "clarification",
    "unresolved",
    "contradiction",
}


def _conversation(
    store: RehearsalArtifactStore, answers: object
) -> tuple[ConversationTurnView, ...]:
    rows: list[ConversationTurnView] = []
    accepted = answers if isinstance(answers, list) else []
    for index, answer in enumerate(accepted, start=1):
        if not isinstance(answer, dict):
            continue
        question = _read_optional(store, f"turns/turn-{index:02d}/question.json")
        update = _read_optional(store, f"turns/turn-{index:02d}/update.json")
        effect = str(update.get("evidence_effect", ""))
        before = update.get("investment_likelihood_before")
        after = update.get("investment_likelihood_after")
        rows.append(
            ConversationTurnView(
                question_id=str(answer.get("question_id") or question.get("question_id") or f"Q-{index:03d}"),
                question=str(answer.get("question") or question.get("text") or "Recorded investor question"),
                response_comment=(
                    str(question["response_comment"])
                    if question.get("response_comment")
                    else None
                ),
                rationale_labels=tuple(str(label) for label in question.get("rationale_labels", [])),
                founder_answer=(
                    str(answer["text_verbatim"])
                    if answer.get("text_verbatim")
                    else None
                ),
                answer_sha256=(
                    str(answer["submission_sha256"])
                    if answer.get("submission_sha256")
                    else None
                ),
                evidence_effect=(
                    effect if effect in _EVIDENCE_EFFECTS else None
                ),
                investment_likelihood_before=(
                    float(before) if isinstance(before, (int, float)) else None
                ),
                investment_likelihood_after=(
                    float(after) if isinstance(after, (int, float)) else None
                ),
                likelihood_delta=(
                    round(float(after) - float(before), 6)
                    if isinstance(before, (int, float))
                    and isinstance(after, (int, float))
                    else None
                ),
            )
        )
    return tuple(rows)


def _likelihood_timeline(
    store: RehearsalArtifactStore,
    initial: object,
    answers: object,
    current: object,
) -> tuple[LikelihoodTimelineView, ...]:
    if not isinstance(initial, dict) or not isinstance(
        initial.get("investment_likelihood"), (int, float)
    ):
        return ()
    baseline = float(initial["investment_likelihood"])
    rows = [
        LikelihoodTimelineView(
            turn=0,
            label="Canonical baseline",
            evidence_effect="baseline",
            before=baseline,
            after=baseline,
            delta=0.0,
        )
    ]
    accepted = answers if isinstance(answers, list) else []
    for index, answer in enumerate(accepted, start=1):
        if not isinstance(answer, dict):
            continue
        update = _read_optional(store, f"turns/turn-{index:02d}/update.json")
        effect = str(update.get("evidence_effect", ""))
        before = update.get("investment_likelihood_before")
        after = update.get("investment_likelihood_after")
        if (
            effect not in _EVIDENCE_EFFECTS
            or not isinstance(before, (int, float))
            or not isinstance(after, (int, float))
        ):
            continue
        rows.append(
            LikelihoodTimelineView(
                turn=index,
                label=str(answer.get("question") or f"Founder response {index}"),
                evidence_effect=effect,  # type: ignore[arg-type]
                before=float(before),
                after=float(after),
                delta=round(float(after) - float(before), 6),
                answer_excerpt=(
                    str(update["supporting_answer_excerpt"])
                    if update.get("supporting_answer_excerpt")
                    else None
                ),
            )
        )
    final_likelihood = (
        current.get("investment_likelihood")
        if isinstance(current, dict)
        else None
    )
    previous = rows[-1].after
    if (
        isinstance(final_likelihood, (int, float))
        and abs(float(final_likelihood) - previous) > 1e-9
    ):
        rows.append(
            LikelihoodTimelineView(
                turn=rows[-1].turn + 1,
                label="Final synthesis",
                evidence_effect="synthesis",
                before=previous,
                after=float(final_likelihood),
                delta=round(float(final_likelihood) - previous, 6),
            )
        )
    return tuple(rows)


def _decision_path(
    store: RehearsalArtifactStore,
    current: Iterable[dict[str, Any]],
    initial: Iterable[dict[str, Any]],
    answers: object,
) -> tuple[DecisionPathView, ...]:
    initial_rows = list(initial)
    current_rows = list(current)
    baseline_ids = {str(row.get("rationale_id")) for row in initial_rows}
    rows: list[DecisionPathView] = []
    for rationale in current_rows:
        rationale_id = str(
            rationale.get("rationale_id")
            or rationale.get("taxonomy_label")
            or "unknown"
        )
        direction = str(rationale.get("direction", "neutral"))
        public_direction = (
            direction if direction in {"positive", "negative"} else "unresolved"
        )
        evidence = [
            row
            for row in rationale.get("evidence_refs", [])
            if isinstance(row, dict)
        ]
        supporting = tuple(
            sorted(
                str(row["evidence_id"])
                for row in evidence
                if row.get("evidence_id")
                and row.get("source_kind") not in {"pitch", "founder_answer"}
            )
        )
        for source in evidence:
            kind = str(source.get("source_kind", ""))
            excerpt = str(source.get("excerpt", "")).strip()
            evidence_id = str(source.get("evidence_id", "")).strip()
            if kind not in {"pitch", "founder_answer"} or not excerpt or not evidence_id:
                continue
            rows.append(
                DecisionPathView(
                    path_id=f"path-{rationale_id}-{evidence_id}",
                    evidence_id=evidence_id,
                    evidence_origin=kind,  # type: ignore[arg-type]
                    evidence_excerpt=excerpt,
                    rationale_id=rationale_id,
                    rationale_label=str(
                        rationale.get("taxonomy_label", "unknown")
                    ),
                    direction=public_direction,  # type: ignore[arg-type]
                    contribution=str(
                        rationale.get("assessment", "Contribution unavailable.")
                    ),
                    baseline_or_rehearsal=(
                        "baseline"
                        if rationale_id in baseline_ids and kind == "pitch"
                        else "rehearsal"
                    ),
                    supporting_evidence_ids=supporting,
                )
            )
    rationale_by_label = {
        str(rationale.get("taxonomy_label")): rationale
        for rationale in (*initial_rows, *current_rows)
        if rationale.get("taxonomy_label")
    }
    existing_answer_links = {
        (row.rationale_id, row.evidence_id)
        for row in rows
        if row.evidence_origin == "founder_answer"
    }
    accepted = answers if isinstance(answers, list) else []
    effect_direction = {
        "new_positive": "positive",
        "new_negative": "negative",
        "contradiction": "negative",
        "clarification": "unresolved",
        "unresolved": "unresolved",
    }
    for index, answer in enumerate(accepted, start=1):
        if not isinstance(answer, dict):
            continue
        answer_id = str(answer.get("answer_id", "")).strip()
        excerpt = str(answer.get("text_verbatim", "")).strip()
        if not answer_id or not excerpt:
            continue
        question = _read_optional(store, f"turns/turn-{index:02d}/question.json")
        update = _read_optional(store, f"turns/turn-{index:02d}/update.json")
        labels = update.get("affected_rationale_labels") or question.get(
            "rationale_labels", []
        )
        if not isinstance(labels, list):
            continue
        effect = str(update.get("evidence_effect", "unresolved"))
        direction = effect_direction.get(effect, "unresolved")
        contribution = str(
            update.get("update_summary")
            or (
                "The founder response left this investment question unresolved."
                if direction == "unresolved"
                else "The founder response materially updated this rationale."
            )
        )
        for label_value in labels:
            label = str(label_value)
            rationale = rationale_by_label.get(label, {})
            rationale_id = str(
                rationale.get("rationale_id") or f"answer-{answer_id}-{label}"
            )
            if (rationale_id, answer_id) in existing_answer_links:
                continue
            evidence = [
                row
                for row in rationale.get("evidence_refs", [])
                if isinstance(row, dict)
            ]
            supporting = tuple(
                sorted(
                    str(row["evidence_id"])
                    for row in evidence
                    if row.get("evidence_id")
                    and row.get("source_kind") not in {"pitch", "founder_answer"}
                )
            )
            rows.append(
                DecisionPathView(
                    path_id=f"path-{rationale_id}-{answer_id}",
                    evidence_id=answer_id,
                    evidence_origin="founder_answer",
                    evidence_excerpt=excerpt,
                    rationale_id=rationale_id,
                    rationale_label=label,
                    direction=direction,  # type: ignore[arg-type]
                    contribution=contribution,
                    baseline_or_rehearsal="rehearsal",
                    supporting_evidence_ids=supporting,
                )
            )
    order = {"positive": 0, "negative": 1, "unresolved": 2}
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                order[row.direction],
                row.rationale_label,
                row.evidence_id,
            ),
        )
    )


def _closing_message(reason: object) -> str:
    messages = {
        "founder_requested": "Thanks — I’ll assess the pitch using what we’ve discussed.",
        "question_cap": "We’ve reached the end of our available questions, so I’ll assess the pitch using the evidence we have.",
        "information_sufficient": "I have enough information to assess the pitch. I’ll now synthesize what we’ve discussed.",
    }
    return messages.get(
        str(reason),
        "The conversation is complete. I’ll now synthesize the assessment.",
    )


def _clip(value: object, limit: int = 1200) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _response_payload(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _plan_activity(
    payload: dict[str, Any], *, phase: str, iteration: int, activity_id: str
) -> AgentActivityView:
    phase_title = phase.replace("phase", "Phase ")
    parsed = payload.get("parsed")
    if not isinstance(parsed, dict):
        return AgentActivityView(
            activity_id=activity_id,
            phase=phase,  # type: ignore[arg-type]
            iteration=iteration,
            kind="plan",
            status="failed",
            title=f"{phase_title} planning response",
            text="The planning agent returned no structured answer text.",
            elapsed_seconds=payload.get("elapsed_seconds"),
        )
    details: list[str] = []
    for label, key in (
        ("Question", "questions"),
        ("Memory search", "wiki_queries"),
        ("Precedent search", "precedent_queries"),
    ):
        values = parsed.get(key, [])
        if isinstance(values, list):
            details.extend(f"{label}: {_clip(value, 500)}" for value in values[:6])
            if len(values) > 6:
                details.append(f"{len(values) - 6} additional {label.casefold()} requests recorded.")
    return AgentActivityView(
        activity_id=activity_id,
        phase=phase,  # type: ignore[arg-type]
        iteration=iteration,
        kind="plan",
        status="complete",
        title=f"{phase_title} agent plan",
        text=_clip(parsed.get("continuation_focus", "Structured investigation plan returned.")),
        details=tuple(details),
        elapsed_seconds=payload.get("elapsed_seconds"),
    )


def _result_activity(
    payload: dict[str, Any], *, phase: str, iteration: int, kind: str, activity_id: str
) -> AgentActivityView:
    parsed = payload.get("parsed")
    title = "Rationale investigation" if kind == "investigation" else "Decision synthesis"
    if not isinstance(parsed, dict):
        usage = payload.get("usage", {})
        output_tokens = usage.get("output_tokens") if isinstance(usage, dict) else None
        token_note = f" ({output_tokens} output tokens were reported)" if isinstance(output_tokens, int) else ""
        return AgentActivityView(
            activity_id=activity_id,
            phase=phase,  # type: ignore[arg-type]
            iteration=iteration,
            kind=kind,  # type: ignore[arg-type]
            status="failed",
            title=title,
            text=f"The agent returned no structured answer text{token_note}.",
            elapsed_seconds=payload.get("elapsed_seconds"),
        )
    details: list[str] = []
    rationales = parsed.get("rationales", [])
    if isinstance(rationales, list):
        for rationale in rationales[:16]:
            if not isinstance(rationale, dict):
                continue
            direction = str(rationale.get("direction", "unresolved")).title()
            salience = str(rationale.get("salience", "unresolved"))
            label = str(rationale.get("label", rationale.get("taxonomy_label", "rationale"))).replace("_", " ")
            interpretation = _clip(rationale.get("interpretation", ""), 600)
            details.append(f"{direction} · {salience} · {label}" + (f" — {interpretation}" if interpretation else ""))
    unanswered = parsed.get("unanswered_questions", [])
    if isinstance(unanswered, list):
        details.extend(f"Unresolved: {_clip(value, 500)}" for value in unanswered[:6])
    if kind == "decision" and parsed.get("decision"):
        details.insert(0, f"Decision: {parsed['decision']}")
    text = parsed.get("summary") or parsed.get("decision_justification") or parsed.get("synthesis_summary")
    return AgentActivityView(
        activity_id=activity_id,
        phase=phase,  # type: ignore[arg-type]
        iteration=iteration,
        kind=kind,  # type: ignore[arg-type]
        status="complete",
        title=title,
        text=_clip(text or "Structured agent response returned."),
        details=tuple(details),
        elapsed_seconds=payload.get("elapsed_seconds"),
    )


def _agent_activity(session_root: Path) -> tuple[AgentActivityView, ...]:
    rows: list[AgentActivityView] = []
    for phase in ("phase1", "phase2"):
        turns = sorted(Path(session_root).glob(f"canonical-bootstrap/runs/*/{phase}/turn-*"))
        for turn in turns:
            try:
                iteration = int(turn.name.removeprefix("turn-"))
            except ValueError:
                continue
            plan = turn / "plan-model-response.json"
            plan_retry = turn / "plan-retry-model-response.json"
            if plan_retry.is_file():
                plan = plan_retry
            if plan.is_file():
                rows.append(_plan_activity(
                    _response_payload(plan), phase=phase, iteration=iteration,
                    activity_id=f"{phase}-turn-{iteration:02d}-plan",
                ))
            result_name = "investigation-model-response.json" if phase == "phase1" else "decision-model-response.json"
            result = turn / result_name
            if result.is_file():
                kind = "investigation" if phase == "phase1" else "decision"
                rows.append(_result_activity(
                    _response_payload(result), phase=phase, iteration=iteration, kind=kind,
                    activity_id=f"{phase}-turn-{iteration:02d}-{kind}",
                ))
    return tuple(rows)


def _canonical_failure_status(session_root: Path) -> str | None:
    for path in sorted(Path(session_root).glob("canonical-bootstrap/runs/*/state.json"), reverse=True):
        payload = _response_payload(path)
        if payload.get("phase1_status") == "failed" or payload.get("phase2_status") == "failed":
            return "failed"
    return None


def _effective_session_status(state: dict[str, Any], session_root: Path) -> str:
    """Recover the public lifecycle state from durable workflow artifacts."""
    status = str(state.get("status") or "")
    if status == "complete":
        return status
    failure = _canonical_failure_status(session_root)
    if failure is not None:
        return failure
    if status == "running" and isinstance(state.get("current_question"), dict):
        return "awaiting_answer"
    return status or "preparing_inputs"


def _read_optional(store: RehearsalArtifactStore, relative: str) -> dict[str, Any]:
    path = store.session_root / relative
    return store.read_json(relative) if path.is_file() else {}


def _assessment(payload: object) -> AssessmentView | None:
    if not isinstance(payload, dict) or payload.get("decision") not in {"In", "Out"}:
        return None
    rationales = payload.get("rationales", [])
    counts = Counter(
        str(row.get("direction", "unresolved"))
        for row in rationales
        if isinstance(row, dict)
    )
    reconciliation = payload.get("score_reconciliation")
    reconciliation_explanation = (
        str(reconciliation["explanation"])
        if isinstance(reconciliation, dict) and reconciliation.get("explanation")
        else None
    )
    return AssessmentView(
        decision=payload["decision"],
        investment_likelihood=float(payload.get("investment_likelihood", 0)),
        decision_confidence=float(payload.get("decision_confidence", 0)),
        review_priority_score=(
            float(payload["review_priority_score"])
            if payload.get("review_priority_score") is not None
            else None
        ),
        rationale_counts=dict(counts),
        decision_justification=(
            str(payload["decision_justification"])
            if payload.get("decision_justification")
            else None
        ),
        score_reconciliation=reconciliation_explanation,
    )


def _rationales(state: dict[str, Any]) -> list[dict[str, Any]]:
    value = state.get("current_rationales") or (
        state.get("initial_assessment", {}).get("rationales", [])
        if isinstance(state.get("initial_assessment"), dict)
        else []
    )
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _evidence(rationales: Iterable[dict[str, Any]]) -> tuple[EvidenceView, ...]:
    rows: dict[str, EvidenceView] = {}
    for rationale in rationales:
        for raw in rationale.get("evidence_refs", []):
            if not isinstance(raw, dict) or not raw.get("evidence_id") or not raw.get("excerpt"):
                continue
            evidence_id = str(raw["evidence_id"])
            rows[evidence_id] = EvidenceView(
                evidence_id=evidence_id,
                source_kind=str(raw.get("source_kind", "unknown")),
                source_path=str(raw.get("source_path", "unknown")),
                excerpt=str(raw["excerpt"]),
                confidence=(
                    float(rationale["confidence"])
                    if rationale.get("confidence") is not None
                    else None
                ),
            )
    return tuple(rows[key] for key in sorted(rows))


def _annotations(
    pitch: str, rationales: Iterable[dict[str, Any]]
) -> tuple[PitchAnnotationView, ...]:
    grouped: dict[tuple[int, int, str], dict[str, set[str]]] = {}
    for rationale in rationales:
        rationale_id = str(rationale.get("rationale_id", "unknown"))
        direction = str(rationale.get("direction", "neutral"))
        if direction not in {"positive", "negative", "neutral"}:
            direction = "unresolved"
        for raw in rationale.get("evidence_refs", []):
            if not isinstance(raw, dict) or raw.get("source_kind") != "pitch":
                continue
            excerpt = str(raw.get("excerpt", ""))
            if not excerpt or pitch.count(excerpt) != 1:
                continue
            start = pitch.index(excerpt)
            key = (start, start + len(excerpt), direction)
            bucket = grouped.setdefault(key, {"rationales": set(), "evidence": set()})
            bucket["rationales"].add(rationale_id)
            bucket["evidence"].add(str(raw.get("evidence_id", "unknown")))
    return tuple(
        PitchAnnotationView(
            annotation_id=f"annotation-{index:03d}",
            start=start,
            end=end,
            text=pitch[start:end],
            direction=direction,  # type: ignore[arg-type]
            rationale_ids=tuple(sorted(values["rationales"])),
            evidence_ids=tuple(sorted(values["evidence"])),
        )
        for index, ((start, end, direction), values) in enumerate(
            sorted(grouped.items()), start=1
        )
    )


def _graph(
    current: list[dict[str, Any]], initial: list[dict[str, Any]]
) -> RationaleGraphResponse:
    initial_by_id = {str(row.get("rationale_id")): row for row in initial}
    nodes = []
    for row in current:
        rationale_id = str(row.get("rationale_id", row.get("taxonomy_label", "unknown")))
        direction = str(row.get("direction", "neutral"))
        if direction not in {"positive", "negative", "neutral"}:
            direction = "unresolved"
        salience = str(row.get("salience", "unresolved"))
        if salience not in {"primary", "secondary"}:
            salience = "unresolved"
        evidence_ids = tuple(
            str(evidence.get("evidence_id"))
            for evidence in row.get("evidence_refs", [])
            if isinstance(evidence, dict) and evidence.get("evidence_id")
        )
        previous = initial_by_id.get(rationale_id, {})
        nodes.append(
            RationaleNodeView(
                node_id=rationale_id,
                taxonomy_label=str(row.get("taxonomy_label", "unknown")),
                title=str(row.get("taxonomy_label", "unknown")).replace("_", " ").title(),
                direction=direction,  # type: ignore[arg-type]
                salience=salience,  # type: ignore[arg-type]
                confidence=float(row.get("confidence", 0)),
                evidence_ids=evidence_ids,
                initial_direction=(
                    str(previous.get("direction")) if previous.get("direction") else None
                ),
                initial_confidence=(
                    float(previous["confidence"])
                    if previous.get("confidence") is not None
                    else None
                ),
            )
        )
    return RationaleGraphResponse(nodes=tuple(nodes), edges=())


class SessionViewBuilder:
    def __init__(self, store: RehearsalArtifactStore) -> None:
        self.store = store

    def build(self) -> SessionDetailResponse:
        verification = self.store.verify()
        manifest = self.store.read_json("manifest.json")
        state = _read_optional(self.store, "state.json")
        metadata = _read_optional(self.store, "session-config.json")
        report = _read_optional(self.store, "founder-report.json")
        pitch = self.store.pitch_path.read_text(encoding="utf-8")
        effective_status = _effective_session_status(state, self.store.session_root)
        initial_payload = state.get("initial_assessment") or report.get("initial_assessment")
        current_payload = (
            state.get("final_assessment")
            or report.get("final_assessment")
            or {
                "decision": initial_payload.get("decision"),
                "investment_likelihood": state.get(
                    "current_likelihood", initial_payload.get("investment_likelihood", 0)
                ),
                "decision_confidence": state.get(
                    "current_confidence", initial_payload.get("decision_confidence", 0)
                ),
                "rationales": state.get("current_rationales", initial_payload.get("rationales", [])),
            }
            if isinstance(initial_payload, dict)
            else None
        )
        initial_rationales = (
            [row for row in initial_payload.get("rationales", []) if isinstance(row, dict)]
            if isinstance(initial_payload, dict)
            else []
        )
        current_rationales = _rationales(state) or initial_rationales
        question_raw = state.get("current_question")
        active_question = None
        if effective_status == "awaiting_answer" and isinstance(question_raw, dict):
            active_question = QuestionView(
                question_id=str(question_raw.get("question_id", "question")),
                text=str(question_raw.get("text", "")),
                rationale_labels=tuple(question_raw.get("rationale_labels", [])),
                decision_relevance=question_raw.get("why_now"),
                response_comment=question_raw.get("response_comment"),
            )
        disclosure = str(
            report.get("disclosure")
            or f"Simulation of {metadata.get('investor_name', 'an investor-like profile')}; not the real investor and not endorsed by them."
        )
        return SessionDetailResponse(
            session_id=str(manifest["session_id"]),
            vc_slug=str(manifest["vc_slug"]),
            investor_display_name=str(metadata.get("investor_name", manifest["vc_slug"])),
            disclosure=disclosure,
            status=effective_status,
            pitch_text=pitch,
            pitch_sha256=str(verification["pitch_sha256"]),
            initial_assessment=_assessment(initial_payload),
            current_assessment=_assessment(current_payload),
            active_question=active_question,
            conversation=_conversation(self.store, state.get("answers", [])),
            likelihood_timeline=_likelihood_timeline(
                self.store,
                initial_payload,
                state.get("answers", []),
                current_payload,
            ),
            decision_path=_decision_path(
                self.store,
                current_rationales,
                initial_rationales,
                state.get("answers", []),
            ),
            rehearsal_depth=str(metadata.get("rehearsal_depth", "standard")),
            max_questions=max(1, int(metadata.get("max_questions", 4))),
            closing_message=(
                _closing_message(state.get("stopping_reason"))
                if effective_status in {"complete", "finished"}
                else None
            ),
            agent_activity=_agent_activity(self.store.session_root),
            turns=tuple(state.get("answers", [])) if isinstance(state.get("answers"), list) else (),
            annotations=_annotations(pitch, current_rationales),
            rationale_graph=_graph(current_rationales, initial_rationales),
            evidence=_evidence(current_rationales),
            usage=(
                dict(state.get("usage", {}))
                if isinstance(state.get("usage"), dict)
                else dict(report.get("usage", {}))
                if isinstance(report.get("usage"), dict)
                else {}
            ),
            findings=tuple(str(row) for row in state.get("findings", [])),
        )


def _summary(store: RehearsalArtifactStore) -> SessionSummary:
    view = SessionViewBuilder(store).build()
    manifest = store.read_json("manifest.json")
    metadata = _read_optional(store, "session-config.json")
    return SessionSummary(
        session_id=view.session_id,
        vc_slug=view.vc_slug,
        investor_display_name=view.investor_display_name,
        company_aliases=tuple(metadata.get("target_company_aliases", [])),
        status=view.status,
        created_at=str(manifest.get("created_at", "unknown")),
        initial_decision=(view.initial_assessment.decision if view.initial_assessment else None),
        initial_likelihood=(
            view.initial_assessment.investment_likelihood if view.initial_assessment else None
        ),
        current_decision=(view.current_assessment.decision if view.current_assessment else None),
        current_likelihood=(
            view.current_assessment.investment_likelihood if view.current_assessment else None
        ),
        cost_usd=(float(view.usage.get("cost_usd", 0)) if view.usage else None),
        verification_status="verified",
    )


def list_sessions(output_root: Path) -> tuple[SessionSummary, ...]:
    root = Path(output_root).resolve()
    rows: list[SessionSummary] = []
    if not root.is_dir():
        return ()
    for manifest in sorted(root.glob("*/*/manifest.json")):
        try:
            rows.append(_summary(RehearsalArtifactStore.open(manifest.parent)))
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
    return tuple(sorted(rows, key=lambda row: (row.created_at, row.session_id), reverse=True))
