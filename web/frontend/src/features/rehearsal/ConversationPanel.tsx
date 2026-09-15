import { useEffect, useState } from "react";
import { ArrowUp, CheckCircle2, LoaderCircle, MessageSquareText } from "lucide-react";
import type { Session } from "../../api/types";
import { SafeMarkdown } from "../../components/SafeMarkdown";

type PendingExchange = { text: string; questionId: string; digest?: string };

const stageMessage: Record<string, string> = {
  queued: "Submitting your evidence…",
  rehearsal_running: "Preparing to review your evidence…",
  answer_update_running: "Reviewing your evidence against the active rationales…",
  continuation_running: "Deciding whether another question could change the assessment…",
  question_selection_running: "Selecting the next investor-style question…",
  decision_synthesis_running: "Synthesizing the investment decision…",
  founder_feedback_running: "Preparing founder feedback…",
  complete: "Finalizing the response…",
};

function turnText(turn: Record<string, unknown>): string {
  return String(turn.text_verbatim || turn.text || turn.answer || "");
}

function humanize(label: string): string {
  const text = label.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const DEPTH_LABELS = { quick: "Quick", standard: "Standard", deep: "Deep" } as const;

async function answerDigest(text: string): Promise<string | undefined> {
  if (!globalThis.crypto?.subtle) return undefined;
  const bytes = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, "0")).join("");
}

function closingMessage(message?: string | null): string {
  if (!message || /(?:end|reached).{0,24}(?:available )?questions/i.test(message)) {
    return "Further questioning is unlikely to materially change this assessment. Remaining uncertainties require evidence or milestones rather than another explanation.";
  }
  return message;
}

export function ConversationPanel({
  session, busy, activityStage = "awaiting_answer", onAnswer, onFinish, onRetry, hidden = false,
}: {
  session: Session; busy: boolean; activityStage?: string; onAnswer: (text: string) => void;
  onFinish: () => void; onRetry: () => void; hidden?: boolean;
}) {
  const [text, setText] = useState("");
  const [pending, setPending] = useState<PendingExchange | null>(null);
  const failed = activityStage === "failed";
  const acknowledged = pending ? (session.conversation || []).find(turn => turn.question_id === pending.questionId && Boolean(turn.founder_answer)) : undefined;
  const digestMismatch = Boolean(pending?.digest && acknowledged?.answer_sha256 && pending.digest !== acknowledged.answer_sha256);

  useEffect(() => {
    if (!pending) return;
    const answerAccepted = (session.conversation || []).some(turn => {
      if (turn.question_id !== pending.questionId || !turn.founder_answer) return false;
      if (turn.answer_sha256) return Boolean(pending.digest && turn.answer_sha256 === pending.digest);
      return turn.founder_answer === pending.text;
    });
    if (answerAccepted || session.status === "complete" || session.status === "finished") setPending(null);
  }, [pending, session.conversation, session.status]);

  const submit = async () => {
    const submitted = text.trim();
    if (!submitted || pending || !session.active_question) return;
    const questionId = session.active_question.question_id;
    setPending({ text: submitted, questionId });
    setText("");
    const digest = await answerDigest(submitted);
    setPending(current => current?.questionId === questionId && current.text === submitted ? { ...current, digest } : current);
    onAnswer(submitted);
  };

  const locked = busy || pending !== null;
  const progress = pending && activityStage === "awaiting_answer"
    ? stageMessage.queued
    : stageMessage[activityStage] || "Reviewing your evidence…";

  const transcript = (session.conversation || []).filter(turn => !(digestMismatch && turn.question_id === pending?.questionId));
  const acceptedCount = transcript.filter(turn => Boolean(turn.founder_answer)).length;
  const currentTurn = Math.min(acceptedCount + (session.active_question ? 1 : 0), session.max_questions || 5);
  const depth = DEPTH_LABELS[session.rehearsal_depth || "standard"];

  return <section id="workspace-conversation" role="tabpanel" hidden={hidden} className="panel conversation chat-conversation">
    <header><div><span className="eyebrow">Founder rehearsal</span><h2>Conversation</h2></div><MessageSquareText size={18}/></header>
    <div className="turns">
      {transcript.length ? transcript.map((turn,index)=><div className="chat-exchange" key={turn.question_id}>
        <article className="investor-message" aria-label={`Investor question ${index+1}`}>
          {turn.response_comment&&<SafeMarkdown className="investor-comment">{turn.response_comment}</SafeMarkdown>}
          <SafeMarkdown className="investor-question">{turn.question}</SafeMarkdown>
          {turn.rationale_labels.length>0&&<div className="question-rationales" aria-label="Relevant investment rationales">{turn.rationale_labels.map(label=><span key={label}>{humanize(label)}</span>)}</div>}
        </article>
        {turn.founder_answer&&<article className="answer"><span><CheckCircle2 size={12}/> You · Response {index+1}</span><SafeMarkdown>{turn.founder_answer}</SafeMarkdown></article>}
      </div>) : session.turns.map((turn,index)=><article className="answer" key={String(turn.answer_id||index)}><span><CheckCircle2 size={12}/> You · Response {index+1}</span><SafeMarkdown>{turnText(turn)}</SafeMarkdown></article>)}
      {session.active_question?<article className="investor-message current-investor-message">
        <div className="question-number">Question {currentTurn} · {depth} rehearsal</div>
        {session.active_question.response_comment&&<SafeMarkdown className="investor-comment">{session.active_question.response_comment}</SafeMarkdown>}
        <SafeMarkdown className="investor-question">{session.active_question.text}</SafeMarkdown>
        <div className="question-rationales" aria-label="Relevant investment rationales">{session.active_question.rationale_labels.map(label=><span key={label}>{humanize(label)}</span>)}</div>
        <label className="answer-field">Your evidence<textarea aria-label="Your answer" rows={6} value={text} disabled={locked} onChange={event=>setText(event.target.value)} placeholder={pending?"Your evidence is being reviewed…":"Answer with the evidence you would give in the room…"}/></label>
        <p className="unverified-note">Your response is treated as unverified founder-provided evidence until independently checked.</p>
        <div className="conversation-actions"><button className="button" disabled={locked||!text.trim()} onClick={submit}>Submit evidence <ArrowUp size={14}/></button><button className="button secondary" disabled={locked||acceptedCount<1} onClick={onFinish}>Finish and assess now</button></div>
      </article>:session.status==="finished"||session.status==="complete"?<div className="complete-note"><CheckCircle2/><h3>Rehearsal complete</h3><p>{closingMessage(session.closing_message)}</p></div>:session.status==="failed"?<div className="error"><p>The last provider operation was interrupted.</p><button className="button secondary" onClick={onRetry}>Retry safely</button></div>:<p className="muted">The next question will appear when analysis completes.</p>}
      {pending&&<><article className="answer pending-answer"><span>Founder-provided evidence · Sending</span><p>{pending.text}</p></article>{digestMismatch?<div className="chat-failure" role="alert"><p>The system could not verify the returned answer against the evidence you submitted. Your exact text is preserved.</p><button className="button secondary" onClick={onRetry}>Retry verification</button></div>:failed?<div className="chat-failure" role="alert"><p>The investor simulation could not finish reviewing this response. Your evidence is preserved.</p><button className="button secondary" onClick={onRetry}>Retry review</button></div>:<div className="investor-typing" role="status" aria-live="polite"><LoaderCircle className="typing-spinner" size={17}/><span>{progress}</span></div>}</>}
    </div>
  </section>;
}
