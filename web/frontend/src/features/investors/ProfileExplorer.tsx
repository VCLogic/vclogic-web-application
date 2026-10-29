import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { InvestorPortrait } from "../../components/InvestorPortrait";
import { SimulationBadge } from "../../components/SimulationBadge";
import { DecisionSignature } from "./DecisionSignature";
import { buildDecisionThemes } from "./decisionAtlas";
import { InvestmentMemoryChapter } from "./InvestmentMemoryChapter";
import { InvestmentMemoryLibrary } from "./InvestmentMemoryLibrary";

export function ProfileExplorer() {
  const [referenceOpen, setReferenceOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const { vcSlug = "" } = useParams();
  const [memorySelection, setMemorySelection] = useState({ vcSlug, query: "" });
  const memoryQuery = memorySelection.vcSlug === vcSlug ? memorySelection.query : "";
  const setMemoryQuery = (query: string) => setMemorySelection({ vcSlug, query });
  useEffect(() => {
    setMemorySelection((current) => current.vcSlug === vcSlug ? current : { vcSlug, query: "" });
  }, [vcSlug]);
  const profile = useQuery({
    queryKey: ["profile", vcSlug],
    queryFn: () => api.profile(vcSlug),
    refetchInterval: 30_000,
  });
  const graph = useQuery({
    queryKey: ["profile-graph", vcSlug, profile.data?.investor.memory_version],
    queryFn: () => api.profileGraph(vcSlug),
    enabled: !!profile.data,
    refetchInterval: 30_000,
  });

  if (profile.isPending) return <div className="dark-state">Opening the Investment Memory…</div>;
  if (profile.error || !profile.data) return <p className="error">Unable to load profile.</p>;

  const { investor, sections } = profile.data;
  const themes = buildDecisionThemes(graph.data ?? { nodes: [], edges: [] });
  const rationaleCount = graph.data?.nodes.length;
  return <section className="profile-dossier" aria-labelledby="dossier-title">
    <header className="dossier-masthead">
      <div className="dossier-portrait">
        <InvestorPortrait name={investor.display_name} src={investor.portrait_path} alt={investor.portrait_alt} attribution={investor.photo_attribution} sourceUrl={investor.source_profile_url} showAttribution />
        <div className="dossier-badge"><SimulationBadge /></div>
      </div>
      <div className="dossier-identity">
        <span className="section-index">01 / Profile identity</span>
        <p className="dossier-type">Investor decision dossier</p>
        <p className="dossier-firm">{investor.role} · {investor.firm}</p>
        <h1 id="dossier-title">{investor.display_name}</h1>
        <p className="dossier-summary">{investor.summary || `A source-linked simulation of ${investor.display_name}'s observable investment approach.`}</p>
        <p className="dossier-purpose">A structured account of the questions, evidence, and rationales visible across this investor’s public record.</p>
        <div className="dossier-actions">{investor.start_available ? <Link className="dossier-primary-action" to={`/assess/${vcSlug}`}>Assess your pitch <ArrowRight size={16} /></Link> : <Link className="dossier-primary-action" to="/settings/investors">Review investor settings <ArrowRight size={16}/></Link>}<span>Save, compare, and rehearse from one reusable investor-like assessment. {investor.investor_version_id && <Link to={`/settings/investors/${encodeURIComponent(vcSlug)}/specifications?version=${encodeURIComponent(investor.investor_version_id)}`}>View investor specifications</Link>}</span></div>
        {investor.memory_note && <p>{investor.memory_note} {investor.memory_generated_at && <>Generated {investor.memory_generated_at.slice(0, 10)}.</>}</p>}
        <p className="dossier-disclosure">{investor.disclosure}</p>
      </div>
      <dl className="dossier-ledger" aria-label="Dossier coverage">
        <div><dt>Investment Memory</dt><dd>{sections.length} {sections.length === 1 ? "chapter" : "chapters"}</dd></div>
        {investor.evidence_basis === "wiki" ? <>
          <div><dt>Decision policy</dt><dd>{investor.policy_count ?? "Unavailable"} sections</dd></div>
          <div><dt>Investment theses</dt><dd>{investor.thesis_count ?? "Unavailable"} entries</dd></div>
          <div><dt>Cited evidence</dt><dd>{investor.evidence_count ?? "Unavailable"} excerpts · {investor.source_count ?? "Unavailable"} sources</dd></div>
        </> : <div><dt>Decision taxonomy</dt><dd>{graph.isPending ? "Loading…" : graph.error ? "Unavailable" : `${themes.length} decision ${themes.length === 1 ? "theme" : "themes"}`}</dd></div>}
        <div><dt>{investor.evidence_basis === "wiki" ? "Evidence-backed rationales" : "Observed model"}</dt><dd>{graph.isPending ? "Loading…" : graph.error ? "Unavailable" : `${rationaleCount ?? 0} ${rationaleCount === 1 ? "rationale" : "rationales"}`}</dd></div>
      </dl>
    </header>

    <nav className="dossier-local-nav" aria-label="Dossier contents"><span>Case file</span><a href="#decision-signature-title"><b>02</b> Decision model</a><a href="#investment-memory-title"><b>03</b> Investment Memory</a></nav>
    {graph.isPending && <section className="atlas-status" aria-live="polite">Opening the Decision Signature…</section>}
    {graph.data && <DecisionSignature graph={graph.data} onFindEvidence={setMemoryQuery} />}
    {graph.error && <section className="atlas-status atlas-error" aria-live="polite">
      <span>The Decision Signature is unavailable. The Investment Memory is still available.</span>
      <button type="button" onClick={() => graph.refetch()}>Retry Decision Signature</button>
    </section>}
    {investor.selection_note && <p role="status">{investor.selection_note} <Link to="/settings/investors">Open investor settings</Link></p>}
    <InvestmentMemoryLibrary vcSlug={vcSlug} sections={sections} query={memoryQuery} onQueryChange={setMemoryQuery} />
    {profile.data.reference_graph && <details className="legacy-memory" onToggle={event => setHistoryOpen(event.currentTarget.open)}>
      <summary>Earlier assessment decision patterns</summary>
      {historyOpen && <DecisionSignature graph={profile.data.reference_graph} idPrefix="reference-" onFindEvidence={setMemoryQuery} />}
    </details>}
    {!!profile.data.reference_sections?.length && <details className="legacy-memory" onToggle={event => setReferenceOpen(event.currentTarget.open)}>
      <summary>Earlier LangGraph Investment Memory ({profile.data.reference_sections.length} chapters)</summary>
      <p>{profile.data.reference_note}</p>
      {referenceOpen && profile.data.reference_sections.map(section => <details key={section.section_id}>
        <summary>{section.title}</summary><InvestmentMemoryChapter section={{...section, section_id: `reference/${section.section_id}`}} />
      </details>)}
    </details>}
  </section>;
}
