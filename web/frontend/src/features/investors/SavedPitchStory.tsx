import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';

/** Entry points into the saved workflow, derived from actual assessment links. */
export function SavedPitchStory() {
  const projects=useQuery({queryKey:['pitch-projects'],queryFn:api.projects});
  const project=projects.data?.projects.find(row=>row.assessment_count>=3 && row.rehearsal_count>0);
  const assessments=useQuery({queryKey:['assessments',project?.project_id,project?.current_version_id],
    queryFn:()=>api.assessments(project!.project_id,project!.current_version_id),enabled:!!project});
  const sessions=useQuery({queryKey:['sessions'],queryFn:api.sessions,enabled:!!project});
  const linked=new Set(assessments.data?.assessments.flatMap(row=>row.rehearsal_session_ids));
  const session=sessions.data?.sessions.find(row=>linked.has(row.session_id) && ['complete','finished'].includes(row.status));
  if(!project || !session)return null;
  const path=`/pitches/${project.project_id}/versions/${project.current_version_id}`;
  const initial=session.initial_likelihood;
  const final=session.current_likelihood;
  return <aside className="saved-pitch-story" aria-label="Saved pitch journey">
    <span className="eyebrow">A pitch, three perspectives, one discussion</span>
    <h2>Follow the evidence from pitch to decision</h2>
    <p>Read the saved pitch, compare its investor assessments, then follow the founder’s answers and their effect on the investment judgment.</p>
    {initial!=null && final!=null && <p><strong>{Math.round(initial*100)} → {Math.round(final*100)}/100</strong> · Recorded funding likelihood after the discussion. This is a model judgment, not a calibrated probability.</p>}
    <div className="hero-actions">
      <a className="button light" href={`${path}?tab=pitch`}>1 · Read the pitch</a>
      <a className="text-link" href={`${path}?tab=comparison`}>2 · Compare investors</a>
      <a className="text-link" href={`/sessions/${session.session_id}`}>3 · Follow the discussion</a>
    </div>
  </aside>;
}
