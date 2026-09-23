import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { api } from "../../api/client";
import { ProjectCard } from "./ProjectCard";
import "./sessions.css";

export function ProjectLibrary() {
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: api.sessions });
  const investors = useQuery({ queryKey: ["investors"], queryFn: api.investors, refetchInterval: 30_000 });
  const bySlug = new Map(investors.data?.investors.map(investor => [investor.vc_slug, investor]));
  return <section className="project-library">
    <header className="library-hero">
      <div><div className="eyebrow">Local project library</div><h1>Your rehearsal sessions</h1><p>Return to the evidence, questions, and decision movement from every investor-like rehearsal.</p></div>
      <Link className="button" to="/"><Plus size={15} /> New rehearsal</Link>
    </header>
    {sessions.isPending ? <div className="library-loading">Loading verified sessions…</div>
      : sessions.error ? <p className="error">{sessions.error.message}</p>
      : sessions.data?.sessions.length ? <div className="project-list">{sessions.data.sessions.map(session => <ProjectCard key={session.session_id} session={session} investor={bySlug.get(session.vc_slug)} />)}</div>
      : <div className="library-empty"><span>01</span><h2>No rehearsals yet</h2><p>Choose an investor-like profile, submit a pitch, and your first project will appear here.</p><Link className="button" to="/">Choose an investor</Link></div>}
  </section>;
}
