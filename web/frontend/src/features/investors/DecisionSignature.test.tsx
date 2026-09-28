import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { Graph, RationaleNode } from "../../api/types";
import { DecisionSignature } from "./DecisionSignature";

function node(overrides: Partial<RationaleNode> & Pick<RationaleNode, "node_id" | "taxonomy_label">): RationaleNode {
  return { title: overrides.taxonomy_label, direction: "mixed", salience: "primary", confidence: .8, evidence_ids: [], occurrence_count: 1, direction_counts: {}, ...overrides };
}

const graph: Graph = {
  nodes: [
    node({ node_id: "founder", taxonomy_label: "founder_conviction", definition: "Evidence that the founder can execute.", occurrence_count: 12, direction_counts: { positive: 10, negative: 1, unresolved: 1 } }),
    node({ node_id: "market", taxonomy_label: "market_size_assessment", definition: "Whether the opportunity can support venture outcomes.", occurrence_count: 8, direction_counts: { positive: 1, negative: 6, unresolved: 1 } }),
    node({ node_id: "terms", taxonomy_label: "deal_terms_complexity", definition: "Terms that need more context.", occurrence_count: 3, direction_counts: { unresolved: 3 } }),
    node({ node_id: "unknown", taxonomy_label: "product_adoption", occurrence_count: null, direction_counts: null }),
  ],
  edges: [
    { edge_id: "pair", source: "founder", target: "market", relationship: "co_occurs_with", inference_status: "observed_cooccurrence", evidence_ids: [], occurrence_count: 5 },
    { edge_id: "pair-reversed", source: "market", target: "founder", relationship: "co_occurs_with", inference_status: "observed_cooccurrence", evidence_ids: [], occurrence_count: 5 },
    { edge_id: "unknown-pair", source: "terms", target: "unknown", relationship: "co_occurs_with", inference_status: "observed_cooccurrence", evidence_ids: [], occurrence_count: null },
  ],
};

afterEach(cleanup);

it("presents a ranked decision signature without a causal graph", () => {
  render(<DecisionSignature graph={graph} onFindEvidence={vi.fn()} />);
  expect(screen.getByRole("heading", { name: "Decision Signature" })).toBeVisible();
  expect(screen.getByRole("region", { name: "Creates conviction" })).toHaveTextContent("Founder conviction");
  expect(screen.getByRole("region", { name: "Creates concern" })).toHaveTextContent("Market size assessment");
  expect(screen.getByRole("region", { name: "Context and unresolved" })).toHaveTextContent("Deal terms complexity");
  expect(screen.getByRole("meter", { name: /Founder conviction recurrence/i })).toHaveAttribute("aria-valuenow", "100");
  expect(screen.getByText(/frequency in the available source-linked record, not causal importance/i)).toBeVisible();
  expect(screen.queryByLabelText(/decision logic visualization/i)).not.toBeInTheDocument();
});

it("explains recurring pairs as noncausal observations", () => {
  render(<DecisionSignature graph={graph} onFindEvidence={vi.fn()} />);
  const pairs = screen.getByRole("region", { name: "Often considered together" });
  expect(pairs).toHaveTextContent("Founder conviction");
  expect(pairs).toHaveTextContent("Market size assessment");
  expect(pairs).toHaveTextContent("5 shared observations");
  expect(pairs).toHaveTextContent("co-occurrence, not cause and effect");
  expect(pairs).toHaveTextContent("Recurrence unavailable");
  expect(within(pairs).getAllByRole("listitem")).toHaveLength(2);
});

it("keeps the complete rationale inventory searchable and sortable", async () => {
  const user = userEvent.setup();
  render(<DecisionSignature graph={graph} onFindEvidence={vi.fn()} />);
  await user.click(screen.getByText(/Browse all 4 rationales/i));
  expect(screen.getByText("Showing 4 of 4 rationales")).toBeVisible();
  await user.type(screen.getByRole("searchbox", { name: /Search all rationales/i }), "venture outcomes");
  expect(screen.getByText("Showing 1 of 4 rationales")).toBeVisible();
  expect(screen.getByRole("row", { name: /Market size assessment/i })).toBeVisible();
  expect(screen.queryByRole("row", { name: /Founder conviction/i })).not.toBeInTheDocument();
});

it("opens supporting evidence from a readable rationale row", async () => {
  const user = userEvent.setup();
  const onFindEvidence = vi.fn();
  render(<DecisionSignature graph={graph} onFindEvidence={onFindEvidence} />);
  const conviction = screen.getByRole("region", { name: "Creates conviction" });
  await user.click(within(conviction).getByRole("button", { name: /Find evidence for Founder conviction/i }));
  expect(onFindEvidence).toHaveBeenCalledWith("founder_conviction");
});

it("keeps unavailable recurrence explicitly unknown", () => {
  render(<DecisionSignature graph={graph} onFindEvidence={vi.fn()} />);
  const product = screen.getByRole("heading", { name: "Product adoption" }).closest("article");
  expect(product).toHaveTextContent("Recurrence unavailable");
  expect(product).not.toHaveTextContent("0 observations");
});


it.each(["not_prepared", "invalid"] as const)("explains %s historical evidence and points to the source library", (evidence_status) => {
  const evidence_note = evidence_status === "invalid"
    ? "The imported historical evidence could not be verified."
    : "Historical rationale evidence has not been prepared for this investor version.";
  render(<DecisionSignature graph={{ nodes: [], edges: [], evidence_status, evidence_note }} onFindEvidence={vi.fn()} />);
  expect(screen.getByText(evidence_note)).toBeVisible();
  expect(screen.queryByText("No recurring decision patterns are available for this profile.")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Explore the Investment Memory below" })).toHaveAttribute("href", "#investment-memory-title");
});

it("labels available history as reference evidence alongside its rationale patterns", () => {
  const evidence_note = "Historical reference evidence; not calibration or current model weights.";
  render(<DecisionSignature graph={{ ...graph, evidence_status: "available", evidence_note }} onFindEvidence={vi.fn()} />);
  expect(screen.getByText(evidence_note)).toBeVisible();
  expect(screen.getByRole("region", { name: "Creates conviction" })).toBeVisible();
});
