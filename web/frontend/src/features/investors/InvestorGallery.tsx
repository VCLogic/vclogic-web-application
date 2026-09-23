import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, FolderClock } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { DecisionInfluenceSummary } from "../../components/DecisionInfluenceSummary";
import { InvestorPortrait } from "../../components/InvestorPortrait";
import { SimulationBadge } from "../../components/SimulationBadge";
import "./investors.css";

export function InvestorGallery() {
  const { data, isPending, error } = useQuery({ queryKey: ["investors"], queryFn: api.investors, refetchInterval: 30_000 });
  const [selectedSlug, setSelectedSlug] = useState("");
  useEffect(() => {
    if (!selectedSlug && data?.investors[0]) setSelectedSlug(data.investors[0].vc_slug);
  }, [data, selectedSlug]);
  if (isPending) return <div className="dark-state">Preparing investor profiles…</div>;
  if (error) return <p className="error">Unable to load profiles: {error.message}</p>;
  const selected = data?.investors.find(investor => investor.vc_slug === selectedSlug) ?? data?.investors[0];
  const hasDecisionInfluences = selected && [selected.recurring_positive_rationales, selected.recurring_negative_rationales, selected.recurring_unresolved_rationales].some(items => items?.length);

  return <section className="investor-selection">
    <div className="selection-hero">
      <div className="selection-copy">
        <span className="eyebrow">Investor decision register · 01</span>
        <h1>See your company through a different investment lens</h1>
        <p>Rehearse with source-linked investor simulations. Learn which signals create conviction, which concerns remain, and what evidence could change the decision.</p>
        <div className="hero-actions">
          <a href="#investors" className="button light">Choose an investor <ArrowRight size={17} /></a>
          <Link to="/sessions" className="text-link"><FolderClock size={17} /> Continue a rehearsal</Link>
        </div>
      </div>
      <aside className="hero-note"><b>Not a generic pitch score</b><p>Each profile is reconstructed from public theses, interviews, portfolio patterns, constraints, and observed rationales.</p><div><span>01</span> Inspect the decision model</div><div><span>02</span> Submit a pitch privately</div><div><span>03</span> Rehearse the open questions</div></aside>
    </div>
    <div className="gallery-heading" id="investors"><div><span className="eyebrow">Available profiles</span><h2>Choose whose questions you want to face</h2></div><p>Auditable simulations—not the real investors and not endorsed by them.</p></div>
    {!data?.investors.length && <div className="dark-state"><h2>No investors are available yet</h2><p>Enable a ready investor version in Settings to start an assessment.</p><Link className="button light" to="/settings/investors">Open investor settings</Link></div>}
    <div className="investor-register">
      <nav className="investor-register-list" aria-label="Investor profiles">
        {data?.investors.map((investor, index) => <button key={investor.vc_slug} type="button" aria-current={selected?.vc_slug === investor.vc_slug ? "true" : undefined} onClick={() => setSelectedSlug(investor.vc_slug)}>
          <span className="register-number">{String(index + 1).padStart(2, "0")}</span><span><b>{investor.display_name}</b><small>{investor.firm}</small></span><ArrowRight size={15}/>
        </button>)}
      </nav>
      {selected && <article className="investor-preview" aria-live="polite">
        <div className="preview-portrait"><InvestorPortrait name={selected.display_name} src={selected.portrait_path} alt={selected.portrait_alt}/><div className="portrait-badge"><SimulationBadge/></div></div>
        <div className="preview-body">
          <p className="preview-kicker">{selected.role} · {selected.firm}</p><h3>{selected.display_name}</h3>
          <p className="investor-summary">{selected.summary || "A source-linked representation of this investor’s observable investment approach."}</p>
          {hasDecisionInfluences && <div className="investor-influences"><h4>Frequently observed rationales</h4><p className="recurrence-note">Bar length shows frequency in the available record, not causal importance.</p>
            <DecisionInfluenceSummary
              dark
              positive={selected.recurring_positive_rationales} negative={selected.recurring_negative_rationales} unresolved={selected.recurring_unresolved_rationales}
              positiveCounts={selected.recurring_positive_counts} negativeCounts={selected.recurring_negative_counts} unresolvedCounts={selected.recurring_unresolved_counts}
            />
          </div>}
          <div className="card-actions"><Link className="button light" to={`/assess/${selected.vc_slug}`}>Assess your pitch <ArrowRight size={16}/></Link><Link className="profile-link" to={`/profiles/${selected.vc_slug}`}><BookOpen size={15}/> Explore decision dossier</Link></div>
        </div>
      </article>}
    </div>
  </section>;
}
