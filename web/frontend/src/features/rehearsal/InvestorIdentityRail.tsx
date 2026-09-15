import type { Investor } from "../../api/types";
import { DecisionInfluenceSummary } from "../../components/DecisionInfluenceSummary";
import { InvestorPortrait } from "../../components/InvestorPortrait";
import { SimulationBadge } from "../../components/SimulationBadge";

export function InvestorIdentityRail({ investor }: { investor: Investor }) {
  return <aside className="identity-rail">
    <div className="identity-photo">
      <InvestorPortrait name={investor.display_name} src={investor.portrait_path} alt={investor.portrait_alt} />
      <div><SimulationBadge /></div>
    </div>
    <div className="identity-copy">
      <span>{investor.role} · {investor.firm}</span>
      <h2>{investor.display_name}</h2>
      <p>{investor.summary}</p>
    </div>
    <DecisionInfluenceSummary
      dark
      positive={investor.recurring_positive_rationales}
      negative={investor.recurring_negative_rationales}
      unresolved={investor.recurring_unresolved_rationales}
      positiveCounts={investor.recurring_positive_counts}
      negativeCounts={investor.recurring_negative_counts}
      unresolvedCounts={investor.recurring_unresolved_counts}
    />
    <p className="identity-disclosure">{investor.disclosure}</p>
  </aside>;
}
