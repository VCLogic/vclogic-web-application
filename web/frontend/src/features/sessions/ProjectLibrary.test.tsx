import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import { ProjectLibrary } from "./ProjectLibrary";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("shows portrait-led session cards and score movement", async () => {
  vi.spyOn(api, "investors").mockResolvedValue({ investors: [{
    vc_slug: "charles", display_name: "Charles Hudson-like Investor", firm: "Precursor", role: "Partner", disclosure: "Simulation", start_available: true,
    portrait_path: "/investors/charles.jpg", portrait_alt: "Charles Hudson portrait", recurring_positive_rationales: [], recurring_negative_rationales: [],
  }] });
  vi.spyOn(api, "sessions").mockResolvedValue({ sessions: [{
    session_id: "s1", vc_slug: "charles", investor_display_name: "Charles Hudson-like Investor", company_aliases: ["TargetCo"], status: "finished", created_at: "2026-08-25T12:00:00Z",
    initial_decision: "Out", current_decision: "In", initial_likelihood: .44, current_likelihood: .58, cost_usd: .12, verification_status: "verified",
  }] });
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ProjectLibrary /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole("img", { name: "Charles Hudson portrait" })).toBeVisible();
  expect(screen.getByText("TargetCo")).toBeVisible();
  expect(screen.getByText("+14 points")).toBeVisible();
  expect(screen.getByRole("link", { name: /resume rehearsal/i })).toBeVisible();
});

it("deletes a finished rehearsal after confirmation", async () => {
  vi.spyOn(api, "investors").mockResolvedValue({ investors: [] });
  const sessions = vi.spyOn(api, "sessions").mockResolvedValue({ sessions: [{
    session_id: "s1", vc_slug: "charles", investor_display_name: "Charles Hudson-like Investor", company_aliases: ["TargetCo"], status: "finished", created_at: "2026-08-25T12:00:00Z",
    initial_decision: "Out", current_decision: "In", initial_likelihood: .44, current_likelihood: .58, cost_usd: .12, verification_status: "verified",
  }] });
  const remove = vi.spyOn(api, "deleteSession").mockResolvedValue(undefined);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ProjectLibrary /></MemoryRouter></QueryClientProvider>);
  const button = await screen.findByRole("button", { name: "Delete rehearsal for TargetCo" });
  const loads = sessions.mock.calls.length;
  button.click();
  await vi.waitFor(() => expect(remove).toHaveBeenCalledWith("s1"));
  await vi.waitFor(() => expect(sessions.mock.calls.length).toBeGreaterThan(loads));
});

it("offers no delete while a rehearsal is running", async () => {
  vi.spyOn(api, "investors").mockResolvedValue({ investors: [] });
  vi.spyOn(api, "sessions").mockResolvedValue({ sessions: [{
    session_id: "s2", vc_slug: "charles", investor_display_name: "Charles Hudson-like Investor", company_aliases: ["BusyCo"], status: "rehearsal_running", created_at: "2026-08-25T12:00:00Z",
    verification_status: "verified",
  }] });
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ProjectLibrary /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText("BusyCo")).toBeVisible();
  expect(screen.queryByRole("button", { name: /delete rehearsal/i })).toBeNull();
});
