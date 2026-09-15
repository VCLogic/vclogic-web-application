"""Independent per-investor assessment orchestration and deterministic shortlist views."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

from .models import (
    CanonicalAssessmentDetail,
    InvestorComparisonDetail,
    MatchAssessmentRow,
    MatchRunDetail,
    RelativeFitView,
)
from .project_store import PitchProjectStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def relative_fit(score: float, reference_scores: Iterable[float]) -> RelativeFitView:
    values = tuple(
        value
        for value in reference_scores
        if isinstance(value, (int, float)) and 0 <= float(value) <= 1
    )
    if len(values) < 10:
        return RelativeFitView(percentile=None, reference_count=len(values))
    percentile = round(100 * sum(float(value) <= score for value in values) / len(values), 1)
    return RelativeFitView(percentile=percentile, reference_count=len(values))


def load_reference_scores(path: Path, vc_slugs: Iterable[str]) -> dict[str, tuple[float, ...]]:
    requested = tuple(vc_slugs)
    results: dict[str, list[float]] = {slug: [] for slug in requested}
    if not Path(path).is_file():
        return {slug: () for slug in requested}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            short_slug = str(row.get("vc_slug", ""))
            matching = next(
                (slug for slug in requested if slug == short_slug or slug.startswith(short_slug + "-")),
                None,
            )
            if matching is None:
                continue
            try:
                value = float(row["investment_likelihood"])
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= value <= 1:
                results[matching].append(value)
    return {slug: tuple(values) for slug, values in results.items()}


class MatchingService:
    def __init__(
        self,
        *,
        store: PitchProjectStore,
        assessments: Any,
        reference_scores: Mapping[str, Iterable[float]] | None = None,
        max_concurrency: int = 2,
    ) -> None:
        self.store = store
        self.assessments = assessments
        self.reference_scores = {
            slug: tuple(values) for slug, values in (reference_scores or {}).items()
        }
        self.max_concurrency = max(1, min(int(max_concurrency), 6))
        self._guard = RLock()

    def _match_root(self, project_id: str, version_id: str, match_id: str) -> Path:
        if not match_id or any(part in match_id for part in ("/", "\\", "..")):
            raise ValueError("invalid match identifier")
        return self.store.version_root(project_id, version_id) / "matches" / match_id

    def _comparison_path(self, project_id: str, version_id: str) -> Path:
        return self.store.version_root(project_id, version_id) / "comparison.json"

    def _find(self, match_id: str) -> Path:
        for path in self.store.root.glob("*/versions/*/matches/*/match.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("match_id") == match_id:
                return path
        raise ValueError(f"unknown investor match: {match_id}")

    @staticmethod
    def _payload(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("investor match artifact is invalid") from exc
        if not isinstance(payload, dict):
            raise ValueError("investor match artifact is invalid")
        return payload

    def create_match(
        self, project_id: str, version_id: str, vc_slugs: tuple[str, ...]
    ) -> MatchRunDetail:
        if not 2 <= len(vc_slugs) <= 6:
            raise ValueError("investor match requires 2 to 6 profiles")
        if len(set(vc_slugs)) != len(vc_slugs):
            raise ValueError("investor profiles must be distinct")
        assessment_rows = [
            self.assessments.ensure_assessment(project_id, version_id, slug)
            for slug in vc_slugs
        ]
        match_id = str(uuid4())
        timestamp = _now()
        payload = {
            "schema": "vc-clone-investor-match-v1",
            "match_id": match_id,
            "project_id": project_id,
            "version_id": version_id,
            "selected_vc_slugs": list(vc_slugs),
            "assessment_ids": [row.assessment_id for row in assessment_rows],
            "status": "queued",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        _write(self._match_root(project_id, version_id, match_id) / "match.json", payload)
        return self.get_match(match_id)

    def _row(self, assessment: CanonicalAssessmentDetail) -> MatchAssessmentRow:
        fit = RelativeFitView(percentile=None, reference_count=0)
        if assessment.investment_likelihood is not None:
            fit = relative_fit(
                assessment.investment_likelihood,
                self.reference_scores.get(assessment.vc_slug, ()),
            )
        return MatchAssessmentRow(
            assessment_id=assessment.assessment_id,
            vc_slug=assessment.vc_slug,
            status=assessment.status,
            decision=assessment.decision,
            investment_likelihood=assessment.investment_likelihood,
            decision_confidence=assessment.decision_confidence,
            positive_rationales=assessment.positive_rationales,
            negative_rationales=assessment.negative_rationales,
            unresolved_rationales=assessment.unresolved_rationales,
            relative_fit=fit,
            public_error=assessment.public_error,
            reused=assessment.status == "complete",
        )

    @staticmethod
    def _comparison_status(rows: list[MatchAssessmentRow]) -> str:
        statuses = {row.status for row in rows}
        if statuses == {"complete"}:
            return "complete"
        if "running" in statuses or "queued" in statuses:
            return "running"
        if "complete" in statuses and "failed" in statuses:
            return "partial"
        return "failed"

    def _decorate_rows(
        self, rows: list[MatchAssessmentRow], selected: tuple[str, ...]
    ) -> list[MatchAssessmentRow]:
        completed = [
            row
            for row in rows
            if row.status == "complete" and row.investment_likelihood is not None
        ]
        leader = max((row.investment_likelihood for row in completed), default=None)
        result = [
            row.model_copy(
                update={
                    "highest_estimated_fit": leader is not None
                    and row.investment_likelihood == leader,
                    "leading_group": leader is not None
                    and row.investment_likelihood is not None
                    and row.investment_likelihood >= leader - 0.05 - 1e-9,
                }
            )
            for row in rows
        ]
        order = {slug: index for index, slug in enumerate(selected)}
        result.sort(
            key=lambda row: (
                row.status != "complete",
                -(row.investment_likelihood if row.investment_likelihood is not None else -1),
                order[row.vc_slug],
            )
        )
        return result

    def update_comparison(
        self, project_id: str, version_id: str, vc_slugs: tuple[str, ...]
    ) -> InvestorComparisonDetail:
        if not 1 <= len(vc_slugs) <= 6:
            raise ValueError("investor comparison requires 1 to 6 profiles")
        if len(set(vc_slugs)) != len(vc_slugs):
            raise ValueError("investor profiles must be distinct")
        path = self._comparison_path(project_id, version_id)
        with self._guard:
            if path.is_file():
                payload = self._payload(path)
                selected = tuple(
                    dict.fromkeys((*payload.get("selected_vc_slugs", ()), *vc_slugs))
                )
                if len(selected) > 6:
                    raise ValueError("investor comparison supports at most 6 profiles")
                payload["selected_vc_slugs"] = list(selected)
                payload["updated_at"] = _now()
            else:
                timestamp = _now()
                payload = {
                    "schema": "vc-clone-investor-comparison-v1",
                    "comparison_id": f"comparison-{version_id}",
                    "project_id": project_id,
                    "version_id": version_id,
                    "selected_vc_slugs": list(vc_slugs),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            for slug in payload["selected_vc_slugs"]:
                self.assessments.ensure_assessment(project_id, version_id, slug)
            _write(path, payload)
        return self.get_comparison(project_id, version_id)

    def get_comparison(
        self, project_id: str, version_id: str
    ) -> InvestorComparisonDetail | None:
        path = self._comparison_path(project_id, version_id)
        if not path.is_file():
            return None
        payload = self._payload(path)
        selected = tuple(str(value) for value in payload.get("selected_vc_slugs", ()))
        assessments = {
            row.vc_slug: row
            for row in self.assessments.list_for_version(project_id, version_id)
        }
        rows = self._decorate_rows(
            [self._row(assessments[slug]) for slug in selected if slug in assessments],
            selected,
        )
        missing = tuple(row.vc_slug for row in rows if row.status != "complete")
        return InvestorComparisonDetail(
            comparison_id=str(payload["comparison_id"]),
            project_id=project_id,
            version_id=version_id,
            selected_vc_slugs=selected,
            status=self._comparison_status(rows),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            missing_vc_slugs=missing,
            assessments=tuple(rows),
        )

    def get_match(self, match_id: str) -> MatchRunDetail:
        path = self._find(match_id)
        payload = self._payload(path)
        rows = [self._row(self.assessments.get_assessment(value)) for value in payload["assessment_ids"]]
        completed = [row for row in rows if row.status == "complete" and row.investment_likelihood is not None]
        leader = max((row.investment_likelihood for row in completed), default=None)
        decorated = [
            row.model_copy(
                update={
                    "highest_estimated_fit": leader is not None and row.investment_likelihood == leader,
                    "leading_group": (
                        leader is not None
                        and row.investment_likelihood is not None
                        and row.investment_likelihood >= leader - 0.05 - 1e-9
                    ),
                }
            )
            for row in rows
        ]
        order = {slug: index for index, slug in enumerate(payload["selected_vc_slugs"])}
        decorated.sort(
            key=lambda row: (
                row.status != "complete",
                -(row.investment_likelihood if row.investment_likelihood is not None else -1),
                order[row.vc_slug],
            )
        )
        statuses = {row.status for row in decorated}
        if statuses == {"complete"}:
            status = "complete"
        elif "complete" in statuses and "failed" in statuses:
            status = "partial"
        elif statuses == {"failed"}:
            status = "failed"
        elif "running" in statuses:
            status = "running"
        else:
            status = str(payload.get("status", "queued"))
        return MatchRunDetail(
            match_id=match_id,
            project_id=str(payload["project_id"]),
            version_id=str(payload["version_id"]),
            selected_vc_slugs=tuple(payload["selected_vc_slugs"]),
            status=status,
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            assessments=tuple(decorated),
        )

    def list_for_version(self, project_id: str, version_id: str) -> tuple[MatchRunDetail, ...]:
        root = self.store.version_root(project_id, version_id) / "matches"
        if not root.is_dir():
            return ()
        rows: list[MatchRunDetail] = []
        for path in root.glob("*/match.json"):
            payload = self._payload(path)
            match_id = payload.get("match_id")
            if isinstance(match_id, str):
                rows.append(self.get_match(match_id))
        return tuple(sorted(rows, key=lambda row: (row.created_at, row.match_id), reverse=True))

    def _set_status(self, path: Path, status: str) -> None:
        with self._guard:
            payload = self._payload(path)
            payload["status"] = status
            payload["updated_at"] = _now()
            _write(path, payload)

    def run_match(
        self,
        match_id: str,
        emit: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> MatchRunDetail:
        path = self._find(match_id)
        payload = self._payload(path)
        self._set_status(path, "running")
        notify = emit or (lambda _stage, _payload: None)

        def run_one(assessment_id: str) -> None:
            row = self.assessments.get_assessment(assessment_id)
            notify("assessment_running", {"vc_slug": row.vc_slug, "assessment_id": assessment_id})
            try:
                self.assessments.run_assessment(assessment_id, emit=notify)
            except Exception as exc:
                notify(
                    "assessment_failed",
                    {"vc_slug": row.vc_slug, "assessment_id": assessment_id, "message": str(exc)},
                )
            else:
                notify("assessment_complete", {"vc_slug": row.vc_slug, "assessment_id": assessment_id})

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = [executor.submit(run_one, value) for value in payload["assessment_ids"]]
            for future in as_completed(futures):
                future.result()
                current = self.get_match(match_id)
                self._set_status(path, current.status)
        result = self.get_match(match_id)
        self._set_status(path, result.status)
        return self.get_match(match_id)

    def retry(self, match_id: str, vc_slug: str) -> MatchRunDetail:
        current = self.get_match(match_id)
        row = next((value for value in current.assessments if value.vc_slug == vc_slug), None)
        if row is None:
            raise ValueError(f"investor is not part of match: {vc_slug}")
        if row.status != "failed":
            raise ValueError("only a failed assessment can be retried")
        self.assessments.run_assessment(row.assessment_id)
        path = self._find(match_id)
        refreshed = self.get_match(match_id)
        self._set_status(path, refreshed.status)
        return self.get_match(match_id)
