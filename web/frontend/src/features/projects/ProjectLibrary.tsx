import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FilePlus2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import "./projects.css";

const plural=(count:number,label:string)=>`${count.toLocaleString()} ${label}${count===1?"":"s"}`;

export function ProjectLibrary(){
  const query=useQuery({queryKey:["pitch-projects"],queryFn:api.projects});
  return <section className="pitch-library">
    <header className="pitch-library-heading"><div><h1>My pitches</h1><p>One durable briefing. Multiple investor-like assessments and rehearsal attempts.</p></div><Link className="button" to="/pitches/new"><FilePlus2 size={16}/> New pitch project</Link></header>
    {query.isPending?<p className="project-state-message">Loading pitch projects…</p>:query.isError?<p className="error" role="alert">{query.error.message}</p>:query.data.projects.length===0?<div className="pitch-library-empty"><h2>Your pitch library starts here</h2><p>Store one immutable pitch, compare investor-like profiles, then return for another rehearsal without rebuilding the assessment.</p><Link className="button" to="/pitches/new">Create a pitch project</Link></div>:<ol className="pitch-project-register">{query.data.projects.map((project,index)=><li key={project.project_id}><span className="project-exhibit">{String(index+1).padStart(2,"0")}</span><div><h2>{project.display_name}</h2><p>{project.company_aliases.join(" · ")}</p></div><dl><div><dt>Versions</dt><dd>{plural(project.version_count,"pitch version")}</dd></div><div><dt>Coverage</dt><dd>{plural(project.assessment_count,"investor assessment")}</dd></div><div><dt>Practice</dt><dd>{plural(project.rehearsal_count,"rehearsal")}</dd></div></dl><Link to={`/pitches/${project.project_id}/versions/${project.current_version_id}`} aria-label={`Open ${project.display_name}`}>Open project <ArrowRight size={15}/></Link></li>)}</ol>}
  </section>;
}
