import type { LikelihoodTimeline as TimelineRow } from "../../api/types";

function fit(value: number): string { return `${Math.round(value * 100)}/100`; }
function effect(value: TimelineRow["evidence_effect"]): string { return ({ baseline: "Baseline", synthesis: "Final decision synthesis", new_positive: "New positive evidence", new_negative: "New concern", clarification: "Clarification", unresolved: "Still unresolved", contradiction: "Contradiction" })[value]; }
function change(delta: number): string { const points = Math.round(Math.abs(delta) * 100); return points === 0 ? "no change" : `${delta > 0 ? "up" : "down"} ${points} points`; }

export function LikelihoodTimeline({ rows }: { rows: TimelineRow[] }) {
  return <section className="likelihood-timeline" aria-labelledby="likelihood-timeline-title"><header><h3 id="likelihood-timeline-title">Estimated fit over the rehearsal</h3><p>Only genuinely new decision-relevant evidence should move the assessment.</p></header>{rows.length ? <ol>{rows.map((row, index) => <li key={`${row.turn}-${index}`} aria-label={`${row.label}. ${effect(row.evidence_effect)}. ${fit(row.before)} to ${fit(row.after)}. ${change(row.delta)}`}><div className="timeline-marker" aria-hidden="true"><i /></div><div><span>{row.label}</span><strong>{fit(row.after)}</strong><small>{effect(row.evidence_effect)} · {change(row.delta)}</small>{row.answer_excerpt && <q>{row.answer_excerpt}</q>}</div></li>)}</ol> : <p className="likelihood-timeline-empty">No rehearsal fit history is available for this legacy assessment.</p>}</section>;
}
