import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import type { DecisionPath as DecisionPathRow, LikelihoodTimeline as TimelineRow } from "../../api/types";
import { DecisionPath } from "./DecisionPath";
import { LikelihoodTimeline } from "./LikelihoodTimeline";

const paths: DecisionPathRow[] = [
  { path_id: "p1", evidence_id: "pitch-1", evidence_origin: "pitch", evidence_excerpt: "Eight agencies currently pay for the product.", rationale_id: "traction", rationale_label: "traction_validation", direction: "positive", contribution: "Early willingness to pay supports adoption.", baseline_or_rehearsal: "baseline", supporting_evidence_ids: ["wiki-1"] },
  { path_id: "p1b", evidence_id: "pitch-2", evidence_origin: "pitch", evidence_excerpt: "Customers processed 41,000 assignments.", rationale_id: "traction", rationale_label: "traction_validation", direction: "positive", contribution: "Early willingness to pay supports adoption.", baseline_or_rehearsal: "baseline", supporting_evidence_ids: ["wiki-1"] },
  { path_id: "p1c", evidence_id: "answer-2", evidence_origin: "founder_answer", evidence_excerpt: "Three customers expanded their usage.", rationale_id: "traction", rationale_label: "traction_validation", direction: "positive", contribution: "Early willingness to pay supports adoption.", baseline_or_rehearsal: "rehearsal", supporting_evidence_ids: ["wiki-1"] },
  { path_id: "p2", evidence_id: "answer-1", evidence_origin: "founder_answer", evidence_excerpt: "We cannot yet separate outbound conversions.", rationale_id: "repeatability", rationale_label: "traction_repeatability_concern", direction: "negative", contribution: "The acquisition motion remains unproven.", baseline_or_rehearsal: "rehearsal", supporting_evidence_ids: ["precedent-1"] },
];
const timeline: TimelineRow[] = [
  { turn: 0, label: "Initial assessment", evidence_effect: "baseline", before: .28, after: .28, delta: 0 },
  { turn: 1, label: "Response 1", evidence_effect: "clarification", before: .28, after: .28, delta: 0, answer_excerpt: "The wedge is replacement coordination." },
  { turn: 2, label: "Response 2", evidence_effect: "new_negative", before: .28, after: .22, delta: -.06, answer_excerpt: "ROI is not verified." },
  { turn: 3, label: "Final synthesis", evidence_effect: "synthesis", before: .22, after: .24, delta: .02 },
];

it("renders an auditable evidence-to-rationale decision path", async () => {
  const user = userEvent.setup(); const onEvidence = vi.fn();
  render(<DecisionPath rows={paths} finalDecision="Out" onEvidence={onEvidence} />);
  expect(screen.getByRole("heading", { name: "Decision Path" })).toBeVisible();
  const pitch = screen.getByRole("article", { name: /Traction validation decision path/i });
  expect(pitch).toHaveTextContent("Creates conviction");
  expect(within(pitch).getAllByText("Early willingness to pay supports adoption.")).toHaveLength(1);
  expect(within(pitch).getAllByRole("listitem")).toHaveLength(3);
  expect(screen.getAllByText(/Final assessment:/)).toHaveLength(1);
  await user.click(within(pitch).getByRole("button", { name: /inspect supporting evidence for eight agencies/i }));
  expect(onEvidence).toHaveBeenCalledWith(["pitch-1", "wiki-1"]);
});

it("shows an estimated-fit timeline where clarification stays flat", () => {
  render(<LikelihoodTimeline rows={timeline} />);
  expect(screen.getByRole("heading", { name: "Estimated fit over the rehearsal" })).toBeVisible();
  expect(screen.getByRole("listitem", { name: /Response 1.*Clarification.*28\/100 to 28\/100.*no change/i })).toBeVisible();
  expect(screen.getByRole("listitem", { name: /Response 2.*New concern.*28\/100 to 22\/100.*down 6 points/i })).toBeVisible();
  expect(screen.getByRole("listitem", { name: /Final synthesis.*Final decision synthesis.*22\/100 to 24\/100.*up 2 points/i })).toBeVisible();
});

it("handles a completed legacy session without path artifacts", () => {
  render(<><DecisionPath rows={[]} finalDecision="Out" onEvidence={vi.fn()} /><LikelihoodTimeline rows={[]} /></>);
  expect(screen.getByText(/No evidence path is available/i)).toBeVisible();
  expect(screen.getByText(/No rehearsal fit history is available/i)).toBeVisible();
});
