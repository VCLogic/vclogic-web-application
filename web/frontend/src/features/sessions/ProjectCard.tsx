import { ArrowRight, CircleAlert, Clock3, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import type { Investor, SessionSummary } from "../../api/types";
import { InvestorPortrait } from "../../components/InvestorPortrait";
import { ScoreTrajectory } from "../../components/ScoreTrajectory";

const ACTIVE = new Set(["queued", "preparing_inputs", "phase1_running", "phase2_running", "rehearsal_running"]);

function dateLabel(raw: string) {
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? raw : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function ProjectCard({ session, investor }: { session: SessionSummary; investor?: Investor }) {
  const verified = session.verification_status === "verified";
  const active = ACTIVE.has(session.status);
  const failed = session.status === "failed" || !verified;
  const company = session.company_aliases.join(", ") || "Untitled company";
  return <article className={`project-card ${failed ? "failed" : active ? "active" : "complete"}`}>
    <InvestorPortrait name={session.investor_display_name} src={investor?.portrait_path} alt={investor?.portrait_alt} className="project-portrait" />
    <div className="project-main">
      <div className="project-meta"><span>{session.investor_display_name}</span><time>{dateLabel(session.created_at)}</time></div>
      <h2>{company}</h2>
      <div className="project-state">
        {failed ? <><CircleAlert size={13} /> Needs attention</> : active ? <><Clock3 size={13} /> Analysis in progress</> : <><ShieldCheck size={13} /> Verified rehearsal</>}
      </div>
      {session.initial_likelihood != null && session.current_likelihood != null
        ? <ScoreTrajectory initial={session.initial_likelihood} current={session.current_likelihood} />
        : <p className="project-pending">{active ? "Building the initial investor assessment…" : "No score trajectory recorded."}</p>}
    </div>
    <div className="project-decision">
      <span>Current decision</span>
      <strong className={session.current_decision?.toLowerCase()}>{session.current_decision || "—"}</strong>
      {session.current_likelihood != null && <b>{Math.round(session.current_likelihood * 100)}%</b>}
    </div>
    {verified ? <Link className="project-link" to={`/sessions/${session.session_id}`}>Resume rehearsal <ArrowRight size={15} /></Link> : <span className="project-disabled">Artifact verification failed</span>}
  </article>;
}
