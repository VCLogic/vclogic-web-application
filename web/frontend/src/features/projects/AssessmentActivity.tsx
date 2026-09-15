import { Check, Circle, LoaderCircle, TriangleAlert } from "lucide-react";
import type { AssessmentActivity } from "../../api/types";

export function AssessmentActivityTimeline({activity}:{activity:AssessmentActivity[]}){
 return <section className="assessment-activity" aria-label="Assessment progress">
  <h3>What the system is doing</h3>
  <ol>{activity.map(row=><li key={row.stage} className={row.status}>
   <span aria-hidden="true">{row.status==="complete"?<Check/>:row.status==="active"?<LoaderCircle/>:row.status==="failed"?<TriangleAlert/>:<Circle/>}</span>
   <div><strong>{row.title}</strong><p>{row.detail}</p></div>
  </li>)}</ol>
  <p className="activity-safety">Only public, artifact-backed stages are shown. Prompts, credentials, raw provider payloads, and hidden reasoning stay private.</p>
 </section>
}
