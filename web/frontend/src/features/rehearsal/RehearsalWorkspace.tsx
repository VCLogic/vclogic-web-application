import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { Download, ShieldCheck } from "lucide-react";
import { api, ApiError } from "../../api/client";
import { subscribeToSession, type ProgressEvent } from "../../api/events";
import { InvestorPortrait } from "../../components/InvestorPortrait";
import { SimulationBadge } from "../../components/SimulationBadge";
import { AnalysisProgress } from "./AnalysisProgress";
import { AssessmentPanel } from "./AssessmentPanel";
import { ConversationPanel } from "./ConversationPanel";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { PitchPanel } from "./PitchPanel";
import { WorkspaceTabs, type WorkspaceTab } from "./WorkspaceTabs";
import type { Session } from "../../api/types";
import "./rehearsal.css";
import "./chat.css";
import "./workspace-redesign.css";
import "./markdown-overrides.css";

export function RehearsalExperience({session,busy,stage,onAnswer,onFinish,onRetry,onEvidence}:{
  session:Session;busy:boolean;stage:string;onAnswer:(text:string)=>void;onFinish:()=>void;onRetry:()=>void;onEvidence:(ids:string[])=>void;
}) {
  const complete = session.status === "complete" || session.status === "finished";
  const [activeTab,setActiveTab] = useState<WorkspaceTab>("conversation");
  return <div className={complete?"completed-rehearsal":"completed-rehearsal active-rehearsal-shell"}>
    <WorkspaceTabs active={activeTab} onChange={setActiveTab} showAssessment={complete}/>
    {activeTab === "conversation"&&<ConversationPanel session={session} busy={busy} activityStage={stage} onAnswer={onAnswer} onFinish={onFinish} onRetry={onRetry}/>}
    {complete&&activeTab === "assessment"&&<div id="workspace-assessment" role="tabpanel"><AssessmentPanel initial={session.initial_assessment} current={session.current_assessment} graph={session.rationale_graph} evidence={session.evidence} path={session.decision_path} timeline={session.likelihood_timeline} onEvidence={onEvidence}/></div>}
    {activeTab === "pitch"&&<div id="workspace-pitch" role="tabpanel"><PitchPanel session={session} onEvidence={onEvidence}/></div>}
  </div>;
}

export function RehearsalWorkspace() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [stage, setStage] = useState("queued");
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const [streamVersion, setStreamVersion] = useState(0);
  const [operationActive, setOperationActive] = useState(false);
  const operationStartedAt = useRef(0);
  const pendingQuestionId = useRef<string | null>(null);
  const lastEventId = useRef(0);
  const [selected, setSelected] = useState<string[]>([]);
  const { data: session, error } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.session(sessionId),
    refetchInterval: query => {
      if (query.state.data?.operation_active) return 1500;
      if (operationActive && Date.now() - operationStartedAt.current < 180_000) return 1500;
      return ["preparing_inputs", "queued"].includes(query.state.data?.status || "") ? 2500 : false;
    },
    retry: true,
  });
  const { data: profile } = useQuery({
    queryKey: ["profile", session?.vc_slug],
    queryFn: () => api.profile(session!.vc_slug),
    enabled: Boolean(session?.vc_slug),
  });
  useEffect(() => {
    lastEventId.current = 0;
    setEvents([]);
    setStartedAt(Date.now());
  }, [sessionId]);

  useEffect(() => {
    return subscribeToSession(`/api/sessions/${sessionId}/events?after=${lastEventId.current}`, event => {
      lastEventId.current = Math.max(lastEventId.current, event.event_id);
      setStage(event.stage);
      setEvents(current => current.some(row => row.event_id === event.event_id) ? current : [...current, event]);
      if (["awaiting_answer", "complete", "failed"].includes(event.stage)) {
        void queryClient.refetchQueries({ queryKey: ["session", sessionId], type: "active" }).finally(() => setOperationActive(false));
      } else {
        void queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
      }
    });
  }, [sessionId, queryClient, streamVersion]);

  useEffect(() => {
    if (!operationActive || !session) return;
    const terminal = ["complete", "finished", "failed"].includes(session.status);
    const questionAdvanced = Boolean(
      pendingQuestionId.current
      && session.active_question?.question_id !== pendingQuestionId.current
    );
    if (terminal || questionAdvanced) setOperationActive(false);
  }, [operationActive, session]);

  const mutation = useMutation({
    mutationFn: async (action: { kind: "answer" | "finish" | "retry"; text?: string }) => action.kind === "answer"
      ? api.answer(sessionId, action.text || "")
      : action.kind === "finish" ? api.finish(sessionId) : api.retry(sessionId),
    onMutate: action => {
      operationStartedAt.current = Date.now();
      pendingQuestionId.current = action.kind === "answer" ? session?.active_question?.question_id || null : null;
      setOperationActive(true);
    },
    onSuccess: () => {
      setStage("rehearsal_running");
      setStreamVersion(value => value + 1);
      void queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    },
    onError: error => {
      if (error instanceof ApiError && error.code === "session_busy") {
        operationStartedAt.current = Date.now();
        setOperationActive(true);
        setStage("rehearsal_running");
        void queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
        return;
      }
      setOperationActive(false);
    },
  });

  if (error) return <p className="error">Unable to load the rehearsal: {error.message}</p>;
  if (!session) return <AnalysisProgress stage={stage} events={events} startedAt={startedAt} />;

  const processing = ["queued", "preparing_inputs", "phase1_running", "phase2_running"].includes(session.status) && !session.initial_assessment;
  const complete = session.status === "complete" || session.status === "finished";
  const progressStage = stage === "queued" && session.status === "failed" ? "failed" : stage;
  const evidence = session.evidence.filter(item => selected.includes(item.evidence_id));
  const investor = profile?.investor;
  const busyConflict = mutation.error instanceof ApiError && mutation.error.code === "session_busy";

  return <div className="workspace-wrap workspace-redesign">
    <div className="workspace-head">
      <div className="workspace-identity">
        <InvestorPortrait name={session.investor_display_name} src={investor?.portrait_path} alt={investor?.portrait_alt} className="workspace-portrait" />
        <div>
          <SimulationBadge />
          <div className="eyebrow">{session.investor_display_name}</div>
          <h1>Founder rehearsal</h1>
          <p>{session.disclosure}</p>
        </div>
      </div>
      {complete&&<div className="workspace-actions">
        <span className="verified" title="Evidence links and session-record completeness were checked; founder claims were not independently fact-checked."><ShieldCheck size={16} /> Assessment integrity checked</span>
        <a className="button secondary" href={`/api/sessions/${sessionId}/export`}><Download size={16} /> Export</a>
      </div>}
    </div>
    {processing || (progressStage === "failed" && !session.initial_assessment) ? <AnalysisProgress
      stage={progressStage}
      events={events}
      agentActivity={session.agent_activity}
      startedAt={startedAt}
      recoveryLabel={session.initial_assessment ? "Retry operation" : "Restart assessment"}
      recoveryPending={mutation.isPending}
      onRecover={session.initial_assessment
        ? () => mutation.mutate({ kind: "retry" })
        : () => navigate(`/new/${session.vc_slug}`, { state: { pitchText: session.pitch_text } })}
    /> : <RehearsalExperience
      session={session}
      busy={mutation.isPending || operationActive || Boolean(session.operation_active)}
      stage={stage}
      onAnswer={text => mutation.mutate({ kind: "answer", text })}
      onFinish={() => mutation.mutate({ kind: "finish" })}
      onRetry={() => mutation.mutate({ kind: "retry" })}
      onEvidence={setSelected}
    />}
    {busyConflict
      ? <p className="muted" role="status">This response is already being processed. The page will update automatically.</p>
      : mutation.error && <p className="error">{mutation.error.message}</p>}
    {complete&&<EvidenceDrawer evidence={evidence} onClose={() => setSelected([])} />}
  </div>;
}
