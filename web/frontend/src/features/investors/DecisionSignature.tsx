import { useMemo, useState } from "react";
import type { Graph, RationaleNode } from "../../api/types";
import { humanizeRationale, knownCount } from "./decisionAtlas";

type SignatureGroup = "conviction" | "concern" | "context";
const GROUPS: { id: SignatureGroup; title: string; description: string }[] = [
  { id: "conviction", title: "Creates conviction", description: "Signals that most often appear positively in the observed record." },
  { id: "concern", title: "Creates concern", description: "Signals that most often appear negatively in the observed record." },
  { id: "context", title: "Context and unresolved", description: "Considerations that remain mixed, conditional, or unresolved." },
];

function label(node: RationaleNode): string { return humanizeRationale(node.taxonomy_label, humanizeRationale(node.title)); }
function groupFor(node: RationaleNode): SignatureGroup {
  const counts = node.direction_counts ?? {};
  const positive = knownCount(counts.positive) ?? 0;
  const negative = knownCount(counts.negative) ?? 0;
  const context = Object.entries(counts).reduce((sum, [direction, count]) => direction === "positive" || direction === "negative" ? sum : sum + (knownCount(count) ?? 0), 0);
  if (positive > negative && positive > context) return "conviction";
  if (negative > positive && negative > context) return "concern";
  if (!positive && !negative && !context) {
    if (node.direction === "positive") return "conviction";
    if (node.direction === "negative") return "concern";
  }
  return "context";
}
function ranked(nodes: RationaleNode[]): RationaleNode[] {
  return [...nodes].sort((left, right) => {
    const a = knownCount(left.occurrence_count); const b = knownCount(right.occurrence_count);
    if (a === undefined || b === undefined) { if (a !== b) return a === undefined ? 1 : -1; }
    else if (a !== b) return b - a;
    return label(left).localeCompare(label(right)) || left.node_id.localeCompare(right.node_id);
  });
}
function RationaleRow({ node, maximum, onFindEvidence }: { node: RationaleNode; maximum: number; onFindEvidence: (label: string) => void }) {
  const title = label(node); const count = knownCount(node.occurrence_count);
  const normalized = count === undefined || maximum <= 0 ? undefined : Math.round((count / maximum) * 100);
  return <article className="signature-rationale"><div className="signature-rationale-copy"><h3>{title}</h3><p>{node.definition?.trim() || "Definition unavailable."}</p><button type="button" onClick={() => onFindEvidence(node.taxonomy_label)} aria-label={`Find evidence for ${title}`}>Find evidence</button></div><div className="signature-recurrence"><span>{count === undefined ? "Recurrence unavailable" : `${count} observed ${count === 1 ? "activation" : "activations"}`}</span>{normalized !== undefined && <div className="signature-meter" role="meter" aria-label={`${title} recurrence`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={normalized} aria-valuetext={`${count} observed activations; ${normalized}% of the profile maximum`}><i style={{ width: `${normalized}%` }} /></div>}</div></article>;
}

export function DecisionSignature({ graph, onFindEvidence }: { graph: Graph; onFindEvidence: (label: string) => void }) {
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<"recurrence" | "label" | "direction">("recurrence");
  const maximum = Math.max(0, ...graph.nodes.map(node => knownCount(node.occurrence_count) ?? 0));
  const grouped = useMemo(() => Object.fromEntries(GROUPS.map(group => [group.id, ranked(graph.nodes.filter(node => groupFor(node) === group.id))])) as Record<SignatureGroup, RationaleNode[]>, [graph.nodes]);
  const byId = useMemo(() => new Map(graph.nodes.map(node => [node.node_id, node])), [graph.nodes]);
  const pairs = useMemo(() => {
    const unique = new Map<string, Graph["edges"][number]>();
    for (const edge of graph.edges) {
      const key = [edge.source, edge.target].sort().join("::");
      const current = unique.get(key);
      const count = knownCount(edge.occurrence_count); const currentCount = knownCount(current?.occurrence_count);
      if (!current || (count !== undefined && (currentCount === undefined || count > currentCount))) unique.set(key, edge);
    }
    return [...unique.values()].sort((left, right) => { const a = knownCount(left.occurrence_count); const b = knownCount(right.occurrence_count); if (a === undefined || b === undefined) return a === b ? left.edge_id.localeCompare(right.edge_id) : a === undefined ? 1 : -1; return b - a || left.edge_id.localeCompare(right.edge_id); });
  }, [graph.edges]);
  const inventory = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    const rows = graph.nodes.filter(node => !normalized || [label(node), node.definition ?? "", groupFor(node), knownCount(node.occurrence_count) ?? ""].join(" ").toLocaleLowerCase().includes(normalized));
    return [...rows].sort((left, right) => {
      if (sortBy === "label") return label(left).localeCompare(label(right));
      if (sortBy === "direction") return groupFor(left).localeCompare(groupFor(right)) || label(left).localeCompare(label(right));
      return ranked([left, right])[0] === left ? -1 : 1;
    });
  }, [graph.nodes, query, sortBy]);
  if (!graph.nodes.length) return <section className="decision-signature signature-empty" aria-labelledby="decision-signature-title"><span className="section-index">02 / Decision model</span><h2 id="decision-signature-title">Decision Signature</h2><p>No recurring decision patterns are available for this profile.</p></section>;
  return <section className="decision-signature" aria-labelledby="decision-signature-title"><header className="signature-heading"><div><span className="section-index">02 / Decision model</span><h2 id="decision-signature-title">Decision Signature</h2><p>A readable summary of what repeatedly creates conviction, creates concern, or remains contextual in the observed record.</p><p className="signature-method-note">Bar length shows frequency in the available source-linked record, not causal importance or model weight.</p></div><aside><strong>{graph.nodes.length}</strong><span>observed rationales</span></aside></header><div className="signature-groups">{GROUPS.map(group => <section key={group.id} className={`signature-group ${group.id}`} aria-label={group.title}><header><h3>{group.title}</h3><p>{group.description}</p></header><div>{grouped[group.id].slice(0,2).map(node => <RationaleRow key={node.node_id} node={node} maximum={maximum} onFindEvidence={onFindEvidence} />)}{grouped[group.id].length > 2 && <p className="signature-more">+ {grouped[group.id].length - 2} more in the complete inventory</p>}{!grouped[group.id].length && <p className="signature-none">No recurring signals in this category.</p>}</div></section>)}</div><section className="signature-pairs" aria-label="Often considered together"><header><div><h3>Often considered together</h3><p>These rationale pairs appeared in the same investigations. This is observed co-occurrence, not cause and effect.</p></div><span>{pairs.length} observed pairs</span></header><ol>{pairs.slice(0,3).map(edge => { const source = byId.get(edge.source); const target = byId.get(edge.target); const count = knownCount(edge.occurrence_count); return <li key={edge.edge_id}><span>{source ? label(source) : edge.source}</span><i aria-hidden="true">+</i><span>{target ? label(target) : edge.target}</span><strong>{count === undefined ? "Recurrence unavailable" : `${count} shared ${count === 1 ? "observation" : "observations"}`}</strong></li>; })}</ol>{pairs.length > 3 && <p className="signature-more">+ {pairs.length - 3} additional pairs omitted from this summary</p>}</section><details className="signature-inventory"><summary>Browse all {graph.nodes.length} rationales</summary><div className="signature-inventory-tools"><label>Search all rationales<input type="search" value={query} onChange={event => setQuery(event.target.value)} /></label><label>Sort rationale inventory<select value={sortBy} onChange={event => setSortBy(event.target.value as typeof sortBy)}><option value="recurrence">Most recurrent</option><option value="label">Rationale name</option><option value="direction">Decision role</option></select></label><p role="status">Showing {inventory.length} of {graph.nodes.length} rationales</p></div><div className="signature-inventory-table"><table><thead><tr><th>Rationale</th><th>Decision role</th><th>Recurrence</th></tr></thead><tbody>{inventory.map(node => <tr key={node.node_id}><td>{label(node)}</td><td>{GROUPS.find(group => group.id === groupFor(node))?.title}</td><td>{knownCount(node.occurrence_count) ?? "Unavailable"}</td></tr>)}</tbody></table></div></details></section>;
}
