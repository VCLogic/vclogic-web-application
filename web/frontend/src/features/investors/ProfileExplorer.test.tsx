import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { Graph, Profile } from "../../api/types";
import { ProfileExplorer } from "./ProfileExplorer";

const profile: Profile = {
  investor: {
    vc_slug: "charles",
    investor_version_id: "a".repeat(64),
    display_name: "Charles Hudson-like Investor",
    firm: "Precursor Ventures",
    role: "Managing Partner",
    disclosure: "Simulation reconstructed from public traces; not the real investor and not endorsed by them.",
    start_available: true,
    summary: "Observable investment approach.",
    portrait_path: "/investors/charles.jpg",
    portrait_alt: "Charles Hudson portrait",
    source_profile_url: "https://www.thepitch.show/investors/charles",
    photo_attribution: "Photo: The Pitch",
    recurring_positive_rationales: ["founder_conviction"],
    recurring_negative_rationales: ["portfolio_conflict"],
    recurring_unresolved_rationales: [],
  },
  sections: [
    {
      section_id: "thesis",
      title: "Investment Thesis",
      preview: "Early conviction is the heart of this chapter.",
      character_count: 42,
      body: "COMPLETE THESIS BODY. We invest early.",
      source_paths: ["wiki/very/long/thesis-source.md"],
    },
    {
      section_id: "process",
      title: "Decision Process",
      preview: "Pattern recognition is tested with evidence.",
      character_count: 84,
      body: "COMPLETE PROCESS BODY. Evidence changes the decision.",
      source_paths: ["wiki/process-one.md", "wiki/process-two.md"],
    },
  ],
};

const graph: Graph = {
  nodes: [{
    node_id: "founder",
    taxonomy_label: "founder_conviction",
    title: "Founder conviction",
    direction: "positive",
    salience: "high",
    confidence: 0.9,
    evidence_ids: [],
    coarse_parent: "founder_team",
    occurrence_count: 9,
    direction_counts: { positive: 7, negative: 2 },
  }],
  edges: [],
};

function renderProfile({ showInvestorSwitch = false }: { showInvestorSwitch?: boolean } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/profiles/charles"]}>
        <Routes><Route path="/profiles/:vcSlug" element={<><ProfileExplorer />{showInvestorSwitch && <Link to="/profiles/alice">Open Alice profile</Link>}</>} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ProfileExplorer", () => {
  it("renders a compact decision dossier, atlas, and one closed memory reader", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    const memory = vi.spyOn(api, "memory").mockResolvedValue({ results: [] });

    renderProfile();

    expect(await screen.findByRole("img", { name: "Charles Hudson portrait" })).toBeVisible();
    expect(screen.getByRole("link", { name: /photo: the pitch/i })).toBeVisible();
    expect(screen.getByText("Investor decision dossier")).toBeVisible();
    expect(screen.getByRole("link", {name:"View investor specifications"})).toHaveAttribute("href", `/settings/investors/charles/specifications?version=${"a".repeat(64)}`);
    expect(screen.getByRole("heading", { name: "Decision Signature" })).toBeVisible();
    expect(screen.getByText("2 chapters")).toBeVisible();
    expect(screen.getByText("1 decision theme")).toBeVisible();
    expect(screen.getByText("1 rationale")).toBeVisible();
    expect(screen.getByText("Early conviction is the heart of this chapter.")).toBeVisible();
    expect(screen.getByText("42 characters · 1 source")).toBeVisible();
    expect(screen.getByText(/not the real investor/i)).toBeVisible();

    const disclosures = [
      screen.getByRole("group", { name: "Read complete chapter: Investment Thesis" }),
      screen.getByRole("group", { name: "Inspect sources: Investment Thesis" }),
    ];
    expect(disclosures).toHaveLength(2);
    disclosures.forEach((details) => expect(details).not.toHaveAttribute("open"));
    expect(screen.getByText(/COMPLETE THESIS BODY/)).not.toBeVisible();
    expect(screen.getByText("wiki/very/long/thesis-source.md")).not.toBeVisible();
    expect(memory).not.toHaveBeenCalled();
    expect(screen.getAllByRole("article", { name: /^Investment Memory chapter:/ })).toHaveLength(1);
  });

  it("reveals the complete body and source paths when a chapter is opened", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    vi.spyOn(api, "memory").mockResolvedValue({ results: [] });
    const user = userEvent.setup();

    renderProfile();
    const reader = await screen.findByRole("article", { name: "Investment Memory chapter: Investment Thesis" });
    await user.click(within(reader).getByText("Read complete chapter"));
    await user.click(within(reader).getByText("Inspect sources (1)"));

    expect(screen.getByText(/COMPLETE THESIS BODY/)).toBeVisible();
    expect(screen.getByText("wiki/very/long/thesis-source.md")).toBeVisible();
    expect(screen.getByRole("group", { name: "Read complete chapter: Investment Thesis" })).toHaveAttribute("open");
  });

  it("places search above chapters and sends a selected taxonomy label to memory search once", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    const memory = vi.spyOn(api, "memory").mockResolvedValue({ results: [] });
    const user = userEvent.setup();

    renderProfile();
    await user.click(await screen.findByRole("button", { name: "Find evidence for Founder conviction" }));

    const input = screen.getByRole("textbox", { name: "Search investment memory" });
    expect(input).toHaveValue("founder_conviction");
    await vi.waitFor(() => expect(memory).toHaveBeenCalledTimes(1));
    expect(memory).toHaveBeenCalledWith("charles", "founder_conviction", 1, 5);
    const search = screen.getByRole("region", { name: "Search the Investment Memory" });
    const firstChapter = screen.getByRole("article", { name: "Investment Memory chapter: Investment Thesis" });
    expect(search.compareDocumentPosition(firstChapter) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows memory search errors and retries the same query successfully", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    const memory = vi.spyOn(api, "memory")
      .mockRejectedValueOnce(new Error("search unavailable"))
      .mockResolvedValueOnce({ results: [{ evidence_id: "e1", source_kind: "interview", excerpt: "Founder evidence recovered.", source_path: "wiki/recovered.md" }] });
    const user = userEvent.setup();

    renderProfile();
    await user.click(await screen.findByRole("button", { name: "Find evidence for Founder conviction" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/unable to search the investment memory/i);
    await user.click(screen.getByRole("button", { name: /retry memory search/i }));

    expect(await screen.findByText("Founder evidence recovered.")).toBeVisible();
    expect(memory).toHaveBeenCalledTimes(2);
    expect(memory).toHaveBeenLastCalledWith("charles", "founder_conviction", 1, 5);
  });

  it("shows five clean results and navigates through server pages", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    const pageOne = Array.from({ length: 5 }, (_, index) => ({
      evidence_id: `e-${index + 1}`,
      source_kind: "talk",
      source_title: "Business Model Economics",
      excerpt: `Clean evidence ${index + 1}`,
      source_path: "inputs/wiki/charles/evidence/business_model_economics.md",
      rationale_label: "business_model_assessment",
      direction: "positive" as const,
      source_reference: "talk:c1eoWu8QVIU",
    }));
    const memory = vi.spyOn(api, "memory").mockImplementation(async (_slug, _query, page) => page === 2
      ? { results: [{ ...pageOne[0], evidence_id: "e-6", excerpt: "Clean evidence 6" }], page: 2, page_size: 5, total_results: 6, total_pages: 2 }
      : { results: pageOne, page: 1, page_size: 5, total_results: 6, total_pages: 2 });
    const user = userEvent.setup();

    renderProfile();
    await user.click(await screen.findByRole("button", { name: "Find evidence for Founder conviction" }));

    expect(await screen.findByText("Showing 1–5 of 6")).toBeVisible();
    expect(screen.getByText("Page 1 of 2")).toBeVisible();
    const firstCard = screen.getByRole("article", {
      name: "Evidence 1 of 6 from Business Model Economics",
    });
    expect(screen.getAllByRole("article", { name: /^Evidence / }).map((card) => card.getAttribute("aria-label")))
      .toEqual([
        "Evidence 1 of 6 from Business Model Economics",
        "Evidence 2 of 6 from Business Model Economics",
        "Evidence 3 of 6 from Business Model Economics",
        "Evidence 4 of 6 from Business Model Economics",
        "Evidence 5 of 6 from Business Model Economics",
      ]);
    expect(within(firstCard).getByText("Business Model Economics")).toBeVisible();
    expect(within(firstCard).getByText("business model assessment")).toBeVisible();
    expect(within(firstCard).getByText("positive")).toBeVisible();
    expect(within(firstCard).getByText(/inputs\/wiki/)).not.toBeVisible();
    expect(within(firstCard).getByRole("group", { name: "Source details: Business Model Economics" })).toBeInTheDocument();

    await user.click(within(firstCard).getByText("Source details"));
    expect(within(firstCard).getByText("talk:c1eoWu8QVIU")).toBeVisible();
    expect(within(firstCard).getByText(/inputs\/wiki/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Next evidence page" }));
    expect(await screen.findByText("Clean evidence 6")).toBeVisible();
    expect(screen.getByText("Showing 6–6 of 6")).toBeVisible();
    expect(memory).toHaveBeenLastCalledWith("charles", "founder_conviction", 2, 5);
    expect(screen.getByRole("button", { name: "Next evidence page" })).toBeDisabled();
  });

  it("resets to page one when the submitted query changes", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    const result = { evidence_id: "e-1", source_kind: "wiki", excerpt: "Evidence", source_path: "wiki/evidence.md" };
    const memory = vi.spyOn(api, "memory").mockImplementation(async (_slug, _query, page) => ({
      results: [result], page, page_size: 5, total_results: 6, total_pages: 2,
    }));
    const user = userEvent.setup();

    renderProfile();
    await user.click(await screen.findByRole("button", { name: "Find evidence for Founder conviction" }));
    await user.click(await screen.findByRole("button", { name: "Next evidence page" }));
    await vi.waitFor(() => expect(memory).toHaveBeenLastCalledWith("charles", "founder_conviction", 2, 5));

    const input = screen.getByRole("textbox", { name: "Search investment memory" });
    await user.clear(input);
    await user.type(input, "portfolio conflict");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await vi.waitFor(() => expect(memory).toHaveBeenLastCalledWith("charles", "portfolio conflict", 1, 5));
  });

  it("keeps the current evidence page visible when the next page fails and retries", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    let pageTwoAttempts = 0;
    vi.spyOn(api, "memory").mockImplementation(async (_slug, _query, page) => {
      if (page === 2) {
        pageTwoAttempts += 1;
        if (pageTwoAttempts === 1) throw new Error("page unavailable");
        return {
          results: [{ evidence_id: "e-6", source_kind: "wiki", excerpt: "Recovered page two", source_path: "wiki/page-two.md" }],
          page: 2, page_size: 5, total_results: 6, total_pages: 2,
        };
      }
      return {
        results: [{ evidence_id: "e-1", source_kind: "wiki", excerpt: "Stable page one", source_path: "wiki/page-one.md" }],
        page: 1, page_size: 5, total_results: 6, total_pages: 2,
      };
    });
    const user = userEvent.setup();

    renderProfile();
    await user.click(await screen.findByRole("button", { name: "Find evidence for Founder conviction" }));
    expect(await screen.findByText("Stable page one")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Next evidence page" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/page unavailable/i);
    expect(screen.getByText("Stable page one")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry memory search" }));
    expect(await screen.findByText("Recovered page two")).toBeVisible();
  });

  it("renders a legacy unpaginated result with a friendly source fallback", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    vi.spyOn(api, "memory").mockResolvedValue({
      results: [{
        evidence_id: "legacy-1",
        source_kind: "wiki",
        excerpt: "Legacy evidence remains available.",
        source_path: "inputs/wiki/charles/founder_conviction.md",
      }],
    });
    const user = userEvent.setup();

    renderProfile();
    await user.click(await screen.findByRole("button", { name: "Find evidence for Founder conviction" }));

    expect(await screen.findByRole("article", { name: "Evidence 1 of 1 from Founder Conviction" })).toBeVisible();
    expect(screen.getByText("Showing 1–1 of 1")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Next evidence page" })).not.toBeInTheDocument();
  });

  it("does not carry a selected rationale query into a newly navigated investor", async () => {
    vi.spyOn(api, "profile").mockImplementation(async (slug) => ({
      ...profile,
      investor: { ...profile.investor, vc_slug: slug, display_name: slug === "alice" ? "Alice Investor" : profile.investor.display_name },
    }));
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    const memory = vi.spyOn(api, "memory").mockResolvedValue({ results: [] });
    const user = userEvent.setup();

    renderProfile({ showInvestorSwitch: true });
    await user.click(await screen.findByRole("button", { name: "Find evidence for Founder conviction" }));
    await vi.waitFor(() => expect(memory).toHaveBeenCalledWith("charles", "founder_conviction", 1, 5));
    await user.click(screen.getByRole("link", { name: "Open Alice profile" }));

    expect(await screen.findByRole("heading", { name: "Alice Investor" })).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Search investment memory" })).toHaveValue("");
    expect(memory).not.toHaveBeenCalledWith("alice", "founder_conviction");
    expect(memory).toHaveBeenCalledTimes(1);
  });

  it("keeps profile content available when the decision graph fails", async () => {
    vi.spyOn(api, "profile").mockResolvedValue(profile);
    vi.spyOn(api, "profileGraph").mockRejectedValue(new Error("graph unavailable"));
    vi.spyOn(api, "memory").mockResolvedValue({ results: [] });

    renderProfile();

    expect(await screen.findByRole("heading", { name: "Charles Hudson-like Investor" })).toBeVisible();
    expect(screen.getByText("Early conviction is the heart of this chapter.")).toBeVisible();
    expect(screen.getByText(/decision signature is unavailable/i)).toBeVisible();
    expect(screen.getByRole("button", { name: /retry decision signature/i })).toBeVisible();
  });

  it("derives a non-empty preview and metadata for older profile payloads", async () => {
    const legacy: Profile = {
      ...profile,
      sections: [{
        section_id: "legacy",
        title: "Legacy Chapter",
        body: "Legacy complete body that predates preview metadata.",
        source_paths: [],
      }],
    };
    vi.spyOn(api, "profile").mockResolvedValue(legacy);
    vi.spyOn(api, "profileGraph").mockResolvedValue(graph);
    vi.spyOn(api, "memory").mockResolvedValue({ results: [] });

    renderProfile();

    const chapter = await screen.findByRole("article", { name: "Investment Memory chapter: Legacy Chapter" });
    expect(within(chapter).getAllByText("Legacy complete body that predates preview metadata.").some((element) => element.classList.contains("memory-reader-preview"))).toBe(true);
    expect(within(chapter).getByText("52 characters · 0 sources")).toBeVisible();
  });
});
