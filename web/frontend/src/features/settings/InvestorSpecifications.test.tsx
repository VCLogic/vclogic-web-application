import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { InvestorSpecifications as Specifications } from "../../api/types";
import { InvestorSpecifications } from "./InvestorSpecifications";

const first = "a".repeat(64), second = "b".repeat(64);
const specification: Specifications = {
  vc_slug: "example", display_name: "Example VC", investor_version_id: first,
  version_label: "Original version", enabled: false, active: false, ready: false,
  error: "Classifier assets are missing.", notes: ["Configuration inspection does not call a model provider."],
  sections: [{id:"assessment", title:"Assessment configuration", fields:[
    {label:"Model", value:"provider/model"}, {label:"Classifier enabled", value:false},
    {label:"Question limit", value:0}, {label:"Optional threshold", value:null},
    {label:"Decision tiers", value:["small", "standard"]},
  ]}],
  taxonomy: [{label:"founder_market_fit", definition:"Relevant founder experience.", coarse_parent:"Founder"}],
};
function renderPage(path = `/settings/investors/example/specifications?version=${first}`) {
  return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}>
    <MemoryRouter initialEntries={[path]}><Link to={`/settings/investors/example/specifications?version=${second}`}>Other version</Link><Routes>
      <Route path="/settings/investors/:vcSlug/specifications" element={<InvestorSpecifications/>}/>
    </Routes></MemoryRouter>
  </QueryClientProvider>);
}
afterEach(() => {cleanup(); vi.restoreAllMocks();});

it("inspects a disabled unready version without modifying settings", async () => {
  const request = vi.spyOn(api,"investorSpecifications").mockResolvedValue(specification);
  const save = vi.spyOn(api,"updateInvestorSettings");
  renderPage();
  expect(await screen.findByRole("heading", {name:"Example VC"})).toBeVisible();
  expect(request).toHaveBeenCalledWith("example", first);
  expect(screen.getByText("Disabled for new assessments")).toBeVisible();
  expect(screen.getByText("Alternative version")).toBeVisible();
  expect(screen.getByText("Not ready")).toBeVisible();
  expect(screen.getByText("Classifier assets are missing.")).toBeVisible();
  expect(screen.getByText(/Prepared configuration: read-only defaults/)).toBeVisible();
  expect(screen.getByText("No")).toBeVisible();
  expect(screen.getByText("0")).toBeVisible();
  expect(screen.getByText("Not specified")).toBeVisible();
  await userEvent.click(screen.getByText("Decision taxonomy (1 rationales)"));
  expect(screen.getByText("Relevant founder experience.")).toBeVisible();
  expect(screen.getByRole("link", {name:"Back to investor settings"})).toHaveAttribute("href", "/settings/investors");
  expect(save).not.toHaveBeenCalled();
});

it("loads a different version without retaining the previous version's fields", async () => {
  const request = vi.spyOn(api,"investorSpecifications").mockImplementation(async (_, version) => ({...specification,
    investor_version_id: version!, version_label: version === first ? "Original version" : "Changed version"}));
  renderPage();
  await screen.findByText("Original version");
  await userEvent.click(screen.getByRole("link", {name:"Other version"}));
  expect(await screen.findByText("Changed version")).toBeVisible();
  expect(screen.queryByText("Original version")).not.toBeInTheDocument();
  expect(request).toHaveBeenLastCalledWith("example", second);
});

it("announces loading and resolves the active version when no version is supplied", () => {
  const request = vi.spyOn(api,"investorSpecifications").mockReturnValue(new Promise(() => {}));
  renderPage("/settings/investors/example/specifications");
  expect(screen.getByRole("status")).toHaveTextContent("Loading investor specifications");
  expect(request).toHaveBeenCalledWith("example", undefined);
});

it("shows a request error and retries without changing settings", async () => {
  vi.spyOn(api,"investorSpecifications").mockRejectedValueOnce(new Error("Selected version is unavailable."))
    .mockResolvedValueOnce(specification);
  renderPage();
  expect(await screen.findByRole("alert")).toHaveTextContent("Selected version is unavailable.");
  await userEvent.click(screen.getByRole("button", {name:"Try again"}));
  expect(await screen.findByRole("heading", {name:"Example VC"})).toBeVisible();
});
