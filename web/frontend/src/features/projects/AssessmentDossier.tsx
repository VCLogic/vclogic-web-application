import { ArrowRight, BookOpenText, FileText, History, Library, X } from "lucide-react";
import { Fragment, useMemo, useState } from "react";
import type { AssessmentCitation, CanonicalAssessment, Investor } from "../../api/types";
import { AssessmentActivityTimeline } from "./AssessmentActivity";
import { AssessmentMetricHelp, decisionLean, fitScore, founderSafeAssessmentText } from "../../components/AssessmentSemantics";

const title=(value:string)=>value.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase());
const referencePattern=/(P-\d{3}|R\d+|[WH]-[0-9a-f]+)/g;

function AnalysisWithCitations({text,citations,onOpen}:{text:string;citations:AssessmentCitation[];onOpen:(citation:AssessmentCitation)=>void}){
 const byId=new Map(citations.map(row=>[row.reference_id,row]));
 return <p className="full-analysis-copy">{text.split(referencePattern).map((part,index)=>{const citation=byId.get(part);return citation?<button key={`${part}-${index}`} className="citation-mark" onClick={()=>onOpen(citation)} aria-label={`Open source ${citation.number}: ${citation.title}`}>[{citation.number}]</button>:<Fragment key={`${part}-${index}`}>{part}</Fragment>})}</p>
}

function EvidenceDrawer({citation,onClose}:{citation:AssessmentCitation;onClose:()=>void}){
 const Icon=citation.source_type==="pitch"?FileText:citation.source_type==="precedent"?History:Library;
 return <aside className="evidence-drawer" aria-label={`Source ${citation.number}: ${citation.title}`}>
  <header><span><Icon size={17}/>{citation.source_type.replace("_"," ")}</span><button onClick={onClose} aria-label="Close source"><X/></button></header>
  <h4>{citation.title}</h4>
  {citation.decision_status&&<span className="evidence-decision">Observed decision: {citation.decision_status}</span>}
  {citation.excerpt?<blockquote>{citation.excerpt}</blockquote>:<p>Exact source detail is unavailable in this legacy artifact.</p>}
  {citation.rationale_labels.length>0&&<div className="citation-rationales">{citation.rationale_labels.map(label=><span key={label}>{title(label)}</span>)}</div>}
  <dl><div><dt>Source</dt><dd>{citation.source_reference||citation.episode_slug||"Unavailable"}</dd></div></dl>
  <details><summary>Technical reference</summary><code>{citation.reference_id}</code></details>
 </aside>
}

function RationaleGroup({label,kind,items}:{label:string;kind:string;items:string[]}){
 if(!items.length)return null;
 return <div className={`dossier-rationales ${kind}`}><span>{label}</span><div>{items.slice(0,5).map(item=><strong key={item}>{title(item)}</strong>)}</div></div>
}

export function AssessmentDossier({assessment,investor,onRehearse}:{assessment:CanonicalAssessment;investor?:Investor;onRehearse:(assessmentId:string)=>void}){
 const [open,setOpen]=useState<AssessmentCitation|null>(null);
 const citations=assessment.citations||[];
 const evidence=useMemo(()=>{
  const selected:AssessmentCitation[]=[];
  const seenTypes=new Set<string>();
  for(const citation of citations){if(!seenTypes.has(citation.source_type)){selected.push(citation);seenTypes.add(citation.source_type)}}
  for(const citation of citations){if(selected.length>=5)break;if(!selected.includes(citation))selected.push(citation)}
  return selected.slice(0,5);
 },[citations]);
 if(assessment.status!=="complete")return <article className={`assessment-dossier ${assessment.status}`}>
  <header><div><h3>{investor?.display_name||assessment.vc_slug}</h3><p>{investor?.firm}</p></div><span className="assessment-status">{assessment.status}</span></header>
  {assessment.status==="failed"?<div className="assessment-failure" role="alert"><strong>Assessment stopped</strong><p>{assessment.public_error||"The provider run did not complete."}</p></div>:<AssessmentActivityTimeline activity={assessment.activity||[]}/>} 
 </article>;
 return <article className="assessment-dossier complete">
  <header><div className="dossier-investor">{investor?.portrait_path&&<img src={investor.portrait_path} alt=""/>}<div><h3>{investor?.display_name||assessment.vc_slug}</h3><p>{investor?.firm}</p></div></div><span className="assessment-status">Canonical assessment</span></header>
  <div className="dossier-verdict"><strong className={assessment.decision?.toLowerCase()}>{decisionLean(assessment.decision)}</strong><dl><div><dt>Estimated investor fit</dt><dd>{fitScore(assessment.investment_likelihood)==null?"Unavailable":`${fitScore(assessment.investment_likelihood)}/100`}</dd><AssessmentMetricHelp kind="fit"/></div><div><dt>Assessment confidence</dt><dd>{fitScore(assessment.decision_confidence)==null?"Unavailable":`${fitScore(assessment.decision_confidence)}%`}</dd><AssessmentMetricHelp kind="confidence"/></div></dl></div>
  <p className="dossier-summary">{founderSafeAssessmentText(assessment.decision_summary)}</p>
  <div className="dossier-signal-grid">
   <RationaleGroup label="Creates conviction" kind="positive" items={assessment.positive_rationales}/>
   <RationaleGroup label="Creates concern" kind="negative" items={assessment.negative_rationales}/>
   <RationaleGroup label="Still unresolved" kind="unresolved" items={assessment.unresolved_rationales}/>
  </div>
  {evidence.length>0&&<section className="key-evidence"><h4>Evidence behind this assessment</h4><div>{evidence.map(row=><button key={row.reference_id} aria-label={`Evidence ${row.number}: ${row.title}`} onClick={()=>setOpen(row)}><span>[{row.number}]</span><strong>{row.title}</strong><small>{row.source_type.replace("_"," ")}</small></button>)}</div></section>}
  {open&&<EvidenceDrawer citation={open} onClose={()=>setOpen(null)}/>} 
  <div className="dossier-actions"><button className="button" onClick={()=>onRehearse(assessment.assessment_id)}>Start rehearsal <ArrowRight size={15}/></button></div>
  {assessment.decision_justification&&<details className="full-analysis"><summary><BookOpenText size={16}/> Full model analysis</summary><p className="analysis-note">This is the original synthesis. Exact commitment amounts are model-generated unless a linked source explicitly supports them.</p><AnalysisWithCitations text={founderSafeAssessmentText(assessment.decision_justification)} citations={citations} onOpen={setOpen}/></details>}
 </article>
}
