import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { ProgressEvent } from "../../api/events";
import type { AgentActivity } from "../../api/types";
import { AnalysisProgress } from "./AnalysisProgress";

const events: ProgressEvent[] = [
  { event_id: 1, session_id: "session", stage: "queued", payload: { operation: "start" } },
  { event_id: 2, session_id: "session", stage: "preparing_inputs", payload: { vc_slug: "charles" } },
  { event_id: 3, session_id: "session", stage: "phase1_running", payload: { message: "Building canonical rationale baseline" } },
];
const agentActivity: AgentActivity[] = [{
  activity_id: "phase1-turn-01-plan",
  phase: "phase1",
  iteration: 1,
  kind: "plan",
  status: "complete",
  title: "Phase1 agent plan",
  text: "Test whether retention changes the decision.",
  details: ["Question: What is cohort retention?", "Memory search: retention hard rules"],
  elapsed_seconds: 1.25,
}];

afterEach(cleanup);

it("shows the active assessment stage and concrete event history", () => {
  render(<AnalysisProgress stage="phase1_running" events={events} agentActivity={agentActivity} startedAt={Date.now() - 65_000} />);

  expect(within(screen.getByRole("list", { name: "Assessment progress" })).getByText("Rationale analysis").closest("li")).toHaveAttribute("aria-current", "step");
  expect(screen.getByText("Mapping pitch evidence to decision rationales")).toBeVisible();
  expect(screen.getByRole("progressbar", { name: "Assessment activity" })).not.toHaveAttribute("aria-valuenow");
  expect(screen.getByText(/Elapsed 1m/)).toBeVisible();
  expect(screen.getByText("Job accepted")).toBeVisible();
  expect(screen.getByText("Pitch stored; preparing leakage-safe inputs")).toBeVisible();
  expect(screen.getByText("Building canonical rationale baseline")).toBeVisible();
  expect(screen.getByText(/retrieving relevant precedents/i)).toBeVisible();
  expect(screen.getByRole("region", { name: "Agent responses" })).toBeVisible();
  expect(screen.getByText("Test whether retention changes the decision.")).toBeVisible();
  expect(screen.getByText("Question: What is cohort retention?")).toBeVisible();
  expect(screen.getByText(/Structured outputs only/i)).toBeVisible();
  expect(screen.queryByText("Working through the configured model provider")).not.toBeInTheDocument();
});

it("replaces activity animation with the public terminal error", () => {
  const failed = [...events, {
    event_id: 4,
    session_id: "session",
    stage: "failed",
    payload: { message: "missing required credential: OPENROUTER_API_KEY", recoverable: true },
  } satisfies ProgressEvent];

  render(<AnalysisProgress stage="failed" events={failed} startedAt={Date.now() - 5_000} />);

  expect(screen.getByRole("heading", { name: "Assessment needs attention" })).toBeVisible();
  expect(screen.getByRole("alert")).toHaveTextContent("missing required credential: OPENROUTER_API_KEY");
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.getByText(/No model result was produced/i)).toBeVisible();
});

it("offers the supplied recovery action after a failed run", async () => {
  const user = userEvent.setup();
  const recover = vi.fn();
  render(
    <AnalysisProgress
      stage="failed"
      events={[...events, {
        event_id: 4,
        session_id: "session",
        stage: "failed",
        payload: { message: "provider interrupted" },
      }]}
      recoveryLabel="Retry operation"
      onRecover={recover}
    />,
  );

  await user.click(screen.getByRole("button", { name: "Retry operation" }));
  expect(recover).toHaveBeenCalledOnce();
});
