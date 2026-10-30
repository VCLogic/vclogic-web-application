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
  const { data, isPending, error } = useQuery({ queryKey: ["investor-gallery"], queryFn: api.investorsForGallery, refetchInterval: 30_000 });
  const [selectedSlug, setSelectedSlug] = useState("");
  useEffect(() => {
    if (!selectedSlug && data?.investors[0]) setSelectedSlug(data.investors[0].vc_slug);
  }, [data, selectedSlug]);
  if (isPending) return <div className="dark-state">Preparing investor profiles…</div>;
  if (error) return <p className="error">Unable to load profiles: {error.message}</p>;
  const selected = data?.investors.find(investor => investor.vc_slug === selectedSlug) ?? data?.investors[0];

  return <section className="investor-selection">
    <div className="selection-hero">
      <div className="selection-copy">
        <span className="eyebrow">Investor decision register · 01</span>
        <h1>See your company through a different investment lens</h1>
        <p>Rehearse with source-linked investor simulations. Learn which signals create conviction, which concerns remain, and what evidence could change the decision.</p>
        <div className="hero-actions">
          <a href="#investors" className="button light">Choose an investor <ArrowRight size={17} /></a>
          <Link to="/sessions" className="text-link"><FolderClock size={17} /> Continue a rehearsal</Link>
          <a href="/pitches" className="text-link">Explore saved pitches <ArrowRight size={17}/></a>
        </div>
      </div>
      <aside className="hero-note"><b>Not a generic pitch score</b><p>Each profile is reconstructed from public theses, interviews, portfolio patterns, constraints, and observed rationales.</p><div><span>01</span> Inspect the decision model</div><div><span>02</span> Submit a pitch privately</div><div><span>03</span> Rehearse the open questions</div></aside>
    </div>
    <div className="gallery-heading" id="investors"><div><span className="eyebrow">Available profiles</span><h2>Choose whose questions you want to face</h2></div></div>
    {!data?.investors.length && <div className="dark-state"><h2>No investors are available yet</h2><p>Enable a ready investor version in Settings to start an assessment.</p><Link className="button light" to="/settings/investors">Open investor settings</Link></div>}
    <div className="investor-register">
      <nav className="investor-register-list" aria-label="Investor profiles" tabIndex={0}>
        {data?.investors.map((investor, index) => <button key={investor.vc_slug} type="button" aria-current={selected?.vc_slug === investor.vc_slug ? "true" : undefined} onClick={() => setSelectedSlug(investor.vc_slug)}>
          <span className="register-number">{String(index + 1).padStart(2, "0")}</span><span><b>{investor.display_name}</b><small>{investor.firm}</small></span><ArrowRight size={15}/>
        </button>)}
      </nav>
      {selected && <article className="investor-preview" aria-live="polite">
        <div className="preview-portrait"><InvestorPortrait name={selected.display_name} src={selected.portrait_path} alt={selected.portrait_alt}/><div className="portrait-badge"><SimulationBadge/></div></div>
        <div className="preview-details">
          {data?.investors.map(investor => {
            const hasDecisionInfluences = [investor.recurring_positive_rationales, investor.recurring_negative_rationales, investor.recurring_unresolved_rationales].some(items => items?.length);
            return (
        <div key={investor.vc_slug} className="preview-body" inert={investor.vc_slug !== selected.vc_slug} aria-hidden={investor.vc_slug !== selected.vc_slug} role="region" aria-label="Selected investor details">
          <p className="preview-kicker">{investor.role} · {investor.firm}</p><h3>{investor.display_name}</h3>
          {investor.selection_note && <p role="status">{investor.selection_note}</p>}
          <p className="investor-summary">{investor.summary || "A source-linked representation of this investor’s observable investment approach."}</p>
          {hasDecisionInfluences && <div className="investor-influences"><h4>{investor.evidence_basis === "wiki" ? "Rationales in the current wiki" : "Frequently observed rationales"}</h4><p className="recurrence-note">{investor.evidence_basis === "wiki" ? "Bar length shows evidence-excerpt frequency, not investment decisions or causal importance." : "Bar length shows frequency in the available record, not causal importance."}</p>
            {investor.evidence_note && <p className="recurrence-note">{investor.evidence_note}</p>}
            <DecisionInfluenceSummary
              dark
              positive={investor.recurring_positive_rationales} negative={investor.recurring_negative_rationales} unresolved={investor.recurring_unresolved_rationales}
              positiveCounts={investor.recurring_positive_counts} negativeCounts={investor.recurring_negative_counts} unresolvedCounts={investor.recurring_unresolved_counts}
            />
          </div>}
          {!hasDecisionInfluences && investor.evidence_note && <p className="recurrence-note">{investor.evidence_note}</p>}
          <div className="card-actions">{investor.start_available ? <Link className="button light" to={`/assess/${investor.vc_slug}`}>Assess your pitch <ArrowRight size={16}/></Link> : <Link className="button light" to="/settings/investors">Choose active version <ArrowRight size={16}/></Link>}<Link className="profile-link" to={`/profiles/${investor.vc_slug}`}><BookOpen size={15}/> Explore decision dossier</Link></div>
        </div>);
          })}
        </div>
      </article>}
    </div>
  </section>;
}
