"""Investor-like profile, memory, and stable rationale graph views."""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
import glob
import json
from pathlib import Path
import re
from statistics import fmean
from typing import Any

from vc_clone_graph.rehearsal_runtime import InvestorProfile, list_investors
from .investor_presentation import INVESTOR_PRESENTATION
from .models import (
    EvidenceView,
    InvestorCard,
    InvestorProfileResponse,
    MemorySearchResponse,
    ProfileSection,
    RationaleEdgeView,
    RationaleGraphResponse,
    RationaleNodeView,
)


DISCLOSURE = (
    "Simulation reconstructed from public traces; not the real investor and "
    "not endorsed by them."
)
_WORDS = re.compile(r"[a-z0-9]+")
_HORIZONTAL_RULE = re.compile(r"^\s{0,3}(?:[-*_]\s*){3,}$")
_LIST_ITEM = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
_EVIDENCE_MARKER = re.compile(r"^\s*\[ev:[^]]+\](?:\s|$)")
_PROVENANCE_LABEL = re.compile(
    r"^(?P<label>sources?|provenance):\s*(?P<value>.*)$", re.IGNORECASE
)
_PROVENANCE_HEADING = re.compile(r"^#+\s*(?:sources?|provenance)\b", re.IGNORECASE)
_PROVENANCE_SIGNAL = re.compile(
    r"https?://|"
    r"\b(?:talk|podcast|video|article|blog|post|interview|medium|website):[\w./-]+|"
    r"(?:^|[\s`(])(?:data|inputs|outputs|reports|evaluation|wiki|src|tests)/[\w./-]+|"
    r"(?:[\w.-]+/)+[\w.-]+\.(?:json|md|txt|toml|ya?ml|csv)\b|"
    r"\b(?:sha(?:-?256)?[:=]\s*)?[a-f0-9]{40,64}\b",
    re.IGNORECASE,
)
_MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+.*$")
_STRUCTURED_EVIDENCE = re.compile(
    r"^\s*\[ev:(?P<evidence_id>[^]]+)\]\s+"
    r"label=(?P<label>\S+)\s+direction=(?P<direction>\S+)\s+"
    r"source=(?P<source>\S+)\s*(?:>\s*)?"
    r"(?P<quote>[\"'].+?[\"'])\s*$",
    re.DOTALL,
)
_EVIDENCE_DIRECTIONS = {"positive", "negative", "neutral", "mixed", "unresolved"}


def _is_provenance_block(lines: list[str]) -> bool:
    if not lines:
        return False
    if _PROVENANCE_HEADING.match(lines[0]):
        return True
    label = _PROVENANCE_LABEL.fullmatch(lines[0])
    if label is None:
        return False
    if label.group("label").casefold() == "provenance":
        return True
    value = label.group("value").strip()
    details = ([value] if value else []) + lines[1:]
    if not details:
        return True
    return all(_PROVENANCE_SIGNAL.search(detail) is not None for detail in details)


def _truncate_preview(value: str, *, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    shortened = compact[: limit - 1].rsplit(maxsplit=1)[0].rstrip()
    return f"{shortened}…"


def _strip_list_markup(line: str) -> str:
    text = _LIST_ITEM.sub("", line).strip()
    return re.sub(r"(?<!\w)([*_]{1,3})(.+?)\1(?!\w)", r"\2", text)


def _chapter_preview(text: str, *, limit: int = 620) -> str:
    """Return the first prose block, compacted for profile-card display."""
    list_fallback = ""
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        normalized_lines = [
            re.sub(r"^(?:>\s*)+", "", line).strip() for line in lines
        ]
        if _is_provenance_block(normalized_lines):
            continue
        content_lines = [
            line
            for line in normalized_lines
            if line
            and not _EVIDENCE_MARKER.match(line)
            and not line.startswith("#")
            and not _HORIZONTAL_RULE.fullmatch(line)
        ]
        if not content_lines:
            continue
        if all(_LIST_ITEM.match(line) for line in content_lines):
            list_items = [_strip_list_markup(line) for line in content_lines]
            if all(_PROVENANCE_SIGNAL.search(item) for item in list_items):
                continue
            if not list_fallback:
                list_fallback = _truncate_preview(
                    " ".join(list_items),
                    limit=limit,
                )
            continue
        prose = " ".join(content_lines)
        return _truncate_preview(prose, limit=limit)
    return list_fallback


def _tokens(value: str) -> set[str]:
    return set(_WORDS.findall(value.casefold()))


def _friendly_source_title(path: Path) -> str:
    return re.sub(r"[-_]+", " ", path.stem).title()


def _strip_balanced_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _clean_memory_block(paragraph: str) -> str:
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    normalized = [
        re.sub(r"^(?:>\s*)+", "", line).strip() for line in lines
    ]
    if _is_provenance_block(normalized):
        return ""
    content = [
        line for line in normalized if not _MARKDOWN_HEADING.fullmatch(line)
    ]
    if _is_provenance_block(content):
        return ""
    return "\n".join(content).strip()


def _like_name(display_name: str) -> str:
    return f"{display_name}-like Investor"


class ProfileService:
    def __init__(self, input_root: Path, *, workspace: Path) -> None:
        self.input_root = Path(input_root).resolve()
        self.workspace = Path(workspace).resolve()
        if not self.input_root.is_relative_to(self.workspace):
            raise ValueError("profile input root must be inside the workspace")
        self._profiles = {
            row.vc_slug: row for row in list_investors(self.input_root)
        }

    def _profile(self, vc_slug: str) -> InvestorProfile:
        try:
            return self._profiles[vc_slug]
        except KeyError as exc:
            raise ValueError(f"unknown investor profile: {vc_slug}") from exc

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.workspace).as_posix()

    def _card(self, profile: InvestorProfile) -> InvestorCard:
        recurring = self._recurring(profile.vc_slug)
        displayed = tuple(labels[:4] for labels, _ in recurring)
        displayed_counts = tuple(
            {label: counts[label] for label in labels}
            for labels, (_, counts) in zip(displayed, recurring, strict=True)
        )
        positive, negative, unresolved = displayed
        positive_counts, negative_counts, unresolved_counts = displayed_counts
        presentation = INVESTOR_PRESENTATION.get(profile.vc_slug)
        investigation_count = len(self._investigations(profile.vc_slug))
        return InvestorCard(
            vc_slug=profile.vc_slug,
            display_name=_like_name(profile.display_name),
            firm=profile.firm,
            role=profile.role,
            disclosure=DISCLOSURE,
            summary=f"A source-linked simulation of {profile.display_name}'s observable investment approach.",
            evidence_coverage=min(1.0, investigation_count / 10) if investigation_count else None,
            portrait_path=presentation.portrait_path if presentation else None,
            portrait_alt=presentation.portrait_alt if presentation else None,
            source_profile_url=(str(presentation.source_profile_url) if presentation else None),
            photo_attribution=presentation.photo_attribution if presentation else None,
            recurring_positive_rationales=positive,
            recurring_negative_rationales=negative,
            recurring_unresolved_rationales=unresolved,
            recurring_positive_counts=positive_counts,
            recurring_negative_counts=negative_counts,
            recurring_unresolved_counts=unresolved_counts,
        )

    def list_profiles(self) -> tuple[InvestorCard, ...]:
        return tuple(
            self._card(profile)
            for profile in sorted(self._profiles.values(), key=lambda row: row.display_name)
        )

    def profile(self, vc_slug: str) -> InvestorProfileResponse:
        profile = self._profile(vc_slug)
        sections: list[ProfileSection] = []
        for path in sorted(profile.wiki_path.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                continue
            heading = next(
                (line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")),
                path.stem.replace("-", " ").title(),
            )
            sections.append(
                ProfileSection(
                    section_id=path.relative_to(profile.wiki_path).as_posix(),
                    title=heading,
                    body=text,
                    preview=_chapter_preview(text),
                    character_count=len(text),
                    source_paths=(self._relative(path),),
                )
            )
        return InvestorProfileResponse(
            investor=self._card(profile), sections=tuple(sections)
        )

    def _search_memory_candidates(
        self, vc_slug: str, query: str
    ) -> list[tuple[int, EvidenceView]]:
        profile = self._profile(vc_slug)
        query_tokens = _tokens(query)
        if not query_tokens:
            raise ValueError("memory search query is empty")
        candidates: list[tuple[int, tuple[str, str], EvidenceView]] = []
        for path in sorted(profile.wiki_path.rglob("*")):
            if not path.is_file() or path.suffix.casefold() not in {".md", ".txt", ".json"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            paragraphs = [row.strip() for row in re.split(r"\n\s*\n", text) if row.strip()]
            for position, paragraph in enumerate(paragraphs):
                cleaned = _clean_memory_block(paragraph)
                if not cleaned:
                    continue
                match = _STRUCTURED_EVIDENCE.fullmatch(cleaned)
                if match:
                    parsed_direction = match.group("direction").casefold()
                    direction = (
                        parsed_direction
                        if parsed_direction in _EVIDENCE_DIRECTIONS
                        else None
                    )
                    excerpt = _strip_balanced_quotes(match.group("quote"))
                    evidence_id = match.group("evidence_id")
                    rationale_label = match.group("label")
                    source_reference = match.group("source")
                    source_kind = source_reference.partition(":")[0] or "wiki"
                else:
                    excerpt = " ".join(cleaned.split())
                    evidence_id = f"memory-{path.stem}-{position}"
                    rationale_label = None
                    direction = None
                    source_reference = None
                    source_kind = "wiki"
                searchable = " ".join(
                    value
                    for value in (
                        excerpt,
                        rationale_label,
                        direction,
                        source_reference,
                        _friendly_source_title(path),
                    )
                    if value
                )
                score = len(query_tokens & _tokens(searchable))
                if score == 0:
                    continue
                relative_path = self._relative(path)
                dedupe_key = (
                    relative_path,
                    " ".join(excerpt.casefold().split()),
                )
                candidates.append(
                    (
                        score,
                        dedupe_key,
                        EvidenceView(
                            evidence_id=evidence_id,
                            source_kind=source_kind,
                            source_path=relative_path,
                            source_title=_friendly_source_title(path),
                            excerpt=excerpt[:2_000],
                            rationale_label=rationale_label,
                            direction=direction,
                            source_reference=source_reference,
                        ),
                    )
                )
        candidates.sort(
            key=lambda row: (-row[0], row[2].source_path, row[2].evidence_id)
        )
        seen: set[tuple[str, str]] = set()
        scored: list[tuple[int, EvidenceView]] = []
        for score, dedupe_key, view in candidates:
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            scored.append((score, view))
        return scored

    def search_memory(
        self,
        vc_slug: str,
        query: str,
        *,
        page: int = 1,
        page_size: int = 5,
    ) -> MemorySearchResponse:
        if page < 1 or not 1 <= page_size <= 20:
            raise ValueError("invalid memory search pagination")
        scored = self._search_memory_candidates(vc_slug, query)
        total_results = len(scored)
        total_pages = (total_results + page_size - 1) // page_size
        effective_page = min(page, total_pages) if total_pages else 1
        start = (effective_page - 1) * page_size
        return MemorySearchResponse(
            query=query,
            results=tuple(
                row for _, row in scored[start : start + page_size]
            ),
            page=effective_page,
            page_size=page_size,
            total_results=total_results,
            total_pages=total_pages,
        )

    def _canonical_key(self, profile: InvestorProfile) -> str:
        return "-".join(_WORDS.findall(profile.display_name.casefold()))

    def _investigations(self, vc_slug: str) -> tuple[dict[str, Any], ...]:
        profile = self._profile(vc_slug)
        registry_path = self.workspace / "evaluation/canonical_runs_v4_v41_portfolio_2026-08-15.json"
        if not registry_path.is_file():
            return ()
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        entry = registry.get("investors", {}).get(self._canonical_key(profile), {})
        rows: list[dict[str, Any]] = []
        seen_paths: set[Path] = set()
        for source in entry.get("sources", []):
            pattern = source.get("path")
            if source.get("kind") != "summary_glob" or not isinstance(pattern, str):
                continue
            for summary_text in glob.glob(str(registry_path.parent / pattern)):
                investigation = (
                    Path(summary_text).parent / "phase1/investigation.json"
                ).resolve()
                if investigation.is_file() and investigation not in seen_paths:
                    seen_paths.add(investigation)
                    payload = json.loads(investigation.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        rows.append(payload)
        return tuple(rows)

    @lru_cache(maxsize=16)
    def _aggregate(
        self, vc_slug: str
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str], int], int]:
        labels: dict[str, list[dict[str, Any]]] = defaultdict(list)
        pairs: Counter[tuple[str, str]] = Counter()
        investigations = self._investigations(vc_slug)
        for investigation in investigations:
            episode_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in investigation.get("rationales", []):
                if not isinstance(row, dict) or not isinstance(row.get("taxonomy_label"), str):
                    continue
                label = row["taxonomy_label"]
                episode_rows[label].append(row)
            for label, rows in episode_rows.items():
                representative = dict(rows[0])
                representative["confidence"] = fmean(
                    float(row.get("confidence", 0)) for row in rows
                )
                if any(row.get("salience") == "primary" for row in rows):
                    representative["salience"] = "primary"
                labels[label].append(representative)
            unique = sorted(episode_rows)
            for index, left in enumerate(unique):
                for right in unique[index + 1 :]:
                    pairs[(left, right)] += 1
        return dict(labels), dict(pairs), len(investigations)

    @lru_cache(maxsize=1)
    def _taxonomy(self) -> dict[str, dict[str, Any]]:
        path = self.input_root / "taxonomy/codebook_v_final.json"
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return {}
        return {
            row["label"]: row
            for row in payload
            if isinstance(row, dict) and isinstance(row.get("label"), str)
        }

    def _recurring(
        self, vc_slug: str
    ) -> tuple[tuple[tuple[str, ...], dict[str, int]], ...]:
        labels, _, _ = self._aggregate(vc_slug)
        ranked: dict[str, list[tuple[int, str]]] = {
            "positive": [],
            "negative": [],
            "unresolved": [],
        }
        for label, rows in labels.items():
            directions = Counter(str(row.get("direction")) for row in rows)
            ranked["positive"].append((directions["positive"], label))
            ranked["negative"].append((directions["negative"], label))
            ranked["unresolved"].append(
                (directions["neutral"] + directions["unresolved"], label)
            )
        recurring: list[tuple[tuple[str, ...], dict[str, int]]] = []
        for direction in ("positive", "negative", "unresolved"):
            ordered = tuple(
                (label, count)
                for count, label in sorted(
                    ranked[direction], key=lambda row: (-row[0], row[1])
                )
                if count
            )
            recurring.append(
                (
                    tuple(label for label, _ in ordered),
                    {label: count for label, count in ordered},
                )
            )
        return tuple(recurring)

    def rationale_graph(self, vc_slug: str) -> RationaleGraphResponse:
        labels, pairs, investigation_count = self._aggregate(vc_slug)
        taxonomy = self._taxonomy()
        weighted_degrees: Counter[str] = Counter()
        for (left, right), count in pairs.items():
            weighted_degrees[left] += count
            weighted_degrees[right] += count
        nodes: list[RationaleNodeView] = []
        for label, rows in sorted(labels.items()):
            directions = Counter(
                str(row.get("direction"))
                if row.get("direction") in {"positive", "negative", "neutral", "unresolved"}
                else "unresolved"
                for row in rows
            )
            active = [
                key
                for key in ("positive", "negative", "neutral", "unresolved")
                if directions[key]
            ]
            direction = active[0] if len(active) == 1 else "mixed"
            confidence = fmean(float(row.get("confidence", 0)) for row in rows)
            metadata = taxonomy.get(label, {})
            nodes.append(
                RationaleNodeView(
                    node_id=label,
                    taxonomy_label=label,
                    title=label.replace("_", " ").title(),
                    direction=direction,  # type: ignore[arg-type]
                    salience="primary" if any(row.get("salience") == "primary" for row in rows) else "secondary",
                    confidence=max(0.0, min(1.0, confidence)),
                    definition=metadata.get("definition"),
                    coarse_parent=metadata.get("coarse_parent"),
                    occurrence_count=len(rows),
                    investigation_count=investigation_count,
                    direction_counts=dict(directions),
                    weighted_degree=weighted_degrees[label],
                )
            )
        node_ids = {node.node_id for node in nodes}
        edges = tuple(
            RationaleEdgeView(
                edge_id=f"{left}--{right}",
                source=left,
                target=right,
                relationship="co_occurs_with",
                inference_status="observed_cooccurrence",
                occurrence_count=count,
            )
            for (left, right), count in sorted(pairs.items(), key=lambda row: (-row[1], row[0]))[:80]
            if count >= 2 and left in node_ids and right in node_ids
        )
        return RationaleGraphResponse(nodes=tuple(nodes), edges=edges)
