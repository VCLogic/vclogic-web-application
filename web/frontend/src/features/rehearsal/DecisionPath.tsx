import { FileText, MessageSquareText } from "lucide-react";
import type { DecisionPath as DecisionPathRow } from "../../api/types";
import { SafeMarkdown } from "../../components/SafeMarkdown";

function humanize(value: string): string {
  const text = value.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const directionCopy = {
  positive: "Creates conviction",
  negative: "Creates concern",
  unresolved: "Remains unresolved",
} as const;

interface PathGroup {
  rationaleId: string;
  rationaleLabel: string;
  direction: DecisionPathRow["direction"];
  contribution: string;
  evidence: DecisionPathRow[];
}

function groupRows(rows: DecisionPathRow[]): PathGroup[] {
  const groups = new Map<string, PathGroup>();
  for (const row of rows) {
    const existing = groups.get(row.rationale_id);
    if (existing) {
      if (!existing.evidence.some(item => item.evidence_id === row.evidence_id)) {
        existing.evidence.push(row);
      }
      if (row.baseline_or_rehearsal === "rehearsal" && row.direction !== "unresolved") {
        existing.direction = row.direction;
      }
      continue;
    }
    groups.set(row.rationale_id, {
      rationaleId: row.rationale_id,
      rationaleLabel: row.rationale_label,
      direction: row.direction,
      contribution: row.contribution,
      evidence: [row],
    });
  }
  return [...groups.values()];
}

export function DecisionPath({ rows, finalDecision, onEvidence }: {
  rows: DecisionPathRow[];
  finalDecision: "In" | "Out";
  onEvidence: (ids: string[]) => void;
}) {
  const groups = groupRows(rows);
  return <section className="decision-path" aria-labelledby="decision-path-title">
    <header>
      <div>
        <h3 id="decision-path-title">Decision Path</h3>
        <p>How pitch evidence and founder responses shaped each investment rationale.</p>
      </div>
      <span>Final assessment: <strong>{finalDecision}</strong></span>
    </header>
    {groups.length ? <div className="decision-path-rows">
      {groups.map(group => <article
        key={group.rationaleId}
        className={`decision-path-group ${group.direction}`}
        aria-label={`${humanize(group.rationaleLabel)} decision path`}
      >
        <header className="path-rationale">
          <div>
            <span>{humanize(group.rationaleLabel)}</span>
            <strong>{directionCopy[group.direction]}</strong>
          </div>
          <SafeMarkdown className="path-contribution">{group.contribution}</SafeMarkdown>
        </header>
        <ul className="path-evidence-list">
          {group.evidence.map(row => <li key={row.path_id} className={row.evidence_origin}>
            <span>
              {row.evidence_origin === "pitch" ? <FileText size={14}/> : <MessageSquareText size={14}/>} {" "}
              {row.evidence_origin === "pitch" ? "Pitch evidence" : "Founder response"}
            </span>
            <SafeMarkdown className="path-evidence-excerpt">{row.evidence_excerpt}</SafeMarkdown>
            {row.contribution !== group.contribution && <SafeMarkdown className="path-answer-effect">{row.contribution}</SafeMarkdown>}
            <button
              type="button"
              aria-label={`Inspect supporting evidence for ${row.evidence_excerpt}`}
              onClick={() => onEvidence([row.evidence_id, ...row.supporting_evidence_ids])}
            >Inspect evidence</button>
          </li>)}
        </ul>
      </article>)}
    </div> : <p className="decision-path-empty">No evidence path is available for this legacy assessment.</p>}
  </section>;
}
