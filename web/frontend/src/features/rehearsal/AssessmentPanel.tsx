import { useState } from "react";
import type { Components } from "react-markdown";
import type { Assessment, DecisionPath as DecisionPathRow, Evidence, Graph, LikelihoodTimeline as TimelineRow } from "../../api/types";
import { DecisionGauge } from "../../components/DecisionGauge";
import { RationaleFingerprint } from "../../components/RationaleFingerprint";
import { SafeMarkdown } from "../../components/SafeMarkdown";
import { ScoreTrajectory } from "../../components/ScoreTrajectory";
import { DecisionPath } from "./DecisionPath";
import { LikelihoodTimeline } from "./LikelihoodTimeline";
import { AssessmentMetricHelp, decisionLean, fitScore, founderSafeAssessmentText } from "../../components/AssessmentSemantics";

function score(value?:number){const result=fitScore(value);return result==null?"Unavailable":`${result}/100`}
function confidence(value?:number){const result=fitScore(value);return result==null?"Unavailable":`${result}%`}
const referencePattern=/\b(?:P-\d{3}|A-\d{3}|R\d+|[WH]-[0-9a-f]+)\b/g;
type SourceLink={number:number;referenceId:string;title:string;evidenceIds:string[]};

function sourceLinks(text:string,evidence:Evidence[],graph?:Graph):SourceLink[]{
  const references=[...text.matchAll(referencePattern)].map(match=>match[0]);
  const unique=[...new Set(references)];
  const evidenceById=new Map(evidence.map(row=>[row.evidence_id,row]));
  const nodesById=new Map((graph?.nodes||[]).map(row=>[row.node_id,row]));
  return unique.map((referenceId,index)=>{
    const row=evidenceById.get(referenceId);
    const node=nodesById.get(referenceId);
    if(node)return {number:index+1,referenceId,title:node.title,evidenceIds:node.evidence_ids};
    if(referenceId.startsWith("P-"))return {number:index+1,referenceId,title:"Current pitch",evidenceIds:row?[referenceId]:[]};
    if(referenceId.startsWith("A-"))return {number:index+1,referenceId,title:"Founder response",evidenceIds:row?[referenceId]:[]};
    if(referenceId.startsWith("H-"))return {number:index+1,referenceId,title:row?.source_path?`Historical precedent · ${row.source_path}`:"Historical precedent",evidenceIds:row?[referenceId]:[]};
    if(referenceId.startsWith("W-"))return {number:index+1,referenceId,title:row?.source_title||"Investment Memory evidence",evidenceIds:row?[referenceId]:[]};
    return {number:index+1,referenceId,title:"Supporting source",evidenceIds:row?[referenceId]:[]};
  });
}

function JustificationWithSources({text,evidence,graph,onEvidence}:{text:string;evidence:Evidence[];graph?:Graph;onEvidence:(ids:string[])=>void}){
  const sources=sourceLinks(text,evidence,graph);
  if(!sources.length)return <SafeMarkdown className="justification">{text}</SafeMarkdown>;
  const byReference=new Map(sources.map(row=>[row.referenceId,row]));
  const byNumber=new Map(sources.map(row=>[String(row.number),row]));
  const linked=text.replace(referencePattern,reference=>`[${byReference.get(reference)?.number}](#assessment-source-${byReference.get(reference)?.number})`);
  const components:Components={a:({href,children})=>{
    const source=href?.startsWith("#assessment-source-")?byNumber.get(href.slice("#assessment-source-".length)):undefined;
    if(!source)return <span>{children}</span>;
    return <button className="citation-mark" disabled={!source.evidenceIds.length} onClick={()=>onEvidence(source.evidenceIds)} aria-label={`Open source ${source.number}: ${source.title}`}>[{children}]</button>;
  }};
  return <div className="assessment-analysis"><SafeMarkdown className="justification" components={components}>{linked}</SafeMarkdown><details className="assessment-sources"><summary>{sources.length} sources cited</summary><ol>{sources.map(source=><li key={source.referenceId}><button disabled={!source.evidenceIds.length} onClick={()=>onEvidence(source.evidenceIds)} aria-label={`Open source ${source.number}: ${source.title}`}><span>[{source.number}]</span>{source.title}</button></li>)}</ol></details></div>;
}

export function AssessmentPanel({initial,current,graph,evidence=[],path=[],timeline=[],onEvidence,hidden=false}:{initial?:Assessment;current?:Assessment;graph?:Graph;evidence?:Evidence[];path?:DecisionPathRow[];timeline?:TimelineRow[];onEvidence:(ids:string[])=>void;hidden?:boolean}) {
  const [view,setView]=useState<"current"|"initial"|"difference">("current");
  if(!current&&!initial)return <section className="panel assessment"><p>Assessment is being prepared…</p></section>;
  const assessment=view==="initial"?initial:current||initial!;
  const nodes=graph?.nodes||[];
  const positive=nodes.filter(n=>n.direction==="positive").map(n=>n.taxonomy_label);
  const negative=nodes.filter(n=>n.direction==="negative").map(n=>n.taxonomy_label);
  const unresolved=nodes.filter(n=>["unresolved","neutral","mixed"].includes(n.direction)).map(n=>n.taxonomy_label);
  return <section id="workspace-decision" role="tabpanel" hidden={hidden} className="panel assessment">
    <header><div><span className="eyebrow">Decision console</span><h2>Investment Decision Synthesis</h2></div><span className={`decision ${assessment?.decision.toLowerCase()}`}>{decisionLean(assessment?.decision)}</span></header>
    <div className="assessment-snapshots"><div><span>Initial assessment</span><strong>{decisionLean(initial?.decision)} · {score(initial?.investment_likelihood)}</strong></div><div><span>Current assessment</span><strong>{decisionLean(current?.decision)} · {score(current?.investment_likelihood)}</strong></div></div>
    {initial&&current&&<ScoreTrajectory initial={initial.investment_likelihood} current={current.investment_likelihood}/>}
    {view!=="initial"&&current?.score_reconciliation&&<p className="score-reconciliation" role="status">{founderSafeAssessmentText(current.score_reconciliation)}</p>}
    <div className="segmented assessment-switch">{(["initial","current","difference"] as const).map(x=><button className={view===x?"active":""} onClick={()=>setView(x)} key={x}>{x[0].toUpperCase()+x.slice(1)}</button>)}</div>
    {view==="difference"&&initial&&current?<div className="difference-note"><strong>{current.decision===initial.decision?"Decision held":"Decision changed"}</strong><p>Estimated investor fit moved by {Math.round((current.investment_likelihood-initial.investment_likelihood)*100)} points as founder evidence was added.</p></div>:assessment&&<div className="decision-block"><DecisionGauge value={assessment.investment_likelihood}/><AssessmentMetricHelp kind="fit"/><div className="metrics"><span>Assessment confidence <strong>{confidence(assessment.decision_confidence)}</strong><AssessmentMetricHelp kind="confidence"/></span>{assessment.review_priority_score!=null&&<span>Review priority <strong>{score(assessment.review_priority_score)}</strong></span>}</div><JustificationWithSources text={founderSafeAssessmentText(assessment.decision_justification)} evidence={evidence} graph={graph} onEvidence={onEvidence}/></div>}
    <RationaleFingerprint context="Current-pitch rationales" positive={positive} negative={negative} unresolved={unresolved}/><LikelihoodTimeline rows={timeline}/><DecisionPath rows={path} finalDecision={(current||initial)!.decision} onEvidence={onEvidence}/>
  </section>;
}
