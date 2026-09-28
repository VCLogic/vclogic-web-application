from dataclasses import replace
import json
from pathlib import Path

import pytest
from vc_clone_graph.rehearsal_runtime import InvestorProfile
from vclogic_web.profile_identity import enrich_identity


def profile(tmp_path: Path) -> InvestorProfile:
    return InvestorProfile(vc_slug="mac-conwell", display_name="Mac Conwell", firm="",
                           role="Investor", wiki_path=tmp_path / "wiki",
                           registry_path=tmp_path / "mac-conwell.toml")


def source(tmp_path: Path, data: object) -> dict[str, Path]:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(data))
    return {"source/pitch-show/profile.json": path}


def test_fills_mac_firm_without_inferring_role_from_bio(tmp_path):
    original = profile(tmp_path)
    files = source(tmp_path, {"name": "Mac Conwell", "firm": "RareBreed Ventures",
                              "bio": "Mac is managing partner at RareBreed Ventures."})
    before = files["source/pitch-show/profile.json"].read_bytes()
    enriched = enrich_identity(original, files)
    assert enriched.firm == "RareBreed Ventures"
    assert enriched.role == "Investor"
    assert original.firm == ""
    assert enriched.registry_path == original.registry_path
    assert enriched.wiki_path == original.wiki_path
    assert files["source/pitch-show/profile.json"].read_bytes() == before


def test_requires_exact_normalized_identity(tmp_path):
    original = profile(tmp_path)
    files = source(tmp_path, {"name": "Mac Conwell Jr.", "firm": "Wrong Firm", "role": "Partner"})
    assert enrich_identity(original, files) is original
    files = source(tmp_path, {"name": "  MAC   CONWELL ", "firm": "RareBreed Ventures", "role": "Managing Partner"})
    assert enrich_identity(original, files).role == "Managing Partner"


def test_preserves_explicit_registry_values(tmp_path):
    original = replace(profile(tmp_path), firm="Registry Firm", role="Founder")
    files = source(tmp_path, {"name": "Mac Conwell", "firm": "Other Firm", "role": "Partner"})
    assert enrich_identity(original, files) is original


@pytest.mark.parametrize("data", [None, [], "text", {"name": "Mac Conwell", "firm": {}, "role": []}])
def test_malformed_metadata_falls_back(tmp_path, data):
    original = profile(tmp_path)
    assert enrich_identity(original, source(tmp_path, data)) is original


def test_invalid_json_and_missing_file_fall_back(tmp_path):
    original = profile(tmp_path)
    files = source(tmp_path, {})
    files["source/pitch-show/profile.json"].write_text("not JSON")
    assert enrich_identity(original, files) is original
    files["source/pitch-show/profile.json"].unlink()
    assert enrich_identity(original, files) is original


def test_uses_only_declared_source_profile_metadata(tmp_path):
    original = profile(tmp_path)
    files = source(tmp_path, {"name": "Mac Conwell", "firm": "RareBreed Ventures"})
    assert enrich_identity(original, {}) is original
    assert enrich_identity(original, {"inputs/profile.json": next(iter(files.values()))}) is original


def test_generic_source_and_blank_role(tmp_path):
    original = replace(profile(tmp_path), display_name="Other Person", role=" ")
    files = source(tmp_path, {"name": "Other Person", "firm": "Source Firm", "role": "Partner"})
    files = {"source/another-provider/profile.json": next(iter(files.values()))}
    enriched = enrich_identity(original, files)
    assert enriched.firm == "Source Firm"
    assert enriched.role == "Partner"


def test_conflicting_sources_do_not_guess(tmp_path):
    original = profile(tmp_path)
    files = source(tmp_path, {"name": "Mac Conwell", "firm": "First Firm", "role": "Partner"})
    second = tmp_path / "second.json"
    second.write_text(json.dumps({"name": "Mac Conwell", "firm": "Second Firm", "role": "Partner"}))
    files["source/second/profile.json"] = second
    enriched = enrich_identity(original, files)
    assert enriched.firm == ""
    assert enriched.role == "Partner"
