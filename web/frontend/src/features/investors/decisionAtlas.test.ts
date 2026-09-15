import { describe, expect, it } from "vitest";
import type { Graph, RationaleNode } from "../../api/types";
import {
  associationsFor,
  buildDecisionThemes,
  directionPercentages,
  humanizeRationale,
  knownCount,
} from "./decisionAtlas";

function node(
  nodeId: string,
  taxonomyLabel: string,
  coarseParent: string | null,
  occurrenceCount: number | null,
  directionCounts: Record<string, number> | null,
): RationaleNode {
  return {
    node_id: nodeId,
    taxonomy_label: taxonomyLabel,
    title: taxonomyLabel,
    direction: "mixed",
    salience: "primary",
    confidence: 0.82,
    evidence_ids: [],
    coarse_parent: coarseParent,
    occurrence_count: occurrenceCount,
    direction_counts: directionCounts,
  };
}

const graph: Graph = {
  nodes: [
    node("f1", "founder_execution", "founder_team", 8, { positive: 5, negative: 2, unresolved: 1 }),
    node("f2", "founder_market_fit", "founder_team", 3, { positive: 2, negative: 1 }),
    node("m1", "market_size_assessment", "market_opportunity", null, null),
  ],
  edges: [{
    edge_id: "e1",
    source: "f1",
    target: "m1",
    relationship: "co_occurs_with",
    inference_status: "observed_cooccurrence",
    evidence_ids: [],
    occurrence_count: 4,
  }],
};

describe("Decision Atlas aggregation", () => {
  it("accepts only known nonnegative integer counts and preserves explicit zero", () => {
    expect(knownCount(0)).toBe(0);
    expect(knownCount(12)).toBe(12);
    expect(knownCount(null)).toBeUndefined();
    expect(knownCount(Number.NaN)).toBeUndefined();
    expect(knownCount(-1)).toBeUndefined();
    expect(knownCount(2.5)).toBeUndefined();
  });

  it("groups and ranks rationales by taxonomy theme without mutating the graph", () => {
    const original = structuredClone(graph);

    const themes = buildDecisionThemes(graph);

    expect(themes.map(({ id }) => id)).toEqual(["founder_team", "market_opportunity"]);
    expect(themes[0]).toMatchObject({
      title: "Founder team",
      knownRecurrence: 11,
      directionTotals: { positive: 7, negative: 3, context: 1, total: 11 },
    });
    expect(themes[0].nodes.map(({ node_id }) => node_id)).toEqual(["f1", "f2"]);
    expect(themes[1].knownRecurrence).toBeUndefined();
    expect(themes[1].directionTotals).toEqual({ positive: 0, negative: 0, context: 0, total: 0 });
    expect(graph).toEqual(original);
  });

  it("groups missing parents into Other considerations", () => {
    const themes = buildDecisionThemes({ nodes: [node("x", "new_signal", null, 1, { neutral: 1 })], edges: [] });

    expect(themes).toHaveLength(1);
    expect(themes[0]).toMatchObject({ id: "other_considerations", title: "Other considerations" });
  });

  it("normalizes direction totals safely and exactly", () => {
    expect(directionPercentages({ positive: 7, negative: 2, context: 1, total: 10 })).toEqual({
      positive: 70,
      negative: 20,
      context: 10,
      total: 100,
    });
    expect(directionPercentages({ positive: 0, negative: 0, context: 0, total: 0 })).toEqual({
      positive: 0,
      negative: 0,
      context: 0,
      total: 0,
    });
  });

  it("returns strongest observed associations with unknown counts last", () => {
    const extended: Graph = {
      ...graph,
      nodes: [...graph.nodes, node("p1", "product_adoption", "product_solution", 2, { positive: 2 })],
      edges: [
        ...graph.edges,
        { edge_id: "e2", source: "f1", target: "p1", relationship: "co_occurs_with", inference_status: "observed_cooccurrence", evidence_ids: [], occurrence_count: null },
      ],
    };

    expect(associationsFor(extended, "f1")).toEqual([
      { id: "e1", label: "Market size assessment", count: 4 },
      { id: "e2", label: "Product adoption", count: undefined },
    ]);
  });

  it("humanizes rationale labels for authored display", () => {
    expect(humanizeRationale("founder_market-fit")).toBe("Founder market fit");
    expect(humanizeRationale(null, "Fallback title")).toBe("Fallback title");
  });
});
