import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InvestorPortrait } from "./InvestorPortrait";

describe("InvestorPortrait", () => {
  it("tries the next investor's photo after a previous image failed", () => {
    const { rerender } = render(<InvestorPortrait name="Missing Person" src="/api/investors/missing/portrait" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByLabelText("Missing Person portrait unavailable")).toBeInTheDocument();
    rerender(<InvestorPortrait name="Mac Conwell" src="/api/investors/mac-conwell/portrait"
      attribution="Photo: The Pitch" sourceUrl="https://www.thepitch.show/investors/mac-conwell-rarebreed-ventures" showAttribution />);
    expect(screen.getByRole("img", { name: "Mac Conwell portrait" })).toHaveAttribute("src", "/api/investors/mac-conwell/portrait");
    expect(screen.getByRole("link", { name: "Photo: The Pitch" })).toHaveAttribute("href", "https://www.thepitch.show/investors/mac-conwell-rarebreed-ventures");
  });
});
