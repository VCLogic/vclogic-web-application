"""Reusable canonical Phase 1/Phase 2 assessments for pitch projects."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

from vc_clone_graph.prompts_v4 import pitch_evidence_index
from vc_clone_graph.rehearsal_bootstrap import build_or_load_canonical_baseline
from .models import (
    AssessmentActivityView,
    AssessmentCitationView,
    CanonicalAssessmentDetail,
)
from .project_store import PitchProjectStore


class AssessmentBusyError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


class CanonicalAssessmentService:
    """Build each pitch-version/investor canonical baseline at most once."""

    def __init__(
        self,
        *,
        store: PitchProjectStore,
        workspace: Path,
        rehearsal_config: Any,
        baseline_builder: Callable[..., Any] = build_or_load_canonical_baseline,
    ) -> None:
        self.store = store
        self.workspace = Path(workspace).resolve()
        self.rehearsal_config = rehearsal_config
        self.baseline_builder = baseline_builder
        self._guard = RLock()
        self._active: set[str] = set()

    def _assessment_root(self, project_id: str, version_id: str, vc_slug: str) -> Path:
        if not vc_slug or any(part in vc_slug for part in ("/", "\\", "..")):
            raise ValueError("invalid investor identifier")
        return self.store.version_root(project_id, version_id) / "assessments" / vc_slug

    @staticmethod
    def _manifest(root: Path) -> Path:
        return root / "assessment.json"

    @staticmethod
    def _read(path: Path) -> CanonicalAssessmentDetail:
        try:
            return CanonicalAssessmentDetail.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise ValueError("canonical assessment artifact is invalid") from exc

    @staticmethod
    def _title(value: str) -> str:
        return value.replace("_", " ").title()

    @staticmethod
    def _json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _activity(self, row: CanonicalAssessmentDetail) -> tuple[AssessmentActivityView, ...]:
        stages = [
            ("queued", "Assessment accepted", "The immutable pitch version is ready for analysis."),
            (
                "phase1_running",
                "Mapping decision rationales",
                "The investor memory, pitch evidence, and relevant precedents are being connected to the rationale taxonomy.",
            ),
            (
                "phase2_running",
                "Synthesizing the investment decision",
                "The grounded rationale record is being weighed into a decision, likelihood, confidence, and review priority.",
            ),
            (
                "assessment_complete",
                "Assessment ready",
                "The canonical assessment is saved and can be reused for comparison or rehearsal.",
            ),
        ]
        if row.status == "queued":
            completed = 0
        elif row.status == "running":
            completed = 1
        elif row.status == "complete":
            completed = len(stages)
        else:
            completed = 1
        result: list[AssessmentActivityView] = []
        for index, (stage, title, detail) in enumerate(stages):
            status = "complete" if index < completed else "pending"
            if row.status == "running" and index == completed:
                status = "active"
            if row.status == "failed" and index == completed:
                status = "failed"
                title = "Assessment stopped"
                detail = row.public_error or "The provider run did not complete."
            result.append(
                AssessmentActivityView(
                    stage=stage,
                    title=title,
                    detail=detail,
                    status=status,
                    timestamp=row.updated_at if status in {"complete", "failed"} else None,
                )
            )
        return tuple(result)

    def _summary(self, row: CanonicalAssessmentDetail) -> str | None:
        if row.decision is None or row.investment_likelihood is None:
            return None
        parts = [
            f"{row.decision} at {round(row.investment_likelihood * 100)}% estimated investment likelihood."
        ]
        if row.positive_rationales:
            parts.append(
                "Strongest signals: "
                + ", ".join(self._title(value) for value in row.positive_rationales[:3])
                + "."
            )
        if row.negative_rationales:
            parts.append(
                "Main concerns: "
                + ", ".join(self._title(value) for value in row.negative_rationales[:3])
                + "."
            )
        elif row.unresolved_rationales:
            parts.append(
                "Still unresolved: "
                + ", ".join(self._title(value) for value in row.unresolved_rationales[:3])
                + "."
            )
        return " ".join(parts)

    def _citations(
        self, path: Path, row: CanonicalAssessmentDetail
    ) -> tuple[AssessmentCitationView, ...]:
        justification = row.decision_justification or ""
        references = tuple(
            dict.fromkeys(
                re.findall(r"\b(?:P-\d{3}|R\d+|[WH]-[0-9a-f]+)\b", justification)
            )
        )
        if not references:
            return ()
        run_root = Path(row.canonical_run_path) if row.canonical_run_path else path.parent
        state = self._json(run_root / "state.json")
        registry = state.get("evidence_registry", {})
        if not isinstance(registry, dict):
            registry = {}
        investigation = self._json(run_root / "phase1" / "investigation.json")
        rationale_by_reference: dict[str, list[str]] = {}
        rationales = investigation.get("rationales", [])
        rationale_records: dict[str, dict[str, Any]] = {}
        if isinstance(rationales, list):
            for rationale in rationales:
                if not isinstance(rationale, dict):
                    continue
                label = rationale.get("taxonomy_label")
                if not isinstance(label, str):
                    continue
                rationale_id = rationale.get("rationale_id")
                if isinstance(rationale_id, str):
                    rationale_records[rationale_id] = rationale
                for field in (
                    "pitch_evidence_ids",
                    "wiki_evidence_ids",
                    "historical_evidence_ids",
                ):
                    values = rationale.get(field, [])
                    if isinstance(values, list):
                        for reference in values:
                            if isinstance(reference, str):
                                rationale_by_reference.setdefault(reference, []).append(label)
        pitch_rows = {
            item["evidence_id"]: item["text"]
            for item in pitch_evidence_index(
                self.store.read_pitch(row.project_id, row.version_id)
            )
        }
        citations: list[AssessmentCitationView] = []
        for number, reference in enumerate(references, start=1):
            labels = tuple(dict.fromkeys(rationale_by_reference.get(reference, ())))
            if reference in rationale_records:
                payload = rationale_records[reference]
                label = str(payload.get("taxonomy_label") or reference)
                citation = AssessmentCitationView(
                    number=number,
                    reference_id=reference,
                    source_type="rationale",
                    title=self._title(label),
                    excerpt=str(payload.get("justification"))
                    if payload.get("justification")
                    else None,
                    source_reference="Phase 1 rationale record",
                    rationale_labels=(label,),
                )
            elif reference.startswith("P-") and reference in pitch_rows:
                citation = AssessmentCitationView(
                    number=number,
                    reference_id=reference,
                    source_type="pitch",
                    title="Current pitch",
                    excerpt=pitch_rows[reference],
                    source_reference="Immutable pitch version",
                    rationale_labels=labels,
                )
            else:
                payload = registry.get(reference)
                if isinstance(payload, dict):
                    is_precedent = reference.startswith("H-")
                    citation = AssessmentCitationView(
                        number=number,
                        reference_id=reference,
                        source_type="precedent" if is_precedent else "investment_memory",
                        title=(
                            str(payload.get("episode_slug") or "Historical pitch precedent")
                            if is_precedent
                            else str(payload.get("heading") or payload.get("source_path") or "Investment memory")
                        ),
                        excerpt=str(payload.get("text")) if payload.get("text") else None,
                        source_reference=str(payload.get("source_path")) if payload.get("source_path") else None,
                        episode_slug=str(payload.get("episode_slug")) if payload.get("episode_slug") else None,
                        decision_status=str(payload.get("decision_status")) if payload.get("decision_status") else None,
                        rationale_labels=labels,
                    )
                else:
                    citation = AssessmentCitationView(
                        number=number,
                        reference_id=reference,
                        source_type="unavailable",
                        title="Source detail unavailable",
                        rationale_labels=labels,
                    )
            citations.append(citation)
        return tuple(citations)

    def _present(self, path: Path, row: CanonicalAssessmentDetail) -> CanonicalAssessmentDetail:
        return row.model_copy(
            update={
                "decision_summary": self._summary(row),
                "citations": self._citations(path, row),
                "activity": self._activity(row),
            }
        )

    def ensure_assessment(
        self, project_id: str, version_id: str, vc_slug: str
    ) -> CanonicalAssessmentDetail:
        root = self._assessment_root(project_id, version_id, vc_slug)
        manifest = self._manifest(root)
        with self._guard:
            if manifest.is_file():
                return self._read(manifest)
            version = self.store.get_version(project_id, version_id)
            timestamp = _now()
            detail = CanonicalAssessmentDetail(
                assessment_id=str(uuid4()),
                project_id=project_id,
                version_id=version_id,
                vc_slug=vc_slug,
                pitch_sha256=version.pitch_sha256,
                status="queued",
                created_at=timestamp,
                updated_at=timestamp,
            )
            _write(manifest, detail.model_dump(by_alias=True, mode="json"))
            return detail

    def _find(self, assessment_id: str) -> Path:
        if not assessment_id or any(part in assessment_id for part in ("/", "\\", "..")):
            raise ValueError("invalid assessment identifier")
        for path in self.store.root.glob("*/versions/*/assessments/*/assessment.json"):
            try:
                row = self._read(path)
            except ValueError:
                continue
            if row.assessment_id == assessment_id:
                return path
        raise ValueError(f"unknown canonical assessment: {assessment_id}")

    def get_assessment(self, assessment_id: str) -> CanonicalAssessmentDetail:
        path = self._find(assessment_id)
        return self._present(path, self._read(path))

    def list_for_version(
        self, project_id: str, version_id: str
    ) -> tuple[CanonicalAssessmentDetail, ...]:
        root = self.store.version_root(project_id, version_id) / "assessments"
        if not root.is_dir():
            return ()
        rows = [
            self._present(path, self._read(path))
            for path in root.glob("*/assessment.json")
            if path.is_file()
        ]
        return tuple(sorted(rows, key=lambda row: (row.created_at, row.vc_slug)))

    @staticmethod
    def _usage(root: Path) -> dict[str, int | float]:
        path = root / "canonical-bootstrap" / "bootstrap.json"
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        usage = payload.get("usage") if isinstance(payload, dict) else None
        return dict(usage) if isinstance(usage, dict) else {}

    def run_assessment(
        self,
        assessment_id: str,
        emit: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> CanonicalAssessmentDetail:
        manifest = self._find(assessment_id)
        with self._guard:
            if assessment_id in self._active:
                raise AssessmentBusyError(f"assessment already running: {assessment_id}")
            current = self._read(manifest)
            if current.status == "complete":
                return current
            self._active.add(assessment_id)
            running = current.model_copy(
                update={"status": "running", "updated_at": _now(), "public_error": None}
            )
            _write(manifest, running.model_dump(by_alias=True, mode="json"))
        notify = emit or (lambda _stage, _payload: None)
        root = manifest.parent
        try:
            notify("phase1_running", {"vc_slug": current.vc_slug})
            project = self.store.get_project(current.project_id)
            pitch = self.store.read_pitch(current.project_id, current.version_id)
            baseline = self.baseline_builder(
                workspace=self.workspace,
                rehearsal_config=self.rehearsal_config,
                session_root=root,
                vc_slug=current.vc_slug,
                episode_slug=f"live-assessment-{assessment_id.replace('-', '')[:16]}",
                pitch=pitch,
                target_company_aliases=project.company_aliases,
            )
            rationales = tuple(getattr(baseline.investigation, "rationales", ()))
            labels = lambda direction: tuple(
                row.taxonomy_label for row in rationales if row.direction == direction
            )
            notify("phase2_running", {"vc_slug": current.vc_slug})
            decision = baseline.decision
            complete = current.model_copy(
                update={
                    "status": "complete",
                    "updated_at": _now(),
                    "canonical_run_path": str(Path(baseline.run_root).resolve()),
                    "contract_version": baseline.contract_version,
                    "phase1_status": baseline.phase1_status,
                    "phase2_status": baseline.phase2_status,
                    "decision": decision.decision,
                    "investment_likelihood": decision.investment_likelihood,
                    "decision_confidence": decision.decision_confidence,
                    "review_priority_score": decision.review_priority_score,
                    "decision_justification": decision.decision_justification,
                    "positive_rationales": labels("positive"),
                    "negative_rationales": labels("negative"),
                    "unresolved_rationales": labels("neutral"),
                    "usage": self._usage(root),
                    "public_error": None,
                }
            )
            _write(manifest, complete.model_dump(by_alias=True, mode="json"))
            notify("assessment_complete", {"vc_slug": current.vc_slug})
            return complete
        except Exception as exc:
            failed = current.model_copy(
                update={
                    "status": "failed",
                    "updated_at": _now(),
                    "public_error": str(exc) or type(exc).__name__,
                }
            )
            _write(manifest, failed.model_dump(by_alias=True, mode="json"))
            raise
        finally:
            with self._guard:
                self._active.discard(assessment_id)

    def register_rehearsal(self, assessment_id: str, session_id: str) -> CanonicalAssessmentDetail:
        manifest = self._find(assessment_id)
        with self._guard:
            current = self._read(manifest)
            sessions = tuple(dict.fromkeys((*current.rehearsal_session_ids, session_id)))
            updated = current.model_copy(
                update={"rehearsal_session_ids": sessions, "updated_at": _now()}
            )
            _write(manifest, updated.model_dump(by_alias=True, mode="json"))
            return updated
