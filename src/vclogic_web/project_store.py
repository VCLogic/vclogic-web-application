"""Verified filesystem storage for durable pitch projects and versions."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from threading import RLock
from typing import Any
from uuid import uuid4

from .models import PitchProjectDetail, PitchProjectSummary, PitchVersionView


_IDENTIFIER = re.compile(r"^[0-9a-f-]{36}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalized_pitch(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("pitch text must not be blank")
    return text + "\n"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


class PitchProjectStore:
    """Store immutable pitch versions with a rebuildable project index."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._guard = RLock()

    @staticmethod
    def _identifier(value: str, kind: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError(f"invalid {kind} identifier")
        return value

    def _project_root(self, project_id: str) -> Path:
        return self.root / self._identifier(project_id, "project")

    def _version_root(self, project_id: str, version_id: str) -> Path:
        return (
            self._project_root(project_id)
            / "versions"
            / self._identifier(version_id, "version")
        )

    def version_root(self, project_id: str, version_id: str) -> Path:
        """Return a verified pitch-version directory for subordinate artifacts."""
        self.get_version(project_id, version_id)
        return self._version_root(project_id, version_id)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid project artifact: {path.name}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"invalid project artifact: {path.name}")
        return value

    def _write_version(self, project_id: str, pitch: str, created_at: str) -> PitchVersionView:
        version_id = str(uuid4())
        version_root = self._version_root(project_id, version_id)
        version_root.mkdir(parents=True, exist_ok=False)
        pitch_path = version_root / "pitch.md"
        pitch_path.write_text(pitch, encoding="utf-8")
        view = PitchVersionView(
            version_id=version_id,
            project_id=project_id,
            created_at=created_at,
            pitch_sha256=sha256(pitch.encode("utf-8")).hexdigest(),
            character_count=len(pitch),
        )
        _atomic_json(
            version_root / "version.json",
            view.model_dump(by_alias=True, mode="json"),
        )
        return view

    def create_project(
        self,
        *,
        display_name: str,
        company_aliases: tuple[str, ...],
        pitch_text: str,
    ) -> PitchProjectDetail:
        name = display_name.strip()
        if not name:
            raise ValueError("project display name must not be blank")
        aliases = tuple(dict.fromkeys(value.strip() for value in company_aliases if value.strip()))
        if not aliases:
            raise ValueError("at least one company alias is required")
        pitch = _normalized_pitch(pitch_text)
        with self._guard:
            project_id = str(uuid4())
            created_at = _now()
            version = self._write_version(project_id, pitch, created_at)
            payload = {
                "schema": "vc-clone-pitch-project-v1",
                "project_id": project_id,
                "display_name": name,
                "company_aliases": list(aliases),
                "created_at": created_at,
                "updated_at": created_at,
                "current_version_id": version.version_id,
            }
            _atomic_json(self._project_root(project_id) / "project.json", payload)
            return self.get_project(project_id)

    def create_version(self, project_id: str, *, pitch_text: str) -> PitchVersionView:
        pitch = _normalized_pitch(pitch_text)
        digest = sha256(pitch.encode("utf-8")).hexdigest()
        with self._guard:
            project = self.get_project(project_id)
            for version in project.versions:
                if version.pitch_sha256 == digest:
                    return version
            created_at = _now()
            version = self._write_version(project_id, pitch, created_at)
            payload = self._read_json(self._project_root(project_id) / "project.json")
            payload["current_version_id"] = version.version_id
            payload["updated_at"] = created_at
            _atomic_json(self._project_root(project_id) / "project.json", payload)
            return version

    def get_version(self, project_id: str, version_id: str) -> PitchVersionView:
        root = self._version_root(project_id, version_id)
        if not root.is_dir():
            raise ValueError(f"unknown pitch version: {version_id}")
        return PitchVersionView.model_validate(self._read_json(root / "version.json"))

    def read_pitch(self, project_id: str, version_id: str) -> str:
        version = self.get_version(project_id, version_id)
        try:
            pitch = (self._version_root(project_id, version_id) / "pitch.md").read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise ValueError("pitch artifact is missing") from exc
        if sha256(pitch.encode("utf-8")).hexdigest() != version.pitch_sha256:
            raise ValueError("pitch digest verification failed")
        return pitch

    def _versions(self, project_id: str) -> tuple[PitchVersionView, ...]:
        versions_root = self._project_root(project_id) / "versions"
        rows = [
            self.get_version(project_id, path.name)
            for path in versions_root.iterdir()
            if path.is_dir() and _IDENTIFIER.fullmatch(path.name)
        ]
        return tuple(sorted(rows, key=lambda row: (row.created_at, row.version_id)))

    def get_project(self, project_id: str) -> PitchProjectDetail:
        root = self._project_root(project_id)
        if not root.is_dir():
            raise ValueError(f"unknown pitch project: {project_id}")
        payload = self._read_json(root / "project.json")
        versions = self._versions(project_id)
        if not versions:
            raise ValueError("pitch project has no verified versions")
        current = str(payload.get("current_version_id", ""))
        if current not in {version.version_id for version in versions}:
            raise ValueError("pitch project current version is invalid")
        return PitchProjectDetail(
            project_id=project_id,
            display_name=str(payload["display_name"]),
            company_aliases=tuple(payload["company_aliases"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            current_version_id=current,
            version_count=len(versions),
            versions=versions,
        )

    def list_projects(self) -> tuple[PitchProjectSummary, ...]:
        rows: list[PitchProjectSummary] = []
        for path in self.root.iterdir():
            if not path.is_dir() or not _IDENTIFIER.fullmatch(path.name):
                continue
            detail = self.get_project(path.name)
            assessment_count = 0
            rehearsal_ids: set[str] = set()
            for manifest in path.glob("versions/*/assessments/*/assessment.json"):
                try:
                    payload = self._read_json(manifest)
                except ValueError:
                    continue
                assessment_count += 1
                sessions = payload.get("rehearsal_session_ids", ())
                if isinstance(sessions, list):
                    rehearsal_ids.update(str(value) for value in sessions if value)
            rows.append(PitchProjectSummary(
                **detail.model_dump(exclude={"schema_version", "versions", "assessment_count", "rehearsal_count"}),
                assessment_count=assessment_count,
                rehearsal_count=len(rehearsal_ids),
            ))
        return tuple(sorted(rows, key=lambda row: (row.updated_at, row.project_id), reverse=True))
