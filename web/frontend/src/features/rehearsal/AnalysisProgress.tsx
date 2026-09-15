import { useEffect, useMemo, useState } from "react";
import type { ProgressEvent } from "../../api/events";
import type { AgentActivity } from "../../api/types";
import { ProcessStepper } from "../../components/ProcessStepper";
import { SafeMarkdown } from "../../components/SafeMarkdown";

const STEPS = [
  { id: "phase1", label: "Rationale analysis" },
  { id: "phase2", label: "Investment Decision Synthesis" },
  { id: "rehearsal", label: "Interactive rehearsal" },
];

const STEP_BY_STAGE: Record<string, string> = {
  queued: "phase1",
  preparing_inputs: "phase1",
  phase1_running: "phase1",
  phase2_running: "phase2",
  rehearsal_running: "rehearsal",
  awaiting_answer: "rehearsal",
  complete: "rehearsal",
};

const LABELS: Record<string, string> = {
  queued: "Assessment queued",
  preparing_inputs: "Preparing leakage-safe inputs",
  phase1_running: "Mapping pitch evidence to decision rationales",
  phase2_running: "Synthesizing the investment judgment",
  rehearsal_running: "Updating the evidence-responsive assessment",
  awaiting_answer: "Ready for your answer",
  complete: "Assessment ready",
  failed: "Assessment needs attention",
};

const DESCRIPTIONS: Record<string, string> = {
  queued: "The job has been accepted and is waiting for the local assessment worker.",
  preparing_inputs: "The pitch is being stored, verified, and separated from outcome-bearing material.",
  phase1_running: "The system is reading the pitch, retrieving relevant precedents and Investment Memory evidence, then testing which decision rationales apply.",
  phase2_running: "The locked rationale evidence is being weighed into a pitch-room decision, likelihood, confidence, and review priority.",
  rehearsal_running: "Your answer is being connected to the relevant rationale and the assessment is being updated.",
  awaiting_answer: "The assessment is paused for founder input; no provider call is currently running.",
  complete: "The public assessment artifacts are ready for review.",
};

function formatElapsed(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`;
}

function activityMessage(event: ProgressEvent): string {
  if (event.stage === "queued") return "Job accepted";
  if (event.stage === "preparing_inputs") return "Pitch stored; preparing leakage-safe inputs";
  if (event.stage === "phase1_running") {
    return typeof event.payload.message === "string" ? event.payload.message : "Rationale analysis started";
  }
  if (event.stage === "phase2_running") return "Investment Decision Synthesis started";
  if (event.stage === "rehearsal_running") return "Rehearsal assessment update started";
  if (event.stage === "awaiting_answer") return "Waiting for founder response";
  if (event.stage === "complete") return "Assessment artifacts completed";
  if (event.stage === "failed") return "Assessment stopped before completion";
  return event.stage.replaceAll("_", " ");
}

interface AnalysisProgressProps {
  stage: string;
  events?: ProgressEvent[];
  startedAt?: number;
  recoveryLabel?: string;
  onRecover?: () => void;
  recoveryPending?: boolean;
  agentActivity?: AgentActivity[];
}

export function AnalysisProgress({
  stage,
  events = [],
  startedAt = Date.now(),
  recoveryLabel,
  onRecover,
  recoveryPending = false,
  agentActivity = [],
}: AnalysisProgressProps) {
  const [now, setNow] = useState(Date.now());
  const failed = stage === "failed";
  const active = !failed && !["complete", "awaiting_answer"].includes(stage);
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  const previousStage = useMemo(
    () => [...events].reverse().find((event) => event.stage !== "failed")?.stage ?? "queued",
    [events],
  );
  const stepStage = failed ? previousStage : stage;
  const failure = [...events].reverse().find((event) => event.stage === "failed");
  const failureMessage = typeof failure?.payload.message === "string"
    ? failure.payload.message
    : "The assessment stopped before a model result was produced.";
  const recentAgentActivity = agentActivity.slice(-2);
  const olderAgentActivity = agentActivity.slice(0, -2);
  const activityCard = (activity: AgentActivity, index: number) => <article key={activity.activity_id} className={activity.status === "failed" ? "failed" : ""}>
    <div className="agent-response-meta"><strong>{activity.title}</strong><span>{activity.phase.replace("phase", "Phase ")} · iteration {activity.iteration}{activity.elapsed_seconds != null ? ` · ${activity.elapsed_seconds.toFixed(1)}s` : ""}</span></div>
    <SafeMarkdown className="agent-response-text">{activity.text}</SafeMarkdown>
    {activity.details.length > 0 && <details open={index === recentAgentActivity.length - 1}><summary>View questions, searches, and rationale output</summary><ul>{activity.details.map((detail, detailIndex) => <li key={`${activity.activity_id}-${detailIndex}`}><SafeMarkdown>{detail}</SafeMarkdown></li>)}</ul></details>}
  </article>;

  return <section className={`analysis-progress${failed ? " analysis-progress-failed" : ""}`} aria-live="polite">
    <span className="eyebrow">Canonical assessment</span>
    <h1>{LABELS[stage] || stage.replaceAll("_", " ")}</h1>
    <p>{failed
      ? "No model result was produced. Review the public error below, correct the configuration, and begin a new assessment."
      : DESCRIPTIONS[stage] || "The assessment is working through its public processing stages."}</p>
    <ProcessStepper steps={STEPS} current={STEP_BY_STAGE[stepStage] || "phase1"} />

    {failed ? <div className="analysis-failure" role="alert">
      <strong>Run stopped</strong>
      <p>{failureMessage}</p>
      {recoveryLabel && onRecover && <button className="button secondary" disabled={recoveryPending} onClick={onRecover}>
        {recoveryPending ? "Restarting…" : recoveryLabel}
      </button>}
    </div> : active && <div className="analysis-live">
      <div className="analysis-progressbar" role="progressbar" aria-label="Assessment activity"><i /></div>
      <div className="analysis-live-meta"><span>Provider activity in progress</span><time>Elapsed {formatElapsed(now - startedAt)}</time></div>
    </div>}

    {agentActivity.length > 0 && <section className="agent-responses" aria-label="Agent responses">
      <header><div><span className="eyebrow">Artifact-backed activity</span><h2>Agent responses</h2></div><span>{agentActivity.length} response{agentActivity.length === 1 ? "" : "s"}</span></header>
      <div className="agent-response-list">{recentAgentActivity.map(activityCard)}</div>
      {olderAgentActivity.length > 0 && <details className="agent-history"><summary>Inspect {olderAgentActivity.length} earlier agent {olderAgentActivity.length === 1 ? "response" : "responses"}</summary><div className="agent-response-list">{olderAgentActivity.map(activityCard)}</div></details>}
      <p className="agent-response-note">Structured outputs only. Prompts, credentials, raw provider payloads, and hidden chain-of-thought are not displayed.</p>
    </section>}

    {events.length > 0 && <div className="analysis-activity">
      <h2>Live activity</h2>
      <ol>{events.map((event) => <li key={event.event_id} className={event.stage === "failed" ? "failed" : ""}>
        <span aria-hidden="true" />
        <div><strong>{activityMessage(event)}</strong><small>{event.stage.replaceAll("_", " ")}</small></div>
      </li>)}</ol>
    </div>}
    <p className="analysis-privacy">This view reports public workflow events and artifacts, not hidden chain-of-thought.</p>
  </section>;
}
