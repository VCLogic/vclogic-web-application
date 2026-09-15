import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { InvestorMatch } from "../../api/types";
import { MatchResults } from "./MatchResults";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const match: InvestorMatch = {
  match_id:"m1", project_id:"p1", version_id:"v1", selected_vc_slugs:["yin","phil"],
  status:"partial", created_at:"2026-09-01T00:00:00Z", updated_at:"2026-09-01T00:01:00Z",
  assessments:[
    {assessment_id:"a1",vc_slug:"yin",status:"complete",decision:"In",investment_likelihood:.71,decision_confidence:.8,positive_rationales:["founder_market_fit"],negative_rationales:["traction_repeatability_concern"],unresolved_rationales:[],relative_fit:{percentile:81,reference_count:20},highest_estimated_fit:true,leading_group:true},
    {assessment_id:"a2",vc_slug:"phil",status:"failed",positive_rationales:[],negative_rationales:[],unresolved_rationales:[],relative_fit:{percentile:null,reference_count:0},highest_estimated_fit:false,leading_group:false,public_error:"Provider timed out"},
  ],
};

it("prioritizes historical fit while distinguishing fit from confidence", async () => {
  vi.spyOn(api,"match").mockResolvedValue(match);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MatchResults match={match} investors={[
    {vc_slug:"yin",display_name:"Elizabeth Yin-like Investor",firm:"Hustle Fund",role:"Partner",disclosure:"",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]},
    {vc_slug:"phil",display_name:"Phil Nadel-like Investor",firm:"Forefront",role:"Partner",disclosure:"",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]},
  ]}/></MemoryRouter></QueryClientProvider>);

  expect(screen.getByText("71/100")).toBeVisible();
  expect(screen.getByText("Estimated investor fit")).toBeVisible();
  expect(screen.getByText("Historical fit percentile")).toBeVisible();
  expect(screen.getByText("Assessment confidence")).toBeVisible();
  expect(screen.getByText("Highest historical fit")).toBeVisible();
  expect(screen.getByText(/not endorsements or comparable real-world investment probabilities/i)).toBeVisible();
  expect(screen.queryByText("Investment likelihood")).not.toBeInTheDocument();
  expect(screen.getByText("81st percentile")).toBeVisible();
  expect(screen.getByText("20 historical pitches")).toBeVisible();
  expect(screen.getByRole("link",{name:/view assessment/i})).toHaveAttribute("href","/pitches/p1/versions/v1?tab=assessments");
  expect(screen.getByText("Provider timed out")).toBeVisible();
});

it("retries only the failed investor", async () => {
  const user=userEvent.setup();
  vi.spyOn(api,"match").mockResolvedValue(match);
  const retry=vi.spyOn(api,"retryMatch").mockResolvedValue({...match,status:"running"});
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MatchResults match={match} investors={[]}/></MemoryRouter></QueryClientProvider>);
  await user.click(screen.getByRole("button",{name:/retry/i}));
  expect(retry).toHaveBeenCalledWith("m1","phil");
});
