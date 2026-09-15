import { useMemo, useState, type KeyboardEvent } from "react";
import { Filter, LockKeyhole } from "lucide-react";
import type { Components } from "react-markdown";
import type { Direction, Session } from "../../api/types";
import { SafeMarkdown } from "../../components/SafeMarkdown";
import { remarkEvidenceAnnotations } from "./annotatedMarkdown";

const filters: [Direction | "all", string][] = [
  ["all", "All evidence"], ["positive", "Positive pitch signals"],
  ["negative", "Negative pitch signals"], ["unresolved", "Unresolved pitch signals"],
];

export function PitchPanel({session,onEvidence,hidden=false}:{session:Session;onEvidence:(ids:string[])=>void;hidden?:boolean}) {
  const [filter,setFilter] = useState<Direction|"all">("all");
  const annotationPlugin = useMemo(() => remarkEvidenceAnnotations(session.annotations,session.pitch_text.length,filter),[filter,session.annotations,session.pitch_text.length]);
  const components:Components = { mark:({children,...props}) => {
    const attributes=props as typeof props&{"data-evidence-ids"?:string;"data-direction"?:Direction;"data-visible"?:string};
    const visible=attributes["data-visible"]==="true";
    const direction=attributes["data-direction"]??"unresolved";
    const evidenceIds=(attributes["data-evidence-ids"]??"").split("|").filter(Boolean);
    const openEvidence=()=>{if(visible&&evidenceIds.length)onEvidence(evidenceIds)};
    const onKeyDown=(event:KeyboardEvent<HTMLElement>)=>{if(visible&&(event.key==="Enter"||event.key===" ")){event.preventDefault();openEvidence()}};
    return <mark {...props} role="button" tabIndex={visible?0:-1} aria-disabled={!visible} aria-label={`${direction} pitch evidence`} onClick={openEvidence} onKeyDown={onKeyDown}>{children}</mark>;
  }};
  return <section id="workspace-pitch" role="tabpanel" hidden={hidden} className="panel pitch-panel">
    <header><div><span className="eyebrow">Pitch memo</span><h2>Evidence in the founder’s words</h2></div><span className="immutable"><LockKeyhole size={12}/> immutable</span></header>
    <div className="signal-filters"><Filter size={13}/>{filters.map(([value,label])=><button key={value} aria-label={label} aria-pressed={filter===value} onClick={()=>setFilter(value)}>{label.replace(" pitch signals","").replace(" evidence","")}</button>)}</div>
    <SafeMarkdown className="pitch-copy" remarkPlugins={[annotationPlugin]} components={components}>{session.pitch_text}</SafeMarkdown>
    <div className="legend"><span className="positive">Positive signal</span><span className="negative">Concern</span><span className="unresolved">Unresolved</span></div>
  </section>;
}
