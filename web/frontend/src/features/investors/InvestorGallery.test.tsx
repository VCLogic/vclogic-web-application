import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { api } from "../../api/client";
import { InvestorGallery } from "./InvestorGallery";

const investor = {
  vc_slug: "charles",
  display_name: "Charles Hudson-like Investor",
  firm: "Precursor",
  role: "Partner",
  disclosure: "Simulation; not the real investor and not endorsed by them.",
  start_available: true,
  portrait_path: "/investors/charles.jpg",
  portrait_alt: "Charles Hudson portrait",
  evidence_coverage: 0.91,
  recurring_positive_rationales: ["founder_conviction"],
  recurring_negative_rationales: ["portfolio_conflict"],
  recurring_unresolved_rationales: ["market_size_assessment"],
  recurring_positive_counts: { founder_conviction: 10 },
  recurring_negative_counts: { portfolio_conflict: 5 },
  recurring_unresolved_counts: { market_size_assessment: 2 },
};

const investorWithoutInfluences = {
  ...investor,
  vc_slug: "no-signals",
  display_name: "No Signals Investor",
  portrait_alt: "No Signals portrait",
  recurring_positive_rationales: [],
  recurring_negative_rationales: [],
  recurring_unresolved_rationales: [],
};

function renderGallery() {
  vi.spyOn(api, "investors").mockResolvedValue({ investors: [investor, investorWithoutInfluences] });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter><InvestorGallery /></MemoryRouter>
    </QueryClientProvider>,
  );
}

it("renders compact frequently observed rationales without implying causal importance", async () => {
  renderGallery();

  const portrait = await screen.findByRole("img", { name: "Charles Hudson portrait" });
  expect(portrait).toBeVisible();
  expect(portrait.closest(".preview-portrait")).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Investor profiles" })).toBeVisible();
  expect(screen.getByText("Investor-like simulation")).toBeVisible();
  expect(screen.getByText("Frequently observed rationales")).toBeVisible();
  expect(screen.getByText(/frequency in the available record, not causal importance/i)).toBeVisible();

  const influences = screen.getByRole("region", { name: "Frequently observed rationales" });
  expect(within(influences).getByText("Creates conviction")).toBeVisible();
  expect(within(influences).getByText("Creates concern")).toBeVisible();
  expect(within(influences).getByText("Mixed / conditional")).toBeVisible();
  expect(within(influences).getByText("Founder Conviction")).toBeVisible();
  expect(within(influences).getByText("Portfolio Conflict")).toBeVisible();
  expect(within(influences).getByText("Market Size Assessment")).toBeVisible();
  expect(within(influences).getAllByRole("meter")).toHaveLength(3);
  expect(within(influences).getByRole("meter", { name: /portfolio conflict observed recurrence/i })).toHaveAttribute("aria-valuenow", "50");
  expect(screen.queryByText(/evidence coverage/i)).not.toBeInTheDocument();
  expect(screen.queryByText("91%")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /assess your pitch/i })).toBeVisible();
  expect(screen.getByRole("link", { name: /explore decision dossier/i })).toBeVisible();

  fireEvent.click(screen.getByRole("button", { name: /no signals investor/i }));
  expect(screen.getByRole("heading", { name: "No Signals Investor" })).toBeVisible();
  expect(screen.queryByRole("region", { name: "Frequently observed rationales" })).not.toBeInTheDocument();
});
