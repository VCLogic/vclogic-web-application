import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "../../api/types";
import { InvestmentMemoryLibrary } from "./InvestmentMemoryLibrary";

vi.mock("./MemorySearch", () => ({
  MemorySearch: ({ vcSlug, query }: { vcSlug: string; query: string }) => <div data-testid="memory-search">Search {vcSlug}: {query}</div>,
}));

afterEach(cleanup);

const sections: Profile["sections"] = [
  { section_id: "evidence/market_opportunity.md", title: "market_opportunity", preview: "Market preview.", body: "Complete market evidence.", character_count: 25, source_paths: ["wiki/evidence/market.md"] },
  { section_id: "persona.md", title: "Charles Hudson — Decision Policy", preview: "Persona preview.", body: "Complete persona body.", character_count: 21, source_paths: ["wiki/persona.md"] },
  { section_id: "theses.md", title: "investment_theses", preview: "Thesis preview.", body: "Complete thesis body.", character_count: 20, source_paths: ["wiki/theses.md"] },
  { section_id: "portfolio_and_constraints.md", title: "portfolio_and_constraints", preview: "Portfolio preview.", body: "Complete portfolio body.", character_count: 23, source_paths: ["wiki/portfolio.md"] },
  { section_id: "evidence/founder_team.md", title: "founder_team", preview: "Founder preview.", body: "Complete founder evidence.", character_count: 26, source_paths: ["wiki/evidence/founder.md"] },
];

const markdownSections: Profile["sections"] = [{
  section_id: "persona.md",
  title: "Markdown chapter",
  preview: "Structured preview.",
  body: "# Investment approach\n\n- Back exceptional founders\n- Enter before consensus\n\n> Public evidence, not private knowledge.\n\nRead the [source](https://example.com).\n\n```text\ncheck_size = 100000\n```",
  character_count: 169,
  source_paths: [],
}];

describe("InvestmentMemoryLibrary", () => {
  it("groups the chapter index and selects persona by default", () => {
    render(<InvestmentMemoryLibrary vcSlug="charles" sections={sections} query="founder_execution" onQueryChange={vi.fn()} />);

    expect(screen.getByText("Core profile")).toBeVisible();
    expect(screen.getByText("Evidence library")).toBeVisible();
    expect(screen.getByTestId("memory-search")).toHaveTextContent("Search charles: founder_execution");
    expect(screen.getByRole("article", { name: "Investment Memory chapter: Charles Hudson — Decision Policy" })).toBeVisible();
    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(screen.getByText("Persona preview.")).toBeVisible();
  });

  it("switches the single reader without retaining the previous chapter", async () => {
    const user = userEvent.setup();
    render(<InvestmentMemoryLibrary vcSlug="charles" sections={sections} query="" onQueryChange={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Open Market opportunity chapter" }));

    expect(screen.getByRole("article", { name: "Investment Memory chapter: Market opportunity" })).toBeVisible();
    expect(screen.getByText("Market preview.")).toBeVisible();
    expect(screen.queryByText("Persona preview.")).not.toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(1);
  });

  it("keeps complete bodies and source paths behind named disclosures", async () => {
    const user = userEvent.setup();
    render(<InvestmentMemoryLibrary vcSlug="charles" sections={sections} query="" onQueryChange={vi.fn()} />);
    const reader = screen.getByRole("article", { name: "Investment Memory chapter: Charles Hudson — Decision Policy" });

    expect(within(reader).getByText("Complete persona body.")).not.toBeVisible();
    expect(within(reader).getByText("wiki/persona.md")).not.toBeVisible();
    await user.click(within(reader).getByRole("group", { name: "Read complete chapter: Charles Hudson — Decision Policy" }).querySelector("summary")!);
    expect(within(reader).getByText("Complete persona body.")).toBeVisible();
    await user.click(within(reader).getByRole("group", { name: "Inspect sources: Charles Hudson — Decision Policy" }).querySelector("summary")!);
    expect(within(reader).getByText("wiki/persona.md")).toBeVisible();
  });

  it("renders complete chapter Markdown as safe semantic content", async () => {
    const user = userEvent.setup();
    render(<InvestmentMemoryLibrary vcSlug="charles" sections={markdownSections} query="" onQueryChange={vi.fn()} />);
    const reader = screen.getByRole("article", { name: "Investment Memory chapter: Markdown chapter" });

    await user.click(within(reader).getByText("Read complete chapter"));

    expect(within(reader).getByRole("heading", { name: "Investment approach" })).toBeVisible();
    expect(within(reader).getByRole("list")).toBeVisible();
    expect(within(reader).getByRole("link", { name: "source" })).toHaveAttribute("href", "https://example.com");
    expect(within(reader).getByText("Public evidence, not private knowledge.").closest("blockquote")).toBeInTheDocument();
    expect(within(reader).getByText("check_size = 100000").closest("code")).toBeInTheDocument();
    expect(within(reader).queryByText(/^# Investment approach/)).not.toBeInTheDocument();
  });

  it("offers every chapter through the compact mobile selector", async () => {
    const user = userEvent.setup();
    render(<InvestmentMemoryLibrary vcSlug="charles" sections={sections} query="" onQueryChange={vi.fn()} />);
    const select = screen.getByRole("combobox", { name: "Choose Investment Memory chapter" });

    expect(within(select).getAllByRole("option")).toHaveLength(5);
    await user.selectOptions(select, "evidence/founder_team.md");
    expect(screen.getByRole("article", { name: "Investment Memory chapter: Founder team" })).toBeVisible();
  });

  it("preserves evidence search when no chapters exist", () => {
    render(<InvestmentMemoryLibrary vcSlug="charles" sections={[]} query="market" onQueryChange={vi.fn()} />);

    expect(screen.getByTestId("memory-search")).toBeVisible();
    expect(screen.getByText("No Investment Memory chapters are available for this profile.")).toBeVisible();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });
});
