import { useMemo, useState } from "react";
import type { Graph, RationaleNode } from "../../api/types";
import {
  associationsFor,
  buildDecisionThemes,
  directionPercentages,
  humanizeRationale,
  knownCount,
  type DecisionTheme,
  type DirectionTotals,
} from "./decisionAtlas";

type AtlasView = "themes" | "inventory";
type SortColumn = "rationale" | "theme" | "recurrence" | "confidence";
type SortDirection = "ascending" | "descending";

interface DecisionAtlasProps {
  graph: Graph;
  onFindEvidence: (label: string) => void;
}

function activationLabel(count: number): string {
  return `${count} observed ${count === 1 ? "activation" : "activations"}`;
}

function confidenceValue(node: RationaleNode): number | undefined {
  return typeof node.confidence === "number" && Number.isFinite(node.confidence)
    ? Math.max(0, Math.min(1, node.confidence))
    : undefined;
}

function confidenceLabel(node: RationaleNode): string {
  const value = confidenceValue(node);
  return value === undefined ? "Confidence unavailable" : `${Math.round(value * 100)}% confidence`;
}

function nodeDirectionTotals(node: RationaleNode): DirectionTotals {
  const totals: DirectionTotals = { positive: 0, negative: 0, context: 0, total: 0 };
  for (const [direction, rawCount] of Object.entries(node.direction_counts ?? {})) {
    const count = knownCount(rawCount);
    if (count === undefined) continue;
    if (direction === "positive") totals.positive += count;
    else if (direction === "negative") totals.negative += count;
    else totals.context += count;
  }
  totals.total = totals.positive + totals.negative + totals.context;
  return totals;
}

function DirectionDistribution({ title, totals }: { title: string; totals: DirectionTotals }) {
  const percentages = directionPercentages(totals);
  const label = `${title} direction distribution: ${totals.positive} positive, ${totals.negative} negative, ${totals.context} context or unresolved`;
  return <span className="atlas-direction" aria-label={label}>
    <span className="atlas-direction-bar" aria-hidden="true">
      {percentages.positive > 0 && <i className="positive" style={{ width: `${percentages.positive}%` }} />}
      {percentages.negative > 0 && <i className="negative" style={{ width: `${percentages.negative}%` }} />}
      {percentages.context > 0 && <i className="context" style={{ width: `${percentages.context}%` }} />}
      {percentages.total === 0 && <i className="unavailable" style={{ width: "100%" }} />}
    </span>
    <span>{totals.total > 0 ? `${totals.positive} positive · ${totals.negative} concern · ${totals.context} context` : "Direction distribution unavailable"}</span>
  </span>;
}

function RationaleCard({ graph, node, onFindEvidence }: { graph: Graph; node: RationaleNode; onFindEvidence: (label: string) => void }) {
  const title = humanizeRationale(node.taxonomy_label, humanizeRationale(node.title));
  const count = knownCount(node.occurrence_count);
  const associations = associationsFor(graph, node.node_id);
  return <article className="atlas-rationale" aria-label={`Rationale: ${title}`}>
    <header>
      <div>
        <span className="atlas-rationale-kicker">{humanizeRationale(node.coarse_parent, "Other considerations")}</span>
        <h3>{title}</h3>
      </div>
      <div className="atlas-rationale-metrics">
        <span>{count === undefined ? "Recurrence unavailable" : `${count} activations`}</span>
        <span>{confidenceLabel(node)}</span>
      </div>
    </header>
    <p>{node.definition?.trim() || "Definition unavailable."}</p>
    <DirectionDistribution title={title} totals={nodeDirectionTotals(node)} />
    {associations.length > 0 && <div className="atlas-associations">
      <div><strong>Often considered alongside</strong><span>Observed co-occurrence, not causality</span></div>
      <ul>{associations.map((association) => <li key={association.id}><span>{association.label}</span><b>{association.count ?? "Unavailable"}</b></li>)}</ul>
    </div>}
    <button type="button" className="atlas-evidence-action" aria-label={`Find evidence for ${title}`} onClick={() => onFindEvidence(node.taxonomy_label)}>Find supporting evidence</button>
  </article>;
}

function ThemeIndex({ themes, selectedId, onSelect }: { themes: DecisionTheme[]; selectedId: string; onSelect: (id: string) => void }) {
  return <ol className="atlas-theme-index" aria-label="Decision themes">
    {themes.map((theme, index) => {
      const recurrence = theme.knownRecurrence;
      const rationaleCount = theme.nodes.length;
      const accessibleRecurrence = recurrence === undefined ? "recurrence unavailable" : activationLabel(recurrence);
      return <li key={theme.id}>
        <button
          type="button"
          aria-pressed={theme.id === selectedId}
          aria-label={`${theme.title}, ${rationaleCount} ${rationaleCount === 1 ? "rationale" : "rationales"}, ${accessibleRecurrence}`}
          onClick={() => onSelect(theme.id)}
        >
          <span className="atlas-theme-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
          <span className="atlas-theme-copy"><strong>{theme.title}</strong><small>{theme.nodes.slice(0, 2).map((node) => humanizeRationale(node.taxonomy_label)).join(" · ")}</small></span>
          <span className="atlas-theme-count">{recurrence ?? "—"}<small>observed</small></span>
          <DirectionDistribution title={theme.title} totals={theme.directionTotals} />
        </button>
      </li>;
    })}
  </ol>;
}

function ThemesView({ graph, themes, onFindEvidence }: { graph: Graph; themes: DecisionTheme[]; onFindEvidence: (label: string) => void }) {
  const [selectedId, setSelectedId] = useState(themes[0]?.id ?? "");
  const selected = themes.find((theme) => theme.id === selectedId) ?? themes[0];
  return <div className="atlas-themes-layout">
    <ThemeIndex themes={themes} selectedId={selected?.id ?? ""} onSelect={setSelectedId} />
    {selected && <section className="atlas-theme-detail" aria-labelledby={`atlas-theme-${selected.id}`}>
      <header><span className="section-index">Selected theme</span><h3 id={`atlas-theme-${selected.id}`}>{selected.title}</h3><p>{selected.nodes.length} {selected.nodes.length === 1 ? "rationale" : "rationales"} observed in this profile</p></header>
      <div className="atlas-rationale-list">{selected.nodes.map((node) => <RationaleCard key={node.node_id} graph={graph} node={node} onFindEvidence={onFindEvidence} />)}</div>
    </section>}
  </div>;
}

function nodeLabel(node: RationaleNode): string {
  return humanizeRationale(node.taxonomy_label, humanizeRationale(node.title));
}

function stableTie(left: RationaleNode, right: RationaleNode): number {
  return nodeLabel(left).localeCompare(nodeLabel(right)) || left.node_id.localeCompare(right.node_id);
}

function InventoryView({ graph, onFindEvidence }: { graph: Graph; onFindEvidence: (label: string) => void }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ column: SortColumn; direction: SortDirection }>({ column: "recurrence", direction: "descending" });
  const [selected, setSelected] = useState<RationaleNode | null>(null);
  const normalized = query.trim().toLocaleLowerCase();
  const filtered = graph.nodes.filter((node) => {
    if (!normalized) return true;
    const recurrence = knownCount(node.occurrence_count);
    const confidence = confidenceValue(node);
    return [
      nodeLabel(node),
      humanizeRationale(node.coarse_parent, "Other considerations"),
      node.definition ?? "",
      node.direction,
      recurrence === undefined ? "" : `${recurrence} recurrence ${recurrence} times`,
      confidence === undefined ? "" : `${Math.round(confidence * 100)}% confidence`,
    ].join(" ").toLocaleLowerCase().includes(normalized);
  });
  const sorted = [...filtered].sort((left, right) => {
    let comparison = 0;
    if (sort.column === "rationale") comparison = nodeLabel(left).localeCompare(nodeLabel(right));
    if (sort.column === "theme") comparison = humanizeRationale(left.coarse_parent, "Other considerations").localeCompare(humanizeRationale(right.coarse_parent, "Other considerations"));
    if (sort.column === "recurrence") {
      const leftCount = knownCount(left.occurrence_count);
      const rightCount = knownCount(right.occurrence_count);
      if (leftCount === undefined || rightCount === undefined) {
        if (leftCount !== rightCount) return leftCount === undefined ? 1 : -1;
      } else comparison = leftCount - rightCount;
    }
    if (sort.column === "confidence") {
      const leftConfidence = confidenceValue(left);
      const rightConfidence = confidenceValue(right);
      if (leftConfidence === undefined || rightConfidence === undefined) {
        if (leftConfidence !== rightConfidence) return leftConfidence === undefined ? 1 : -1;
      } else comparison = leftConfidence - rightConfidence;
    }
    if (comparison) return sort.direction === "ascending" ? comparison : -comparison;
    return stableTie(left, right);
  });
  const changeSort = (column: SortColumn) => setSort((current) => current.column === column
    ? { column, direction: current.direction === "ascending" ? "descending" : "ascending" }
    : { column, direction: column === "rationale" || column === "theme" ? "ascending" : "descending" });
  const sortHeader = (column: SortColumn, title: string) => <th aria-sort={sort.column === column ? sort.direction : undefined}><button type="button" aria-label={`Sort by ${column}, ${sort.column === column ? sort.direction : "not sorted"}`} onClick={() => changeSort(column)}>{title}<span aria-hidden="true"> {sort.column === column ? sort.direction === "ascending" ? "↑" : "↓" : "↕"}</span></button></th>;

  return <div className="atlas-inventory">
    <div className="atlas-inventory-tools">
      <label htmlFor="atlas-inventory-search">Search rationale inventory</label>
      <input id="atlas-inventory-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} />
      <p role="status">Showing {sorted.length} of {graph.nodes.length} rationales</p>
    </div>
    <div className="atlas-table-wrap"><table aria-label="Complete rationale inventory"><thead><tr>{sortHeader("rationale", "Rationale")}{sortHeader("theme", "Theme")}{sortHeader("recurrence", "Recurrence")}{sortHeader("confidence", "Confidence")}</tr></thead><tbody>
      {sorted.map((node) => <tr key={node.node_id}>
        <td><button type="button" aria-label={`Inspect ${nodeLabel(node)}`} onClick={() => setSelected(node)}>{nodeLabel(node)}</button></td>
        <td>{humanizeRationale(node.coarse_parent, "Other considerations")}</td>
        <td>{knownCount(node.occurrence_count) ?? "Unavailable"}</td>
        <td>{confidenceValue(node) === undefined ? "Unavailable" : `${Math.round(confidenceValue(node)! * 100)}%`}</td>
      </tr>)}
      {!sorted.length && <tr><td colSpan={4}>No rationales match your search.</td></tr>}
    </tbody></table></div>
    {selected && <div className="atlas-inventory-detail"><RationaleCard graph={graph} node={selected} onFindEvidence={onFindEvidence} /></div>}
  </div>;
}

export function DecisionAtlas({ graph, onFindEvidence }: DecisionAtlasProps) {
  const [view, setView] = useState<AtlasView>("themes");
  const themes = useMemo(() => buildDecisionThemes(graph), [graph]);
  if (!graph.nodes.length) return <section className="decision-atlas atlas-empty" aria-labelledby="decision-atlas-title"><span className="section-index">02 / Decision model</span><h2 id="decision-atlas-title">Decision Atlas</h2><p>No recurring decision patterns are available for this profile.</p></section>;
  return <section className="decision-atlas" aria-labelledby="decision-atlas-title">
    <header className="atlas-heading"><div><span className="section-index">02 / Decision model</span><h2 id="decision-atlas-title">Decision Atlas</h2><p>Recurring considerations organized by the investment taxonomy—not a causal map.</p></div><div role="tablist" aria-label="Decision Atlas views"><button type="button" role="tab" aria-selected={view === "themes"} onClick={() => setView("themes")}>Themes</button><button type="button" role="tab" aria-selected={view === "inventory"} onClick={() => setView("inventory")}>All rationales</button></div></header>
    <div role="tabpanel" aria-label={view === "themes" ? "Decision themes" : "All rationales inventory"}>{view === "themes" ? <ThemesView graph={graph} themes={themes} onFindEvidence={onFindEvidence} /> : <InventoryView graph={graph} onFindEvidence={onFindEvidence} />}</div>
  </section>;
}
