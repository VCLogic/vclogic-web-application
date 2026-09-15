import { useQuery } from "@tanstack/react-query";
import { type ChangeEvent, useState } from "react";
import { FileText, LockKeyhole, Upload } from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { ProcessStepper } from "../../components/ProcessStepper";
import { InvestorIdentityRail } from "./InvestorIdentityRail";
import "./intake.css";

const STEPS = [
  { id: "phase1", label: "Rationale analysis" },
  { id: "phase2", label: "Investment Decision Synthesis" },
  { id: "rehearsal", label: "Interactive rehearsal" },
];

interface RestartState { pitchText?: string }

export function PitchIntake() {
  const { vcSlug = "" } = useParams();
  const navigate = useNavigate();
  const recovered = useLocation().state as RestartState | null;
  const { data } = useQuery({ queryKey: ["profile", vcSlug], queryFn: () => api.profile(vcSlug) });
  const [company, setCompany] = useState("");
  const [pitch, setPitch] = useState(recovered?.pitchText || "");
  const [authorized, setAuthorized] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function file(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0];
    if (!selected) return;
    if (!/\.(txt|md)$/i.test(selected.name)) {
      setError("Upload a UTF-8 .txt or .md file.");
      return;
    }
    const text = (await selected.text()).replace(/\r\n?/g, "\n");
    if (text.length > 200000) {
      setError("Pitch exceeds the 200,000 character limit.");
      return;
    }
    setPitch(text);
    setError("");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!company.trim() || !pitch.trim() || !authorized) return;
    setBusy(true);
    setError("");
    try {
      const project = await api.createProject({
        display_name: company.split(",")[0].trim(),
        company_aliases: company.split(",").map(value => value.trim()).filter(Boolean),
        pitch_text: pitch,
      });
      await api.startAssessment(project.project_id, project.current_version_id, vcSlug);
      navigate(`/pitches/${project.project_id}/versions/${project.current_version_id}?tab=assessments`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start assessment");
      setBusy(false);
    }
  }

  return <section className="intake-page">
    <div className="intake-title">
      <span className="eyebrow">New founder rehearsal</span>
      <h1>Bring the pitch you would give in the room.</h1>
      <p>The system saves this pitch, builds a reusable investor-like assessment, then lets you begin one or more rehearsals from that baseline.</p>
    </div>
    <div className="intake-steps"><ProcessStepper steps={STEPS} current="phase1" /></div>
    <div className="intake-layout">
      {data?.investor ? <InvestorIdentityRail investor={data.investor} /> : <aside className="identity-rail loading">Loading investor profile…</aside>}
      <form className="intake-form" onSubmit={submit}>
        <div className="briefing-label"><FileText size={18} /><div><strong>Founder briefing</strong><span>Your pitch becomes immutable after submission.</span></div></div>
        {recovered?.pitchText && <p className="recovery-note">Pitch restored from the failed assessment. Confirm the company name and provider-cost authorization before restarting.</p>}
        <label>Company name or aliases<input value={company} onChange={event => setCompany(event.target.value)} placeholder="Acme, Acme AI" required /></label>
        <label>Pitch text<textarea value={pitch} onChange={event => setPitch(event.target.value.slice(0, 200000))} rows={16} placeholder="Paste the pitch exactly as the investor would receive it…" required /></label>
        <div className="upload"><label className="upload-button" htmlFor="pitch-file"><Upload size={15} /> Upload .txt or .md</label><input id="pitch-file" type="file" accept=".txt,.md,text/plain,text/markdown" onChange={file} /><span>{pitch.length.toLocaleString()} / 200,000 characters</span></div>
        <p className="recovery-note">Rehearsal can start from the saved assessment as soon as it completes. You can choose Quick, Standard, or Deep then—and repeat the conversation without rerunning the assessment.</p>
        <div className="privacy-note"><LockKeyhole size={17} /><p>The pitch is stored locally as a verified artifact. Credentials, hidden reasoning, and raw provider responses are not exposed in the interface.</p></div>
        <label className="authorization"><input type="checkbox" checked={authorized} onChange={event => setAuthorized(event.target.checked)} /><span><strong>Authorize provider API costs</strong> for the canonical assessment.</span></label>
        {error && <p className="error">{error}</p>}
        <button className="button intake-submit" disabled={busy || !authorized || !pitch.trim() || !company.trim()}>{busy ? "Starting assessment…" : "Begin investor assessment"}</button>
      </form>
    </div>
  </section>;
}
