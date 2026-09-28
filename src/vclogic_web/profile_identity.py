"""Presentation-only identity enrichment from declared bundle source metadata."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path, PurePosixPath
import unicodedata

from vc_clone_graph.rehearsal_runtime import InvestorProfile

_MAX_METADATA_BYTES = 256 * 1024


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalized_name(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", _text(value)).casefold().split())


def enrich_identity(profile: InvestorProfile, files: dict[str, Path]) -> InvestorProfile:
    """Fill absent presentation fields without changing registry or source files.

    ``files`` must be the selected version's validated declared-file mapping. Only
    source profile JSON records with an exact normalized name match contribute.
    Conflicting source values are left unresolved; biography text is never parsed.
    """
    identity = _normalized_name(profile.display_name)
    needed = set()
    if not _text(profile.firm):
        needed.add("firm")
    if _normalized_name(profile.role) in {"", "investor"}:
        needed.add("role")
    if not identity or not needed:
        return profile

    candidates: dict[str, set[str]] = {key: set() for key in needed}
    for declared, path in files.items():
        relative = PurePosixPath(declared)
        if (relative.is_absolute() or ".." in relative.parts
                or not relative.parts or relative.parts[0] != "source"
                or relative.name != "profile.json"):
            continue
        try:
            with path.open("rb") as stream:
                raw = stream.read(_MAX_METADATA_BYTES + 1)
            if len(raw) > _MAX_METADATA_BYTES:
                continue
            data = json.loads(raw)
        except (OSError, ValueError, RecursionError):
            continue
        if not isinstance(data, dict) or _normalized_name(data.get("name")) != identity:
            continue
        for key in needed:
            value = _text(data.get(key))
            if value:
                candidates[key].add(value)

    updates = {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}
    return replace(profile, **updates) if updates else profile
