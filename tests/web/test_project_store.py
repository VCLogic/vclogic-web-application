from __future__ import annotations

from hashlib import sha256
import json

import pytest

from vclogic_web.project_store import PitchProjectStore


def test_create_project_persists_verified_immutable_pitch(tmp_path) -> None:
    store = PitchProjectStore(tmp_path / "projects")

    project = store.create_project(
        display_name="ShiftPilot",
        company_aliases=("ShiftPilot", "Shift Pilot"),
        pitch_text="# ShiftPilot",
    )
    version = store.get_version(project.project_id, project.current_version_id)

    assert version.pitch_sha256 == sha256(b"# ShiftPilot\n").hexdigest()
    assert store.read_pitch(project.project_id, version.version_id) == "# ShiftPilot\n"
    assert project.company_aliases == ("ShiftPilot", "Shift Pilot")
    assert store.list_projects()[0].project_id == project.project_id


def test_unchanged_revision_reuses_version_and_changed_revision_preserves_history(
    tmp_path,
) -> None:
    store = PitchProjectStore(tmp_path / "projects")
    project = store.create_project(
        display_name="ShiftPilot",
        company_aliases=("ShiftPilot",),
        pitch_text="First pitch",
    )

    same = store.create_version(project.project_id, pitch_text="First pitch\n")
    revised = store.create_version(project.project_id, pitch_text="Revised pitch")

    assert same.version_id == project.current_version_id
    assert revised.version_id != same.version_id
    assert store.read_pitch(project.project_id, same.version_id) == "First pitch\n"
    assert store.read_pitch(project.project_id, revised.version_id) == "Revised pitch\n"
    assert store.get_project(project.project_id).current_version_id == revised.version_id


def test_invalid_identifiers_and_corrupt_pitch_are_rejected(tmp_path) -> None:
    store = PitchProjectStore(tmp_path / "projects")
    project = store.create_project(
        display_name="ShiftPilot",
        company_aliases=("ShiftPilot",),
        pitch_text="Pitch",
    )
    version = store.get_version(project.project_id, project.current_version_id)

    with pytest.raises(ValueError, match="invalid project identifier"):
        store.get_project("../escape")

    pitch_path = (
        tmp_path
        / "projects"
        / project.project_id
        / "versions"
        / version.version_id
        / "pitch.md"
    )
    pitch_path.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="digest"):
        store.read_pitch(project.project_id, version.version_id)


def test_blank_project_fields_are_rejected(tmp_path) -> None:
    store = PitchProjectStore(tmp_path / "projects")

    with pytest.raises(ValueError, match="display name"):
        store.create_project(display_name=" ", company_aliases=("X",), pitch_text="P")
    with pytest.raises(ValueError, match="alias"):
        store.create_project(display_name="X", company_aliases=(), pitch_text="P")
    with pytest.raises(ValueError, match="pitch"):
        store.create_project(display_name="X", company_aliases=("X",), pitch_text=" ")


def test_project_summary_counts_persisted_assessments_and_rehearsals(tmp_path) -> None:
    store = PitchProjectStore(tmp_path / "projects")
    project = store.create_project(
        display_name="ShiftPilot", company_aliases=("ShiftPilot",), pitch_text="Pitch"
    )
    assessment_root = (
        tmp_path / "projects" / project.project_id / "versions"
        / project.current_version_id / "assessments" / "charles"
    )
    assessment_root.mkdir(parents=True)
    (assessment_root / "assessment.json").write_text(json.dumps({
        "assessment_id": "a1", "rehearsal_session_ids": ["s1", "s2"]
    }), encoding="utf-8")

    summary = store.list_projects()[0]

    assert summary.assessment_count == 1
    assert summary.rehearsal_count == 2
