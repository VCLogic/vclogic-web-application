import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Session } from "../../api/types";
import { PitchPanel } from "./PitchPanel";

afterEach(cleanup);

const pitch = `# ShiftPilot

## Traction

- We have **eight paying agencies** today.
- Retention is not yet known.`;

function makeSession(): Session {
  const evidence = "eight paying agencies";
  const start = pitch.indexOf(evidence);
  return {
    session_id: "markdown-pitch",
    vc_slug: "yin",
    investor_display_name: "Elizabeth Yin-like Investor",
    disclosure: "Simulation",
    status: "complete",
    pitch_text: pitch,
    pitch_sha256: "abc",
    turns: [],
    annotations: [{
      annotation_id: "a1",
      start,
      end: start + evidence.length,
      text: evidence,
      direction: "positive",
      rationale_ids: ["product_adoption"],
      evidence_ids: ["e1"],
    }],
    evidence: [{ evidence_id: "e1", source_kind: "pitch", source_path: "pitch.md", excerpt: evidence }],
    usage: {},
    findings: [],
  };
}

describe("PitchPanel Markdown evidence", () => {
  it("renders Markdown structure while keeping evidence interactive", async () => {
    const user = userEvent.setup();
    const onEvidence = vi.fn();
    render(<PitchPanel session={makeSession()} onEvidence={onEvidence} />);

    expect(screen.getByRole("heading", { name: "ShiftPilot", level: 1 })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Traction", level: 2 })).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("eight paying agencies").tagName).toBe("MARK");

    const markedEvidence = screen.getByRole("button", { name: "positive pitch evidence" });
    await user.click(markedEvidence);
    expect(onEvidence).toHaveBeenCalledWith(["e1"]);
    markedEvidence.focus();
    await user.keyboard("{Enter}");
    expect(onEvidence).toHaveBeenCalledTimes(2);
  });

  it("keeps a filtered annotation readable but noninteractive", async () => {
    const user = userEvent.setup();
    render(<PitchPanel session={makeSession()} onEvidence={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Negative pitch signals" }));

    const mark = screen.getByText("eight paying agencies");
    expect(mark).toHaveClass("filtered");
    expect(mark).toHaveAttribute("aria-disabled", "true");
    expect(mark).toHaveAttribute("tabindex", "-1");
  });
});
