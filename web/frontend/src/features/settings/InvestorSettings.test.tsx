import { MemoryRouter } from "react-router-dom";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { InvestorSettingsResponse } from "../../api/types";
import { InvestorSettings } from "./InvestorSettings";

const first = "a".repeat(64), second = "b".repeat(64);
const settings: InvestorSettingsResponse = { investors: [{ vc_slug: "example", display_name: "Example VC", enabled: true, available: true, active_version: first, versions: [
  {version_id: first, label: "Original", ready: true, error: null, capabilities: {wiki: true}},
  {version_id: second, label: "Updated", ready: true, error: null, capabilities: {wiki: true, precedents: true}},
]}], discovery_errors: [] };
function setup() {
  vi.spyOn(api, "investorSettings").mockResolvedValue(settings);
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}, mutations:{retry:false}}})}><MemoryRouter><InvestorSettings/></MemoryRouter></QueryClientProvider>);
}
afterEach(()=>{cleanup();vi.restoreAllMocks()});
it("saves one active version and the enabled choice", async()=>{
  const save = vi.spyOn(api,"updateInvestorSettings").mockResolvedValue(settings);
  setup(); const user=userEvent.setup();
  const form=await screen.findByRole("form",{name:"Example VC"});
  expect(within(form).getByRole("link", {name:"View selected version specifications"})).toHaveAttribute("href", `/settings/investors/example/specifications?version=${first}`);
  await user.selectOptions(within(form).getByLabelText("Active version"), second);
  expect(within(form).getByRole("link", {name:"View selected version specifications"})).toHaveAttribute("href", `/settings/investors/example/specifications?version=${second}`);
  expect(save).not.toHaveBeenCalled();
  await user.click(within(form).getByRole("checkbox",{name:"Enabled for new assessments"}));
  await user.click(within(form).getByRole("button",{name:"Save changes"}));
  expect(save).toHaveBeenCalledWith("example",{enabled:false,active_version:second});
  expect(await screen.findByText("Settings saved.")).toBeVisible();
});
it("retains edits and offers retry after a failed save",async()=>{
  vi.spyOn(api,"updateInvestorSettings").mockRejectedValue(new Error("Version is no longer available. Refresh and choose another."));
  setup(); const user=userEvent.setup();
  await user.selectOptions(await screen.findByLabelText("Active version"),second);
  await user.click(screen.getByRole("button",{name:"Save changes"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("Version is no longer available");
  expect(screen.getByLabelText("Active version")).toHaveValue(second);
  expect(screen.getByRole("button",{name:"Save changes"})).toBeEnabled();
});
it("shows incomplete versions without allowing activation",async()=>{
  vi.spyOn(api,"investorSettings").mockResolvedValue({investors:[{...settings.investors[0], enabled:false, available:false, active_version:null,
    versions:[{...settings.investors[0].versions[0],ready:false,error:"Required indexes are missing."}]}],discovery_errors:[]});
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><InvestorSettings/></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText("Required indexes are missing.")).toBeVisible();
  expect(screen.getByRole("link", {name:"Inspect Original specifications"})).toHaveAttribute("href", `/settings/investors/example/specifications?version=${first}`);
  expect(screen.getByRole("option",{name:/Original/})).toBeDisabled();
  expect(screen.getByRole("checkbox")).toBeDisabled();
});
