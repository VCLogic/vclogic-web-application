import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Graph, RationaleNode } from "../../api/types";
import { DecisionAtlas } from "./DecisionAtlas";

function rationale(overrides: Partial<RationaleNode> & Pick<RationaleNode, "node_id" | "taxonomy_label">): RationaleNode {
  return {
    title: overrides.taxonomy_label,
    direction: "mixed",
    salience: "primary",
    confidence: 0.82,
    evidence_ids: [],
    coarse_parent: "founder_team",
    occurrence_count: 1,
    direction_counts: { positive: 1 },
    ...overrides,
  };
}

const graph: Graph = {
  nodes: [
    rationale({ node_id: "f1", taxonomy_label: "founder_execution", definition: "Can the founder build and deliver?", occurrence_count: 8, confidence: 0.84, direction_counts: { positive: 5, negative: 2, unresolved: 1 } }),
    rationale({ node_id: "f2", taxonomy_label: "founder_market_fit", definition: "Does experience fit the market?", occurrence_count: 3, confidence: 0.72, direction_counts: { positive: 2, negative: 1 } }),
    rationale({ node_id: "m1", taxonomy_label: "market_size_assessment", coarse_parent: "market_opportunity", definition: "Can the market support venture outcomes?", occurrence_count: 5, confidence: 0.91, direction_counts: { positive: 1, negative: 4 } }),
    rationale({ node_id: "p1", taxonomy_label: "product_adoption", coarse_parent: "product_solution", definition: null, occurrence_count: null, confidence: Number.NaN, direction_counts: null }),
  ],
  edges: [{ edge_id: "e1", source: "f1", target: "m1", relationship: "co_occurs_with", inference_status: "observed_cooccurrence", evidence_ids: [], occurrence_count: 4 }],
};

afterEach(cleanup);

describe("DecisionAtlas", () => {
  it("presents taxonomy themes instead of a node-link graph", () => {
    render(<DecisionAtlas graph={graph} onFindEvidence={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Decision Atlas" })).toBeVisible();
    expect(screen.queryByLabelText("Decision logic visualization")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Founder team, 2 rationales, 11 observed activations/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Market opportunity, 1 rationale, 5 observed activations/ })).toBeVisible();
    expect(screen.getByLabelText("Founder team direction distribution: 7 positive, 3 negative, 1 context or unresolved")).toBeVisible();
  });

  it("changes rationale detail when a different theme is selected", async () => {
    const user = userEvent.setup();
    render(<DecisionAtlas graph={graph} onFindEvidence={vi.fn()} />);

    expect(screen.getByRole("article", { name: "Rationale: Founder execution" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: /Market opportunity, 1 rationale/ }));

    expect(screen.getByRole("article", { name: "Rationale: Market size assessment" })).toBeVisible();
    expect(screen.queryByRole("article", { name: "Rationale: Founder execution" })).not.toBeInTheDocument();
  });

  it("explains recurrence, confidence, associations, and evidence action", async () => {
    const onFindEvidence = vi.fn();
    const user = userEvent.setup();
    render(<DecisionAtlas graph={graph} onFindEvidence={onFindEvidence} />);

    const founder = screen.getByRole("article", { name: "Rationale: Founder execution" });
    expect(within(founder).getByText("Can the founder build and deliver?")).toBeVisible();
    expect(within(founder).getByText("8 activations")).toBeVisible();
    expect(within(founder).getByText("84% confidence")).toBeVisible();
    expect(within(founder).getByText("Observed co-occurrence, not causality")).toBeVisible();
    expect(within(founder).getByText("Market size assessment")).toBeVisible();

    await user.click(within(founder).getByRole("button", { name: "Find evidence for Founder execution" }));
    expect(onFindEvidence).toHaveBeenCalledWith("founder_execution");
  });

  it("exposes a complete searchable rationale inventory", async () => {
    const user = userEvent.setup();
    render(<DecisionAtlas graph={graph} onFindEvidence={vi.fn()} />);
    await user.click(screen.getByRole("tab", { name: "All rationales" }));

    expect(screen.getByText("Showing 4 of 4 rationales")).toBeVisible();
    expect(screen.getByRole("table", { name: "Complete rationale inventory" })).toBeVisible();
    await user.type(screen.getByRole("searchbox", { name: "Search rationale inventory" }), "venture outcomes");
    expect(screen.getByText("Showing 1 of 4 rationales")).toBeVisible();
    expect(screen.getByRole("button", { name: "Inspect Market size assessment" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Inspect Founder execution" })).not.toBeInTheDocument();
  });

  it("sorts unavailable recurrence last in both directions", async () => {
    const user = userEvent.setup();
    render(<DecisionAtlas graph={graph} onFindEvidence={vi.fn()} />);
    await user.click(screen.getByRole("tab", { name: "All rationales" }));
    const table = screen.getByRole("table", { name: "Complete rationale inventory" });
    const labels = () => within(table).getAllByRole("row").slice(1).map((row) => within(row).getAllByRole("cell")[0].textContent);

    expect(labels()).toEqual(["Founder execution", "Market size assessment", "Founder market fit", "Product adoption"]);
    await user.click(screen.getByRole("button", { name: /Sort by recurrence/ }));
    expect(labels()).toEqual(["Founder market fit", "Market size assessment", "Founder execution", "Product adoption"]);
  });

  it("keeps missing metadata unavailable rather than inventing zero", async () => {
    const user = userEvent.setup();
    render(<DecisionAtlas graph={graph} onFindEvidence={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Product solution, 1 rationale/ }));

    const product = screen.getByRole("article", { name: "Rationale: Product adoption" });
    expect(within(product).getByText("Definition unavailable.")).toBeVisible();
    expect(within(product).getByText("Recurrence unavailable")).toBeVisible();
    expect(within(product).getByText("Confidence unavailable")).toBeVisible();
    expect(product).not.toHaveTextContent("0 activations");
  });

  it("shows a clear empty state", () => {
    render(<DecisionAtlas graph={{ nodes: [], edges: [] }} onFindEvidence={vi.fn()} />);

    expect(screen.getByText("No recurring decision patterns are available for this profile.")).toBeVisible();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });
});
