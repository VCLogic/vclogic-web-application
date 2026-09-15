import json
from dataclasses import replace
from pathlib import Path
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from vclogic_web.app import create_app
from vclogic_web.models import InvestorCard, RationaleEdgeView, RationaleNodeView
from vclogic_web.profiles import ProfileService, _chapter_preview


ROOT = Path(os.environ.get("VCLOGIC_PIPELINE_WORKSPACE",
    str(Path(__file__).resolve().parents[3] / "vclogic-vc-agentic-assessment"))).resolve()


def _memory_service(tmp_path: Path, blocks: str) -> tuple[ProfileService, str]:
    service = ProfileService(ROOT / "inputs", workspace=ROOT)
    slug = "charles-hudson-precursor-ventures"
    wiki = tmp_path / "inputs/wiki/charles"
    wiki.mkdir(parents=True)
    (wiki / "business_model_economics.md").write_text(blocks, encoding="utf-8")
    service.workspace = tmp_path
    service._profiles = {slug: replace(service._profiles[slug], wiki_path=wiki)}
    return service, slug


def _rationale(label: str, direction: str, confidence: float) -> dict[str, object]:
    return {
        "taxonomy_label": label,
        "direction": direction,
        "confidence": confidence,
    }


def test_gallery_uses_like_names_and_disclosure() -> None:
    service = ProfileService(ROOT / "inputs", workspace=ROOT)

    cards = service.list_profiles()
    charles = next(row for row in cards if row.vc_slug.startswith("charles"))

    assert charles.display_name == "Charles Hudson-like Investor"
    assert "not the real investor" in charles.disclosure.lower()
    assert charles.start_available
    assert charles.portrait_path == "/investors/charles-hudson-precursor-ventures.jpg"
    assert charles.portrait_alt == "Charles Hudson portrait"
    assert charles.source_profile_url.startswith("https://www.thepitch.show/investors/")
    assert charles.photo_attribution == "Photo: The Pitch"
    assert isinstance(charles.recurring_unresolved_rationales, tuple)
    investigation_count = len(service._investigations(charles.vc_slug))
    for rationales, counts in (
        (charles.recurring_positive_rationales, charles.recurring_positive_counts),
        (charles.recurring_negative_rationales, charles.recurring_negative_counts),
        (charles.recurring_unresolved_rationales, charles.recurring_unresolved_counts),
    ):
        assert set(counts) == set(rationales)
        assert all(
            isinstance(count, int) and 0 < count <= investigation_count
            for count in counts.values()
        )
    assert len(cards) == 6


def test_investor_card_recurrence_maps_default_empty_for_legacy_callers() -> None:
    card = InvestorCard(
        vc_slug="legacy",
        display_name="Legacy-like Investor",
        firm="Legacy Fund",
        role="Partner",
        disclosure="Simulation.",
    )

    assert card.recurring_positive_counts == {}
    assert card.recurring_negative_counts == {}
    assert card.recurring_unresolved_counts == {}


def test_gallery_recurrence_counts_are_distinct_by_investigation_and_stable(monkeypatch) -> None:
    investigations = (
        {
            "rationales": [
                _rationale("business_model_assessment", "positive", 0.8),
                _rationale("business_model_assessment", "positive", 0.6),
            ]
        },
        {
            "rationales": [
                _rationale("business_model_assessment", "positive", 0.9),
                _rationale("portfolio_conflict", "negative", 0.7),
                _rationale("market_size_assessment", "neutral", 0.5),
            ]
        },
        {
            "rationales": [
                _rationale("portfolio_conflict", "negative", 0.9),
                _rationale("market_size_assessment", "unresolved", 0.7),
            ]
        },
    )

    def card_for(rows: tuple[dict[str, Any], ...]) -> InvestorCard:
        service = ProfileService(ROOT / "inputs", workspace=ROOT)
        monkeypatch.setattr(service, "_investigations", lambda _vc_slug: rows)
        return service._card(service._profile("charles-hudson-precursor-ventures"))

    permuted = tuple(
        {"rationales": list(reversed(row["rationales"]))}
        for row in reversed(investigations)
    )
    first = card_for(investigations)
    second = card_for(permuted)

    assert first.recurring_positive_counts == {"business_model_assessment": 2}
    assert first.recurring_negative_counts == {"portfolio_conflict": 2}
    assert first.recurring_unresolved_counts == {"market_size_assessment": 2}
    assert first.recurring_positive_rationales == second.recurring_positive_rationales
    assert first.recurring_negative_rationales == second.recurring_negative_rationales
    assert first.recurring_unresolved_rationales == second.recurring_unresolved_rationales
    assert first.recurring_positive_counts == second.recurring_positive_counts
    assert first.recurring_negative_counts == second.recurring_negative_counts
    assert first.recurring_unresolved_counts == second.recurring_unresolved_counts


def test_profile_graph_has_valid_taxonomy_nodes(monkeypatch) -> None:
    service = ProfileService(ROOT / "inputs", workspace=ROOT)

    labels = list(service._taxonomy())[:2]
    monkeypatch.setattr(service, "_investigations", lambda _vc: ({
        "rationales": [_rationale(label, "supports", 0.8) for label in labels]
    },))
    graph = service.rationale_graph("charles-hudson-precursor-ventures")

    assert graph.nodes
    assert all(node.taxonomy_label for node in graph.nodes)
    assert all(
        edge.relationship
        in {"co_occurs_with", "conditions", "overrides", "constrains"}
        for edge in graph.edges
    )
    taxonomy = {
        row["label"]: row
        for row in json.loads(
            (ROOT / "inputs/taxonomy/codebook_v_final.json").read_text(encoding="utf-8")
        )
    }
    assert all(
        node.definition == taxonomy[node.taxonomy_label]["definition"]
        for node in graph.nodes
    )
    assert all(
        node.coarse_parent == taxonomy[node.taxonomy_label]["coarse_parent"]
        for node in graph.nodes
    )


def test_profile_sections_expose_preview_and_complete_body() -> None:
    service = ProfileService(ROOT / "inputs", workspace=ROOT)

    profile = service.profile("charles-hudson-precursor-ventures")
    section = next(
        row
        for row in profile.sections
        if row.section_id == "evidence/founder_team.md"
    )

    stored = (ROOT / section.source_paths[0]).read_text(encoding="utf-8").strip()
    assert section.body == stored
    assert section.character_count == len(stored)
    assert 0 < len(section.preview) <= 620
    assert "\n" not in section.preview
    assert not section.preview.startswith(("#", "-", "*", ">"))


def test_profile_preview_truncates_at_a_word_boundary() -> None:
    preview = _chapter_preview(
        "# Heading\n\n---\n\n- list only\n- still a list\n\n"
        + " ".join("abcdefghij" for _ in range(150))
    )

    assert preview.endswith("…")
    assert len(preview) <= 620
    assert preview == " ".join("abcdefghij" for _ in range(56)) + "…"


@pytest.mark.parametrize(
    "structural_list_block",
    (
        "# Heading\n- list item",
        "---\n- list item",
        "> # Heading\n> - blockquoted list item",
    ),
)
def test_profile_preview_skips_combined_structural_and_list_blocks(
    structural_list_block: str,
) -> None:
    text = f"{structural_list_block}\n\nThis is the first substantive prose paragraph."

    assert _chapter_preview(text) == "This is the first substantive prose paragraph."


@pytest.mark.parametrize(
    "provenance_block",
    (
        "Source: `data/investors/example.json` → `investment_theses`",
        "Provenance:\n- Repository: inputs/wiki/example.md\n- Imported verbatim",
        "Sources: https://example.com/interview",
        "Source: sha256: " + "a" * 64,
    ),
)
def test_profile_preview_skips_source_only_provenance_blocks(
    provenance_block: str,
) -> None:
    text = f"# Thesis\n\n{provenance_block}\n\nFounders must understand the market."

    assert _chapter_preview(text) == "Founders must understand the market."


@pytest.mark.parametrize(
    "prose",
    (
        "Source: founders who deeply understand customers build better products.",
        "Source: product/market fit is the core underwriting question.",
        "Source: `trust` is the foundation of the founder relationship.",
        "Source: the transcript reveals a consistent investment thesis.",
    ),
)
def test_profile_preview_preserves_prose_labeled_as_a_source(prose: str) -> None:

    assert _chapter_preview(prose) == prose


def test_profile_preview_preserves_mixed_source_and_prose_blocks() -> None:
    text = (
        "Source: https://example.com/interview\n"
        "The source supports a durable founder-market-fit thesis."
    )

    assert _chapter_preview(text) == " ".join(text.split())


def test_profile_preview_falls_back_to_substantive_list_text() -> None:
    text = (
        "# Constraints\n\n"
        "Source: `data/investors/example.json`\n\n"
        "## Fund mandate\n"
        "- **Firm:** Precursor Ventures.\n"
        "- **Stage:** Pre-seed."
    )

    assert _chapter_preview(text) == "Firm: Precursor Ventures. Stage: Pre-seed."


def test_profile_preview_fallback_skips_provenance_only_lists() -> None:
    text = (
        "## Sources\n"
        "- https://example.com/interview\n"
        "- `data/investors/example.json`\n\n"
        "## Fund mandate\n"
        "- Back founders with a distinctive market insight."
    )

    assert _chapter_preview(text) == "Back founders with a distinctive market insight."


@pytest.mark.parametrize("section_id", ("theses.md", "portfolio_and_constraints.md"))
def test_real_list_only_chapter_preview_is_substantive(section_id: str) -> None:
    service = ProfileService(ROOT / "inputs", workspace=ROOT)
    section = next(
        section
        for section in service.profile(
            "charles-hudson-precursor-ventures"
        ).sections
        if section.section_id == section_id
    )

    assert section.preview
    assert not section.preview.startswith(
        ("Source:", "Sources:", "Provenance:", "-", "*", "#")
    )


def test_profile_graph_counts_distinct_investigations_and_cooccurrences(monkeypatch) -> None:
    service = ProfileService(ROOT / "inputs", workspace=ROOT)
    investigations = (
        {
            "rationales": [
                _rationale("business_model_assessment", "positive", 0.8),
                _rationale("business_model_assessment", "positive", 0.6),
                _rationale("competitive_advantage_assessment", "negative", 0.7),
            ]
        },
        {
            "rationales": [
                _rationale("business_model_assessment", "negative", 0.9),
                _rationale("competitive_advantage_assessment", "negative", 0.9),
            ]
        },
        {
            "rationales": [
                _rationale("business_model_assessment", "positive", 0.5),
            ]
        },
    )
    monkeypatch.setattr(service, "_investigations", lambda _vc_slug: investigations)

    graph = service.rationale_graph("charles-hudson-precursor-ventures")
    business = next(
        node for node in graph.nodes if node.node_id == "business_model_assessment"
    )
    competition = next(
        node
        for node in graph.nodes
        if node.node_id == "competitive_advantage_assessment"
    )
    edge = next(
        row
        for row in graph.edges
        if row.edge_id
        == "business_model_assessment--competitive_advantage_assessment"
    )

    assert business.occurrence_count == 3
    assert business.investigation_count == 3
    assert business.direction_counts == {"positive": 2, "negative": 1}
    assert business.weighted_degree == 2
    assert competition.occurrence_count == 2
    assert competition.investigation_count == 3
    assert competition.weighted_degree == 2
    assert edge.occurrence_count == 2
    assert edge.inference_status == "observed_cooccurrence"


def test_profile_graph_edges_have_stable_order_and_eighty_edge_cap(monkeypatch) -> None:
    service = ProfileService(ROOT / "inputs", workspace=ROOT)
    labels = {
        f"node-{index:03}": [
            _rationale(f"node-{index:03}", "positive", 0.8)
        ]
        for index in range(86)
    }
    unordered_pairs = {
        ("node-000", f"node-{index:03}"): 2 + (index % 4)
        for index in reversed(range(1, 86))
    }
    monkeypatch.setattr(
        service,
        "_aggregate",
        lambda _vc_slug: (labels, unordered_pairs, 1),
    )

    first = service.rationale_graph("charles-hudson-precursor-ventures")
    second = service.rationale_graph("charles-hudson-precursor-ventures")
    expected_pairs = sorted(
        unordered_pairs,
        key=lambda pair: (-unordered_pairs[pair], pair),
    )[:80]
    expected_ids = tuple(f"{left}--{right}" for left, right in expected_pairs)

    assert len(first.edges) == 80
    assert tuple(edge.edge_id for edge in first.edges) == expected_ids
    assert tuple(edge.edge_id for edge in second.edges) == expected_ids


def test_session_graph_models_keep_profile_metadata_optional() -> None:
    node = RationaleNodeView(
        node_id="r-1",
        taxonomy_label="unknown",
        title="Unknown",
        direction="neutral",
        confidence=0.5,
    )
    edge = RationaleEdgeView(
        edge_id="e-1",
        source="r-1",
        target="r-2",
        relationship="co_occurs_with",
        inference_status="observed_cooccurrence",
    )

    assert node.definition is None
    assert node.coarse_parent is None
    assert node.occurrence_count is None
    assert node.investigation_count is None
    assert node.direction_counts == {}
    assert node.weighted_degree is None
    assert edge.occurrence_count is None


def test_memory_search_returns_source_linked_text() -> None:
    service = ProfileService(ROOT / "inputs", workspace=ROOT)

    results = service.search_memory("charles-hudson-precursor-ventures", "pre-seed")

    assert results.results
    assert all(row.source_path and row.excerpt for row in results.results)


def test_memory_search_cleans_structured_evidence_and_deduplicates(
    tmp_path: Path,
) -> None:
    service, slug = _memory_service(
        tmp_path,
        """# business_model_economics

## business_model_economics

[ev:cyan-0038] label=business_model_assessment direction=positive source=talk:c1eoWu8QVIU > "Then I consider whether people can pay for it."

[ev:cyan-0038-copy] label=business_model_assessment direction=positive source=talk:c1eoWu8QVIU
> "Then I consider whether people can pay for it."

## Market evidence
Customers need a business model they can afford.
""",
    )

    response = service.search_memory(slug, "business model")

    assert [row.excerpt for row in response.results] == [
        "Then I consider whether people can pay for it.",
        "Customers need a business model they can afford.",
    ]
    structured = response.results[0]
    assert structured.evidence_id == "cyan-0038"
    assert structured.rationale_label == "business_model_assessment"
    assert structured.direction == "positive"
    assert structured.source_reference == "talk:c1eoWu8QVIU"
    assert structured.source_title == "Business Model Economics"
    assert all(not row.excerpt.startswith("#") for row in response.results)


def test_memory_search_discards_heading_wrapped_and_public_reference_provenance(
    tmp_path: Path,
) -> None:
    service, slug = _memory_service(
        tmp_path,
        """## Audit metadata
Sources:
- inputs/wiki/persona.md

Sources:
- talk:abc123

Founder sources are evaluated in context.
""",
    )

    response = service.search_memory(slug, "sources")

    assert [row.excerpt for row in response.results] == [
        "Founder sources are evaluated in context."
    ]


def test_memory_search_paginates_unique_results_and_clamps_last_page(
    tmp_path: Path,
) -> None:
    blocks = "\n\n".join(
        f"Founder evidence number {index}." for index in range(1, 13)
    )
    service, slug = _memory_service(tmp_path, blocks)

    first = service.search_memory(slug, "founder evidence", page=1, page_size=5)
    last = service.search_memory(slug, "founder evidence", page=99, page_size=5)
    empty = service.search_memory(slug, "unmatchedtoken", page=7, page_size=5)

    assert len(first.results) == 5
    assert (
        first.page,
        first.page_size,
        first.total_results,
        first.total_pages,
    ) == (1, 5, 12, 3)
    assert len(last.results) == 2
    assert last.page == 3
    assert (
        empty.page,
        empty.total_results,
        empty.total_pages,
        empty.results,
    ) == (1, 0, 0, ())


def test_memory_search_route_validates_and_forwards_pagination(
    tmp_path: Path,
) -> None:
    blocks = "\n\n".join(
        f"Founder evidence number {index}." for index in range(1, 13)
    )
    service, slug = _memory_service(tmp_path, blocks)
    client = TestClient(create_app(testing=True, profile_service=service))

    response = client.get(
        f"/api/investors/{slug}/memory/search",
        params={"q": "founder", "page": 2, "page_size": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 5
    assert len(payload["results"]) == 5
    invalid = client.get(
        f"/api/investors/{slug}/memory/search",
        params={"q": "founder", "page": 0},
    )
    assert invalid.status_code == 422


def test_investor_routes_are_configuration_driven() -> None:
    service = ProfileService(ROOT / "inputs", workspace=ROOT)
    client = TestClient(create_app(testing=True, profile_service=service))

    response = client.get("/api/investors")

    assert response.status_code == 200
    assert len(response.json()["investors"]) == 6
    assert client.get(
        "/api/investors/charles-hudson-precursor-ventures/rationale-graph"
    ).status_code == 200
