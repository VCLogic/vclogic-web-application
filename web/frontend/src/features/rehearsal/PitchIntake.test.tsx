import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { api } from "../../api/client";
import { PitchIntake } from "./PitchIntake";

it("shows dark decision-influence rows, authorizes, and submits a founder pitch", async () => {
  const user = userEvent.setup();
  vi.spyOn(api, "profile").mockResolvedValue({
    investor: {
      vc_slug: "charles",
      display_name: "Charles Hudson-like Investor",
      firm: "Precursor",
      role: "Partner",
      disclosure: "Not the real investor.",
      start_available: true,
      portrait_path: "/investors/charles.jpg",
      portrait_alt: "Charles Hudson portrait",
      recurring_positive_rationales: ["founder_conviction"],
      recurring_negative_rationales: ["portfolio_conflict"],
      recurring_unresolved_rationales: ["market_size_assessment"],
      recurring_positive_counts: { founder_conviction: 10 },
      recurring_negative_counts: { portfolio_conflict: 5 },
      recurring_unresolved_counts: { market_size_assessment: 2 },
    },
    sections: [],
  });
  const createProject = vi.spyOn(api, "createProject").mockResolvedValue({
    project_id: "p1", display_name: "TargetCo", company_aliases: ["TargetCo"],
    created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
    current_version_id: "v1", version_count: 1, assessment_count: 0,
    rehearsal_count: 0, versions: [],
  });
  const startAssessment = vi.spyOn(api, "startAssessment").mockResolvedValue({ assessment_id: "a1", status: "queued", event_url: "/events" });

  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/new/charles"]}>
        <Routes>
          <Route path="/new/:vcSlug" element={<PitchIntake />} />
          <Route path="/pitches/:projectId/versions/:versionId" element={<p>Project ready</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  const portrait = await screen.findByRole("img", { name: "Charles Hudson portrait" });
  expect(portrait).toBeVisible();
  expect(portrait.closest(".identity-photo")).toBeInTheDocument();
  const influences = screen.getByRole("region", { name: "Frequently observed rationales" });
  expect(influences).toHaveClass("decision-influence-summary--dark");
  expect(within(influences).getByText("Creates conviction")).toBeVisible();
  expect(within(influences).getByText("Creates concern")).toBeVisible();
  expect(within(influences).getByText("Mixed / conditional")).toBeVisible();
  expect(within(influences).getAllByRole("meter")).toHaveLength(3);
  expect(within(influences).getByRole("meter", { name: /market size assessment observed recurrence/i })).toHaveAttribute("aria-valuenow", "20");
  expect(screen.getByText("Rationale analysis")).toBeVisible();
  expect(screen.getByText(/pitch becomes immutable/i)).toBeVisible();
  expect(screen.getByText(/rehearsal can start from the saved assessment/i)).toBeVisible();

  const pitchText = screen.getByLabelText(/^pitch text/i);
  expect(pitchText.closest(".intake-form")).toBeInTheDocument();

  await user.type(screen.getByLabelText(/company name/i), "TargetCo");
  await user.type(pitchText, "Founder pitch");
  await user.click(screen.getByRole("checkbox", { name: /provider api costs/i }));
  await user.click(screen.getByRole("button", { name: /begin investor assessment/i }));

  expect(createProject).toHaveBeenCalledWith({display_name:"TargetCo", company_aliases:["TargetCo"], pitch_text:"Founder pitch"});
  expect(startAssessment).toHaveBeenCalledWith("p1", "v1", "charles");
  expect(await screen.findByText("Project ready")).toBeVisible();
});

it("restores the immutable pitch when restarting a failed initial assessment", async () => {
  vi.spyOn(api, "profile").mockResolvedValue({
    investor: {
      vc_slug: "charles",
      display_name: "Charles Hudson-like Investor",
      firm: "Precursor",
      role: "Partner",
      disclosure: "Not the real investor.",
      start_available: true,
      recurring_positive_rationales: [],
      recurring_negative_rationales: [],
    },
    sections: [],
  });

  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[{
        pathname: "/new/charles",
        state: { pitchText: "Recovered founder pitch" },
      }]}>
        <Routes><Route path="/new/:vcSlug" element={<PitchIntake />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByLabelText(/^pitch text/i)).toHaveValue("Recovered founder pitch");
  expect(screen.getByText(/restored from the failed assessment/i)).toBeVisible();
});
