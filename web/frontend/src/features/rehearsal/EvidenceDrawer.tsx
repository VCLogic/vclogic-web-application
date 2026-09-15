import { X } from "lucide-react";
import type { Evidence } from "../../api/types";
import { SafeMarkdown } from "../../components/SafeMarkdown";

export function EvidenceDrawer({evidence,onClose}:{evidence:Evidence[];onClose:()=>void}) {
  if(!evidence.length)return null;
  return <aside className="evidence-drawer" aria-label="Source evidence"><header><div><span className="eyebrow">Traceable evidence</span><h2>Why this signal appears</h2></div><button className="icon-button" onClick={onClose} aria-label="Close evidence"><X/></button></header>{evidence.map(row=><article key={row.evidence_id}><span className="pill">{row.source_kind}</span><SafeMarkdown className="evidence-excerpt">{row.excerpt}</SafeMarkdown><code>{row.source_path}</code>{row.confidence!=null&&<small>{Math.round(row.confidence*100)}% confidence</small>}</article>)}</aside>;
}
