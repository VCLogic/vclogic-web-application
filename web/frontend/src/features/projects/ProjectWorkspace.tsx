import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePenLine, LockKeyhole } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, api } from "../../api/client";
import type { RehearsalDepth } from "../../api/types";
import { SafeMarkdown } from "../../components/SafeMarkdown";
import { AssessmentDossier } from "./AssessmentDossier";
import { InvestorComparison } from "./InvestorComparison";
import "./projects.css";

type Tab="pitch"|"comparison"|"assessments"|"rehearsals";

export function ProjectWorkspace(){
 const {projectId="",versionId=""}=useParams();
 const [params,setParams]=useSearchParams();
 const requestedTab=params.get("tab");
 const tab:Tab=requestedTab==="match"?"comparison":(["pitch","comparison","assessments","rehearsals"].includes(requestedTab||"")?requestedTab as Tab:"pitch");
 const navigate=useNavigate();
 const client=useQueryClient();
 const project=useQuery({queryKey:["project",projectId],queryFn:()=>api.project(projectId)});
 const version=useQuery({queryKey:["pitch-version",projectId,versionId],queryFn:()=>api.pitchVersion(projectId,versionId)});
 const investors=useQuery({queryKey:["investors"],queryFn:api.investors,refetchInterval:30_000});
 const assessments=useQuery({queryKey:["assessments",projectId,versionId],queryFn:()=>api.assessments(projectId,versionId),refetchInterval:q=>q.state.data?.assessments.some(row=>["queued","running"].includes(row.status))?1500:false});
 const comparison=useQuery({queryKey:["comparison",projectId,versionId],queryFn:async()=>{try{return await api.comparison(projectId,versionId)}catch(error){if(error instanceof ApiError&&error.status===404)return null;throw error}},refetchInterval:q=>q.state.data&&["queued","running"].includes(q.state.data.status)?1500:false,retry:false});
 const [selected,setSelected]=useState<string[]>([]);
 const [authorized,setAuthorized]=useState(false);
 const [error,setError]=useState("");
 const [revision,setRevision]=useState("");
 const [editing,setEditing]=useState(false);
 const [depth,setDepth]=useState<RehearsalDepth>("standard");
 const previousInvestors=useRef<Record<string,string|null>>({});
 useEffect(()=>{
  if(!investors.data)return;
  const current=Object.fromEntries(investors.data.investors.map(row=>[row.vc_slug,row.investor_version_id??null]));
  const changed=selected.filter(slug=>slug in previousInvestors.current&&previousInvestors.current[slug]!==current[slug]);
  if(changed.length){setSelected(values=>values.filter(slug=>!changed.includes(slug)));setAuthorized(false);setError("An investor version or availability changed. Review the available profiles and select again.")}
  previousInvestors.current=current;
 },[investors.data]);
 useEffect(()=>{
  if(!comparison.data||!investors.data)return;
  const retained=comparison.data.assessments.filter(row=>investors.data.investors.some(profile=>profile.vc_slug===row.vc_slug&&(profile.investor_version_id??null)===(row.investor_version_id??null))).map(row=>row.vc_slug);
  setSelected(values=>Array.from(new Set([...values,...retained])));
 },[comparison.data?.comparison_id,comparison.data?.assessments.map(row=>row.assessment_id).join("|"),Boolean(investors.data)]);
 const refresh=()=>{client.invalidateQueries({queryKey:["assessments",projectId,versionId]});client.invalidateQueries({queryKey:["comparison",projectId,versionId]})};
 const completedSlugs=new Set(assessments.data?.assessments.filter(row=>row.status==="complete"&&(row.investor_version_id??null)===(investors.data?.investors.find(investor=>investor.vc_slug===row.vc_slug)?.investor_version_id??null)).map(row=>row.vc_slug)||[]);
 const needsProvider=selected.some(slug=>!completedSlugs.has(slug));
 const run=useMutation({mutationFn:()=>api.updateComparison(projectId,versionId,selected,needsProvider?authorized:false,Object.fromEntries((investors.data?.investors||[]).filter(row=>selected.includes(row.vc_slug)&&row.investor_version_id).map(row=>[row.vc_slug,row.investor_version_id!]))),onSuccess:()=>{refresh();setError("");setAuthorized(false)},onError:e=>setError(e.message)});
 const revise=useMutation({mutationFn:()=>api.createVersion(projectId,revision),onSuccess:row=>navigate(`/pitches/${projectId}/versions/${row.version_id}`)});
 const rehearse=useMutation({mutationFn:(id:string)=>api.startAssessmentRehearsal(id,depth),onSuccess:job=>navigate(`/sessions/${job.session_id}`)});
 const profileRows=investors.data?.investors||[];
 const attempts=useMemo(()=>assessments.data?.assessments.flatMap(row=>row.rehearsal_session_ids.map(id=>({id,row})))||[],[assessments.data]);
 const viewAssessment=(id:string)=>{setParams({tab:"assessments"});setTimeout(()=>document.getElementById(`assessment-${id}`)?.scrollIntoView({behavior:"smooth",block:"start"}),0)};
 if(project.isPending||version.isPending)return <p className="project-state-message">Opening verified pitch…</p>;
 if(project.isError||version.isError)return <p className="error" role="alert">{(project.error||version.error)?.message}</p>;
 return <section className="pitch-workspace">
  <header className="workspace-heading"><div><Link to="/pitches">My pitches</Link><h1>{project.data.display_name}</h1><p>Pitch version {project.data.versions.findIndex(row=>row.version_id===versionId)+1} · {version.data.character_count.toLocaleString()} characters</p></div><div className="immutable-note"><LockKeyhole size={16}/><span>This evaluated version is immutable.</span></div></header>
  <nav className="workspace-tabs" role="tablist" aria-label="Pitch project"><button role="tab" aria-selected={tab==="pitch"} onClick={()=>setParams({tab:"pitch"})}>Pitch</button><button role="tab" aria-selected={tab==="comparison"} onClick={()=>setParams({tab:"comparison"})}>Investor comparison</button><button role="tab" aria-selected={tab==="assessments"} onClick={()=>setParams({tab:"assessments"})}>Assessments</button><button role="tab" aria-selected={tab==="rehearsals"} onClick={()=>setParams({tab:"rehearsals"})}>Rehearsals</button></nav>
  {tab==="pitch"&&<article className="project-pitch"><div className="pitch-version-index"><h2>Version history</h2>{project.data.versions.map((row,index)=><Link className={row.version_id===versionId?"active":""} key={row.version_id} to={`/pitches/${projectId}/versions/${row.version_id}`}><span>Version {index+1}</span><small>{new Date(row.created_at).toLocaleDateString()}</small></Link>)}<button onClick={()=>{setEditing(!editing);setRevision(version.data.pitch_text)}}><FilePenLine size={15}/> Create revised version</button></div><div className="project-pitch-sheet"><SafeMarkdown>{version.data.pitch_text}</SafeMarkdown>{editing&&<form className="revision-editor" onSubmit={event=>{event.preventDefault();revise.mutate()}}><h2>New immutable version</h2><textarea rows={18} value={revision} onChange={event=>setRevision(event.target.value)}/><button className="button">Save revised version</button></form>}</div></article>}
  {tab==="comparison"&&<div className="match-workspace"><header><h2>Who should assess this pitch?</h2><p>Choose one profile for an individual view or several to compare. Existing canonical assessments are reused; only newly selected profiles need provider work.</p></header><div className="investor-selector">{profileRows.map(row=>{const locked=comparison.data?.assessments.some(assessment=>assessment.vc_slug===row.vc_slug&&(assessment.investor_version_id??null)===(row.investor_version_id??null))||false;return <label key={row.vc_slug} className={selected.includes(row.vc_slug)?"selected":""}><input type="checkbox" aria-label={row.display_name} checked={selected.includes(row.vc_slug)} disabled={locked||(!selected.includes(row.vc_slug)&&selected.length===6)} onChange={()=>setSelected(values=>values.includes(row.vc_slug)?values.filter(value=>value!==row.vc_slug):[...values,row.vc_slug])}/>{row.portrait_path&&<img src={row.portrait_path} alt=""/>}<span><strong>{row.display_name}</strong><small>{locked?"Already in this comparison":row.firm}{row.investor_version_id?` · Version ${row.investor_version_id.slice(0,8)}`:""}</small></span></label>})}</div>{needsProvider&&<label className="match-authorization"><input type="checkbox" checked={authorized} onChange={event=>setAuthorized(event.target.checked)} aria-label="Authorize provider API costs"/><span>Authorize provider API costs for {selected.filter(slug=>!completedSlugs.has(slug)).length} new canonical assessment{selected.filter(slug=>!completedSlugs.has(slug)).length===1?"":"s"}. Completed assessments will not rerun.</span></label>}{!needsProvider&&selected.length>0&&<p className="reuse-note"><LockKeyhole size={15}/> Every selected assessment already exists. Updating this view has no provider cost.</p>}{error&&<p role="alert" className="error">{error}</p>}<button className="button" disabled={selected.length<1||run.isPending||(needsProvider&&!authorized)} onClick={()=>run.mutate()}>{comparison.data?"Update investor comparison":selected.length===1?"Assess with selected investor":`Compare ${selected.length} investor-like profiles`}</button>{comparison.data&&<InvestorComparison comparison={comparison.data} investors={profileRows} onView={viewAssessment} onRehearse={id=>rehearse.mutate(id)}/>}</div>}
  {tab==="assessments"&&<div className="assessment-register"><header><h2>Canonical assessments</h2><p>Each dossier is the reusable Phase 1 rationale analysis and Phase 2 decision synthesis for this exact pitch version.</p></header>{!assessments.data?.assessments.length?<div className="assessment-empty"><h3>No assessments yet</h3><p>Choose an investor in the comparison tab to build the first canonical assessment.</p><button onClick={()=>setParams({tab:"comparison"})}>Choose an investor</button></div>:assessments.data.assessments.map(row=><div id={`assessment-${row.assessment_id}`} key={row.assessment_id}><AssessmentDossier assessment={row} investor={profileRows.find(investor=>investor.vc_slug===row.vc_slug)} onRehearse={id=>rehearse.mutate(id)}/></div>)}</div>}
  {tab==="rehearsals"&&<div className="attempt-register"><header><h2>Rehearsal attempts</h2><p>Every conversation is preserved and begins from the canonical assessment attached to this exact pitch version.</p></header><label className="global-depth">Default depth for the next rehearsal<select value={depth} onChange={event=>setDepth(event.target.value as RehearsalDepth)}><option value="quick">Quick · up to 3 questions</option><option value="standard">Standard · up to 5 questions</option><option value="deep">Deep · up to 8 questions</option></select></label>{attempts.length===0?<p>No rehearsal attempts yet.</p>:attempts.map(({id,row},index)=><Link key={id} to={`/sessions/${id}`}><span>Attempt {index+1}</span><strong>{profileRows.find(investor=>investor.vc_slug===row.vc_slug)?.display_name||row.vc_slug}</strong></Link>)}</div>}
 </section>;
}
