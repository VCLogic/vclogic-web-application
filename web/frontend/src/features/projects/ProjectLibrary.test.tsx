import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import { ProjectLibrary } from "./ProjectLibrary";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("lists durable pitch projects with version and activity coverage", async () => {
  vi.spyOn(api, "projects").mockResolvedValue({ projects: [{
    project_id: "p1", display_name: "ShiftPilot", company_aliases: ["ShiftPilot"],
    created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T01:00:00Z",
    current_version_id: "v1", version_count: 2, assessment_count: 3, rehearsal_count: 4,
  }] });
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ProjectLibrary /></MemoryRouter></QueryClientProvider>);

  expect(await screen.findByRole("heading", { name: "ShiftPilot" })).toBeVisible();
  expect(screen.getByText("2 pitch versions")).toBeVisible();
  expect(screen.getByText("3 investor assessments")).toBeVisible();
  expect(screen.getByText("4 rehearsals")).toBeVisible();
  expect(screen.getByRole("link", { name: /open shiftpilot/i })).toHaveAttribute("href", "/pitches/p1/versions/v1");
});

it("offers a useful empty state", async () => {
  vi.spyOn(api, "projects").mockResolvedValue({ projects: [] });
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ProjectLibrary /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText("Your pitch library starts here")).toBeVisible();
  expect(screen.getByRole("link", { name: /create a pitch project/i })).toHaveAttribute("href", "/pitches/new");
});
