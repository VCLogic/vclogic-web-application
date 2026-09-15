import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { NewPitchProject } from "./NewPitchProject";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("accepts a markdown pitch upload", async () => {
  const user = userEvent.setup();
  const uploaded = new File(["# ShiftPilot\n\nEvidence."], "shiftpilot.md", { type: "text/markdown" });
  Object.defineProperty(uploaded, "text", { value: vi.fn().mockResolvedValue("# ShiftPilot\n\nEvidence.") });
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><NewPitchProject /></MemoryRouter></QueryClientProvider>);

  await user.upload(screen.getByLabelText(/upload pitch/i), uploaded);

  expect(screen.getByLabelText(/^pitch text/i)).toHaveValue("# ShiftPilot\n\nEvidence.");
});
