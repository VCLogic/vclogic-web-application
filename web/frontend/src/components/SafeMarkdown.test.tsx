import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SafeMarkdown } from "./SafeMarkdown";

const markdown = `# Operating evidence

**ShiftPilot** has:

- eight paying agencies
- three implementations

> Founder-provided and unverified.

| Metric | Value |
| --- | ---: |
| MRR | $18,640 |

\`\`\`text
implementation_days = 21
\`\`\`
`;

describe("SafeMarkdown", () => {
  it("renders GFM as semantic reading content", () => {
    render(<SafeMarkdown>{markdown}</SafeMarkdown>);

    expect(screen.getByRole("heading", { name: "Operating evidence", level: 1 })).toBeVisible();
    expect(screen.getByText("ShiftPilot").tagName).toBe("STRONG");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("Founder-provided and unverified.").closest("blockquote")).not.toBeNull();
    expect(screen.getByRole("table")).toBeVisible();
    expect(screen.getByText("implementation_days = 21").closest("code")).not.toBeNull();
  });

  it("keeps raw HTML inert and hardens external links", () => {
    const { container } = render(<SafeMarkdown>{`<script>alert("x")</script>\n\n[Source](https://example.com)\n\n[Unsafe](javascript:alert(1))`}</SafeMarkdown>);

    expect(container.querySelector("script")).toBeNull();
    expect(container).toHaveTextContent('<script>alert("x")</script>');
    const source = screen.getByRole("link", { name: "Source" });
    expect(source).toHaveAttribute("target", "_blank");
    expect(source).toHaveAttribute("rel", "noreferrer noopener");
    expect(within(container).queryByRole("link", { name: "Unsafe" })).toBeNull();
    expect(screen.getByText("Unsafe")).toBeVisible();
  });
});
