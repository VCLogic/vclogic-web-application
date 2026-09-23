import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ApiError, api } from "../../api/client";
import { ProjectWorkspace } from "./ProjectWorkspace";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const investor = (slug:string, name:string) => ({ vc_slug:slug, investor_version_id:"b".repeat(64), display_name:name, firm:"Fund", role:"Partner", disclosure:"Investor-like simulation.", start_available:true, recurring_positive_rationales:[], recurring_negative_rationales:[] });

function setup() {
  vi.spyOn(api, "project").mockResolvedValue({ project_id:"p1", display_name:"ShiftPilot", company_aliases:["ShiftPilot"], created_at:"2026-09-01T00:00:00Z", updated_at:"2026-09-01T00:00:00Z", current_version_id:"v1", version_count:1, assessment_count:0, rehearsal_count:0, versions:[{version_id:"v1",project_id:"p1",created_at:"2026-09-01T00:00:00Z",pitch_sha256:"a".repeat(64),character_count:27}] });
  vi.spyOn(api, "pitchVersion").mockResolvedValue({version_id:"v1",project_id:"p1",created_at:"2026-09-01T00:00:00Z",pitch_sha256:"a".repeat(64),character_count:27,pitch_text:"# ShiftPilot\n\nPaid pilots."});
  vi.spyOn(api, "assessments").mockResolvedValue({assessments:[]});
  vi.spyOn(api, "matches").mockResolvedValue({matches:[]});
  vi.spyOn(api, "comparison").mockRejectedValue(new ApiError(404,"No comparison"));
  vi.spyOn(api, "investors").mockResolvedValue({investors:[investor("yin","Elizabeth Yin-like Investor"),investor("phil","Phil Nadel-like Investor"),investor("cyan","Cyan Banister-like Investor")]});
}

it("keeps immutable pitch markdown available and supports one investor", async () => {
  setup();
  const user=userEvent.setup();
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/pitches/p1/versions/v1"]}><Routes><Route path="/pitches/:projectId/versions/:versionId" element={<ProjectWorkspace/>}/></Routes></MemoryRouter></QueryClientProvider>);
  expect((await screen.findAllByRole("heading",{name:"ShiftPilot"}))[0]).toBeVisible();
  expect(screen.getByText("Paid pilots.")).toBeVisible();
  await user.click(screen.getByRole("tab",{name:"Investor comparison"}));
  expect(screen.getByText(/choose one profile for an individual view/i)).toBeVisible();
});

it("selects 2–6 profiles with explicit cost authorization", async () => {
  setup();
  const user=userEvent.setup();
  vi.spyOn(api,"updateComparison").mockResolvedValue({comparison_id:"comparison-v1",project_id:"p1",version_id:"v1",selected_vc_slugs:["yin","phil"],status:"running",created_at:"2026-09-01T00:00:00Z",updated_at:"2026-09-01T00:00:00Z",missing_vc_slugs:["yin","phil"],assessments:[]});
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/pitches/p1/versions/v1?tab=match"]}><Routes><Route path="/pitches/:projectId/versions/:versionId" element={<ProjectWorkspace/>}/></Routes></MemoryRouter></QueryClientProvider>);
  await user.click(await screen.findByRole("checkbox",{name:/elizabeth yin-like/i}));
  await user.click(screen.getByRole("checkbox",{name:/phil nadel-like/i}));
  expect(screen.getByRole("button",{name:/compare 2 investor-like profiles/i})).toBeDisabled();
  await user.click(screen.getByRole("checkbox",{name:/authorize provider api costs/i}));
  await user.click(screen.getByRole("button",{name:/compare 2 investor-like profiles/i}));
  expect(api.updateComparison).toHaveBeenCalledWith("p1","v1",["yin","phil"],true,{yin:"b".repeat(64),phil:"b".repeat(64)});
});

it("opens the investor comparison from its human-readable deep link", async () => {
  setup();
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/pitches/p1/versions/v1?tab=comparison"]}><Routes><Route path="/pitches/:projectId/versions/:versionId" element={<ProjectWorkspace/>}/></Routes></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole("heading", { name: "Who should assess this pitch?" })).toBeVisible();
  expect(screen.getByRole("tab", { name: "Investor comparison" })).toHaveAttribute("aria-selected", "true");
});

it("requires a new selection when the selected investor version changes", async()=>{
  setup();
  const client = new QueryClient();
  const user = userEvent.setup();
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/pitches/p1/versions/v1?tab=comparison"]}><Routes><Route path="/pitches/:projectId/versions/:versionId" element={<ProjectWorkspace/>}/></Routes></MemoryRouter></QueryClientProvider>);
  await user.click(await screen.findByRole("checkbox",{name:/elizabeth yin-like/i}));
  vi.mocked(api.investors).mockResolvedValue({investors:[{...investor("yin","Elizabeth Yin-like Investor"),investor_version_id:"c".repeat(64)}]});
  await act(async()=>{await client.invalidateQueries({queryKey:["investors"]})});
  await waitFor(()=>expect(screen.getByRole("checkbox",{name:/elizabeth yin-like/i})).not.toBeChecked());
  expect(screen.getByRole("alert")).toHaveTextContent(/version.*changed/i);
});
