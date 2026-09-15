import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { InvestorPortrait } from "../../components/InvestorPortrait";
import { SimulationBadge } from "../../components/SimulationBadge";
import { DecisionSignature } from "./DecisionSignature";
import { buildDecisionThemes } from "./decisionAtlas";
import { InvestmentMemoryLibrary } from "./InvestmentMemoryLibrary";

export function ProfileExplorer() {
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
  });
  const graph = useQuery({
    queryKey: ["profile-graph", vcSlug],
    queryFn: () => api.profileGraph(vcSlug),
  });

  if (profile.isPending) return <div className="dark-state">Opening the Investment Memory…</div>;
  if (profile.error || !profile.data) return <p className="error">Unable to load profile.</p>;

  const { investor, sections } = profile.data;
  const themes = buildDecisionThemes(graph.data ?? { nodes: [], edges: [] });
  const rationaleCount = graph.data?.nodes.length ?? 0;
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
        <div className="dossier-actions"><Link className="dossier-primary-action" to={`/assess/${vcSlug}`}>Assess your pitch <ArrowRight size={16} /></Link><span>Save, compare, and rehearse from one reusable investor-like assessment.</span></div>
        <p className="dossier-disclosure">{investor.disclosure}</p>
      </div>
      <dl className="dossier-ledger" aria-label="Dossier coverage"><div><dt>Investment Memory</dt><dd>{sections.length} {sections.length === 1 ? "chapter" : "chapters"}</dd></div><div><dt>Decision taxonomy</dt><dd>{themes.length} decision {themes.length === 1 ? "theme" : "themes"}</dd></div><div><dt>Observed model</dt><dd>{rationaleCount} {rationaleCount === 1 ? "rationale" : "rationales"}</dd></div></dl>
    </header>

    <nav className="dossier-local-nav" aria-label="Dossier contents"><span>Case file</span><a href="#decision-signature-title"><b>02</b> Decision model</a><a href="#investment-memory-title"><b>03</b> Investment Memory</a></nav>
    {graph.isPending && <section className="atlas-status" aria-live="polite">Opening the Decision Signature…</section>}
    {graph.data && <DecisionSignature graph={graph.data} onFindEvidence={setMemoryQuery} />}
    {graph.error && <section className="atlas-status atlas-error" aria-live="polite">
      <span>The Decision Signature is unavailable. The Investment Memory is still available.</span>
      <button type="button" onClick={() => graph.refetch()}>Retry Decision Signature</button>
    </section>}
    <InvestmentMemoryLibrary vcSlug={vcSlug} sections={sections} query={memoryQuery} onQueryChange={setMemoryQuery} />
  </section>;
}
