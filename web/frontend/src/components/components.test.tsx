import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { Graph, Profile } from "../api/types";
import { DecisionGauge } from "./DecisionGauge";
import { DecisionInfluenceSummary } from "./DecisionInfluenceSummary";
import { InvestorPortrait } from "./InvestorPortrait";
import { ProcessStepper } from "./ProcessStepper";
import { RationaleFingerprint } from "./RationaleFingerprint";
import { ScoreTrajectory } from "./ScoreTrajectory";
import { AppShell } from "./AppShell";
import { CaseIndex } from "./CaseIndex";
import { decisionLean } from "./AssessmentSemantics";

describe("shared visual components", () => {
  it("provides an accessible dossier shell and route index", () => {
    render(<MemoryRouter initialEntries={["/sessions"]}><AppShell><CaseIndex label="Case file" items={[{id:"conversation",label:"Conversation"},{id:"assessment",label:"Assessment"}]} active="conversation" onChange={()=>{}}/><h1 id="content-title">Case content</h1></AppShell></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    const home = screen.getByRole("link", { name: "InvestorLens home" });
    expect(home).toHaveAttribute("href", "/");
    const mark = home.querySelector("svg.investor-lens-mark");
    expect(mark).not.toBeNull();
    expect(mark).toHaveAttribute("aria-hidden", "true");
    expect(mark).not.toHaveAttribute("role", "img");
    expect(screen.getByRole("link", { name: "Rehearsals" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("navigation", { name: "Case file" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Conversation" })).toHaveAttribute("aria-current", "page");
  });
  it("accepts null profile statistics emitted by the API", () => {
    const profile = { investor: {} as Profile["investor"], sections: [{ section_id:"thesis", title:"Thesis", body:"", source_paths:[], preview:null, character_count:null }] } satisfies Profile;
    const graph = { nodes: [{ node_id:"n1", taxonomy_label:"founder_conviction", title:"Founder conviction", direction:"positive", salience:"high", confidence:1, evidence_ids:[], initial_direction:null, initial_confidence:null, definition:null, coarse_parent:null, occurrence_count:null, investigation_count:null, direction_counts:null, weighted_degree:null }], edges: [{ edge_id:"e1", source:"n1", target:"n2", relationship:"supports", inference_status:"observed", evidence_ids:[], occurrence_count:null }] } satisfies Graph;

    expect(profile.sections[0].preview).toBeNull();
    expect(graph.nodes[0].weighted_degree).toBeNull();
    expect(graph.edges[0].occurrence_count).toBeNull();
  });

  it("falls back to initials and preserves attribution", () => {
    render(<InvestorPortrait name="Charles Hudson-like Investor" src="/missing.jpg"
      alt="Charles Hudson portrait" attribution="Photo: The Pitch"
      sourceUrl="https://www.thepitch.show/investors/charles-hudson-precursor-ventures"
      showAttribution />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByText("CH")).toBeVisible();
    expect(screen.getByRole("link", { name: /photo: the pitch/i })).toHaveAttribute("href", expect.stringContaining("thepitch.show"));
  });

  it("labels fingerprint context and directions", () => {
    render(<RationaleFingerprint context="Stable investor tendencies"
      positive={["founder_conviction"]} negative={["portfolio_conflict"]}
      unresolved={["market_size_assessment"]} />);
    expect(screen.getByText("Stable investor tendencies")).toBeVisible();
    expect(screen.getByText("Creates conviction")).toBeVisible();
    expect(screen.getByText("Creates concern")).toBeVisible();
    expect(screen.getByText("Conditional / unresolved")).toBeVisible();
  });

  it("shows one dominant rationale for each populated decision influence", () => {
    render(<DecisionInfluenceSummary
      positive={["founder_conviction", "ignored_positive"]}
      negative={["portfolio_conflict", "ignored_negative"]}
      unresolved={["market_size_assessment", "ignored_unresolved"]}
      positiveCounts={{ founder_conviction: 10, ignored_positive: 100 }}
      negativeCounts={{ portfolio_conflict: 5, ignored_negative: 100 }}
      unresolvedCounts={{ market_size_assessment: 2, ignored_unresolved: 100 }}
    />);

    const summary = screen.getByRole("region", { name: "Frequently observed rationales" });
    expect(summary).toBeVisible();
    expect(within(summary).getByText("Creates conviction")).toBeVisible();
    expect(within(summary).getByText("Creates concern")).toBeVisible();
    expect(within(summary).getByText("Mixed / conditional")).toBeVisible();
    expect(within(summary).getByText("Founder Conviction")).toBeVisible();
    expect(within(summary).getByText("Portfolio Conflict")).toBeVisible();
    expect(within(summary).getByText("Market Size Assessment")).toBeVisible();
    expect(within(summary).queryByText(/ignored/i)).not.toBeInTheDocument();
    const positiveRow = within(summary).getByText("Creates conviction").closest(".decision-influence-row");
    const negativeRow = within(summary).getByText("Creates concern").closest(".decision-influence-row");
    const unresolvedRow = within(summary).getByText("Mixed / conditional").closest(".decision-influence-row");
    expect(positiveRow).toHaveClass("positive");
    expect(positiveRow?.nextElementSibling).toBe(negativeRow);
    expect(negativeRow).toHaveClass("negative");
    expect(negativeRow?.nextElementSibling).toBe(unresolvedRow);
    expect(unresolvedRow).toHaveClass("unresolved");
    expect(summary.querySelectorAll("svg")).toHaveLength(3);
    summary.querySelectorAll("svg").forEach(icon => {
      expect(icon).toHaveAttribute("aria-hidden", "true");
    });
    const meters = within(summary).getAllByRole("meter");
    expect(meters).toHaveLength(3);
    expect(meters.map(meter => meter.getAttribute("aria-valuenow"))).toEqual(["100", "50", "20"]);
    expect(meters.map(meter => meter.getAttribute("aria-valuetext"))).toEqual([
      "10 observed activations; 100% of displayed maximum.",
      "5 observed activations; 50% of displayed maximum.",
      "2 observed activations; 20% of displayed maximum.",
    ]);
    meters.forEach(meter => {
      expect(meter).toHaveAttribute("aria-valuemin", "0");
      expect(meter).toHaveAttribute("aria-valuemax", "100");
      expect(meter).toHaveAccessibleName(/observed recurrence frequency, not confidence or importance/i);
    });
  });

  it("does not report false zero recurrence for missing, null, or invalid legacy counts", () => {
    const { container } = render(<DecisionInfluenceSummary
      positive={["founder_conviction"]}
      negative={["portfolio_conflict"]}
      unresolved={["market_size_assessment"]}
      negativeCounts={null}
      unresolvedCounts={{ market_size_assessment: Number.NaN }}
    />);

    expect(within(container).queryAllByRole("meter")).toHaveLength(0);
    expect(within(container).queryByText(/0 observed activations/i)).not.toBeInTheDocument();
    expect(within(container).getByText("Founder Conviction")).toHaveAccessibleName(/observed recurrence unavailable/i);
    expect(within(container).getByText("Portfolio Conflict")).toHaveAccessibleName(/observed recurrence unavailable/i);
    expect(within(container).getByText("Market Size Assessment")).toHaveAccessibleName(/observed recurrence unavailable/i);
  });

  it("exposes an explicit dark-context styling contract", () => {
    render(<DecisionInfluenceSummary dark positive={["founder_conviction"]} />);

    const summary = screen.getAllByRole("region", { name: "Frequently observed rationales" }).at(-1);
    expect(summary).toHaveClass("decision-influence-summary--dark");
  });

  it("omits empty directions without rendering placeholders", () => {
    const { rerender } = render(<DecisionInfluenceSummary negative={["portfolio_conflict"]} />);
    const summary = screen.getAllByRole("region", { name: "Frequently observed rationales" }).at(-1)!;

    expect(within(summary).queryByText("Creates conviction")).not.toBeInTheDocument();
    expect(within(summary).getByText("Creates concern")).toBeVisible();
    expect(within(summary).queryByText("Mixed / conditional")).not.toBeInTheDocument();
    expect(within(summary).queryByText(/not documented/i)).not.toBeInTheDocument();

    rerender(<DecisionInfluenceSummary />);
    expect(summary).not.toBeInTheDocument();
  });

  it("announces founder-safe fit semantics and score movement", () => {
    render(<><ProcessStepper current="phase2" steps={[{id:"phase1",label:"Rationale analysis"},{id:"phase2",label:"Decision synthesis"}]}/><DecisionGauge value={0.62}/><ScoreTrajectory initial={0.4} current={0.52}/></>);
    expect(decisionLean("In")).toBe("Leans In");
    expect(decisionLean("Out")).toBe("Leans Out");
    expect(screen.getByText("Decision synthesis").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByLabelText("Estimated investor fit, 62 out of 100")).toBeVisible();
    expect(screen.getByLabelText("Estimated investor fit moved from 40 to 52 out of 100")).toBeVisible();
    expect(screen.getByText("+12 points")).toBeVisible();
  });
});
