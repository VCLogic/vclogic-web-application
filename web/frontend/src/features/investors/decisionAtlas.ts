import type { Graph, RationaleNode } from "../../api/types";

export type AtlasDirection = "positive" | "negative" | "context";

export interface DirectionTotals {
  positive: number;
  negative: number;
  context: number;
  total: number;
}

export interface DecisionTheme {
  id: string;
  title: string;
  nodes: RationaleNode[];
  knownRecurrence?: number;
  directionTotals: DirectionTotals;
}

export interface AtlasAssociation {
  id: string;
  label: string;
  count?: number;
}

const CONTEXT_DIRECTIONS = new Set(["neutral", "mixed", "unresolved"]);

export function knownCount(value: unknown): number | undefined {
  return typeof value === "number" && Number.isInteger(value) && value >= 0
    ? value
    : undefined;
}

export function humanizeRationale(value: string | null | undefined, fallback = "Untitled rationale"): string {
  const source = value?.trim() || fallback;
  const spaced = source.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : fallback;
}

function stableNodeSort(left: RationaleNode, right: RationaleNode): number {
  const leftCount = knownCount(left.occurrence_count);
  const rightCount = knownCount(right.occurrence_count);
  if (leftCount === undefined || rightCount === undefined) {
    if (leftCount !== rightCount) return leftCount === undefined ? 1 : -1;
  } else if (leftCount !== rightCount) {
    return rightCount - leftCount;
  }
  return humanizeRationale(left.taxonomy_label).localeCompare(humanizeRationale(right.taxonomy_label))
    || left.node_id.localeCompare(right.node_id);
}

function nodeDirectionTotals(node: RationaleNode): DirectionTotals {
  const totals: DirectionTotals = { positive: 0, negative: 0, context: 0, total: 0 };
  for (const [direction, rawCount] of Object.entries(node.direction_counts ?? {})) {
    const count = knownCount(rawCount);
    if (count === undefined) continue;
    if (direction === "positive") totals.positive += count;
    else if (direction === "negative") totals.negative += count;
    else if (CONTEXT_DIRECTIONS.has(direction)) totals.context += count;
  }
  totals.total = totals.positive + totals.negative + totals.context;
  return totals;
}

export function buildDecisionThemes(graph: Graph): DecisionTheme[] {
  const groups = new Map<string, RationaleNode[]>();
  for (const node of graph.nodes) {
    const id = node.coarse_parent?.trim() || "other_considerations";
    const existing = groups.get(id) ?? [];
    existing.push(node);
    groups.set(id, existing);
  }

  const themes = Array.from(groups, ([id, unsortedNodes]) => {
    const nodes = [...unsortedNodes].sort(stableNodeSort);
    const recurrenceCounts = nodes.map((node) => knownCount(node.occurrence_count));
    const knownCounts = recurrenceCounts.filter((count): count is number => count !== undefined);
    const directionTotals = nodes.reduce<DirectionTotals>((totals, node) => {
      const next = nodeDirectionTotals(node);
      totals.positive += next.positive;
      totals.negative += next.negative;
      totals.context += next.context;
      totals.total += next.total;
      return totals;
    }, { positive: 0, negative: 0, context: 0, total: 0 });
    return {
      id,
      title: humanizeRationale(id),
      nodes,
      knownRecurrence: knownCounts.length ? knownCounts.reduce((sum, count) => sum + count, 0) : undefined,
      directionTotals,
    } satisfies DecisionTheme;
  });

  return themes.sort((left, right) => {
    if (left.knownRecurrence === undefined || right.knownRecurrence === undefined) {
      if (left.knownRecurrence !== right.knownRecurrence) return left.knownRecurrence === undefined ? 1 : -1;
    } else if (left.knownRecurrence !== right.knownRecurrence) {
      return right.knownRecurrence - left.knownRecurrence;
    }
    return left.title.localeCompare(right.title) || left.id.localeCompare(right.id);
  });
}

export function directionPercentages(totals: DirectionTotals): DirectionTotals {
  if (!Number.isFinite(totals.total) || totals.total <= 0) {
    return { positive: 0, negative: 0, context: 0, total: 0 };
  }
  const positive = Math.round((totals.positive / totals.total) * 10_000) / 100;
  const negative = Math.round((totals.negative / totals.total) * 10_000) / 100;
  const context = Math.max(0, Math.round((100 - positive - negative) * 100) / 100);
  return { positive, negative, context, total: 100 };
}

export function associationsFor(graph: Graph, nodeId: string, limit = 5): AtlasAssociation[] {
  const labels = new Map(graph.nodes.map((node) => [
    node.node_id,
    humanizeRationale(node.taxonomy_label, humanizeRationale(node.title)),
  ]));
  return graph.edges
    .filter((edge) => edge.source === nodeId || edge.target === nodeId)
    .map((edge) => {
      const associatedId = edge.source === nodeId ? edge.target : edge.source;
      return {
        id: edge.edge_id,
        label: labels.get(associatedId) ?? "Unknown rationale",
        count: knownCount(edge.occurrence_count),
      };
    })
    .sort((left, right) => {
      if (left.count === undefined || right.count === undefined) {
        if (left.count !== right.count) return left.count === undefined ? 1 : -1;
      } else if (left.count !== right.count) {
        return right.count - left.count;
      }
      return left.label.localeCompare(right.label) || left.id.localeCompare(right.id);
    })
    .slice(0, Math.max(0, limit));
}
