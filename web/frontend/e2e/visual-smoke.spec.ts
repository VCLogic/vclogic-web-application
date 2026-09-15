import { expect, test, type Page } from "@playwright/test";

type GalleryGeometry = {
  cardCount: number;
  summaryCount: number;
  influenceSectionCount: number;
  influenceRowCount: number;
  maxCardHeight: number;
  cardsFitContent: boolean;
  actionsInFlow: boolean;
  influencesFitWidth: boolean;
  influenceRowsClearActions: boolean;
};

async function galleryGeometry(page: Page): Promise<GalleryGeometry> {
  return page.evaluate(() => {
    const cards = [...document.querySelectorAll<HTMLElement>(".investor-preview")];
    const summaries = [...document.querySelectorAll<HTMLElement>(".investor-preview .decision-influence-summary")];
    const influenceRows = [...document.querySelectorAll<HTMLElement>(".investor-preview .decision-influence-row")];
    const tolerance = 1;
    return {
      cardCount: cards.length,
      summaryCount: summaries.length,
      influenceSectionCount: document.querySelectorAll(".investor-preview .investor-influences").length,
      influenceRowCount: influenceRows.length,
      maxCardHeight: Math.max(0, ...cards.map(card => card.getBoundingClientRect().height)),
      cardsFitContent: cards.every(card => card.scrollHeight <= card.clientHeight + tolerance),
      actionsInFlow: cards.every(card => {
        const actions = card.querySelector<HTMLElement>(".card-actions");
        if (!actions) return false;
        const cardRect = card.getBoundingClientRect();
        const body = actions.closest<HTMLElement>(".preview-body");
        const bodyRect = body?.getBoundingClientRect();
        const actionsRect = actions.getBoundingClientRect();
        const position = getComputedStyle(actions).position;
        return (position === "static" || position === "relative") && body?.parentElement === card && bodyRect !== undefined &&
          actionsRect.top >= bodyRect.top - tolerance && actionsRect.bottom <= bodyRect.bottom + tolerance &&
          actionsRect.top >= cardRect.top - tolerance && actionsRect.bottom <= cardRect.bottom + tolerance &&
          card.contains(actions);
      }),
      influencesFitWidth: summaries.every(summary => summary.scrollWidth <= summary.clientWidth + tolerance),
      influenceRowsClearActions: summaries.every(summary => {
        const rows = [...summary.querySelectorAll<HTMLElement>(".decision-influence-row")];
        const card = summary.closest<HTMLElement>(".investor-preview");
        const actions = card?.querySelector<HTMLElement>(".card-actions");
        if (!rows.length || !actions) return false;
        const summaryRect = summary.getBoundingClientRect();
        const actionsRect = actions.getBoundingClientRect();
        return rows.every(row => row.getBoundingClientRect().bottom <= summaryRect.bottom + tolerance) &&
          Math.max(...rows.map(row => row.getBoundingClientRect().bottom)) <= actionsRect.top + tolerance;
      }),
    };
  });
}

async function documentOverflow(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

test("InvestorLens brand lockup and favicon remain usable", async ({ page }, testInfo) => {
  await page.setViewportSize(testInfo.project.name === "mobile"
    ? { width: 390, height: 844 }
    : { width: 1347, height: 900 });
  const favicon = await page.request.get("/favicon.svg");
  expect(favicon.ok()).toBe(true);
  expect(favicon.headers()["content-type"]).toContain("image/svg+xml");
  await page.goto("/");
  const home = page.getByRole("link", { name: "InvestorLens home" });
  await expect(home).toBeVisible();
  await expect(home.locator("svg.investor-lens-mark")).toBeVisible();
  const geometry = await page.locator(".app-header").evaluate((header) => {
    const mark = header.querySelector<SVGElement>(".investor-lens-mark")!;
    const wordmark = header.querySelector<HTMLElement>(".wordmark")!;
    return {
      overflow: header.scrollWidth - header.clientWidth,
      markWidth: mark.getBoundingClientRect().width,
      linkTop: wordmark.getBoundingClientRect().top,
      linkBottom: wordmark.getBoundingClientRect().bottom,
      headerTop: header.getBoundingClientRect().top,
      headerBottom: header.getBoundingClientRect().bottom,
    };
  });
  expect(geometry.overflow).toBeLessThanOrEqual(1);
  expect(geometry.markWidth).toBeGreaterThanOrEqual(24);
  expect(geometry.linkTop).toBeGreaterThanOrEqual(geometry.headerTop);
  expect(geometry.linkBottom).toBeLessThanOrEqual(geometry.headerBottom);
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);
});

test("saved assessment dossiers remain compact and non-overlapping", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop dossier geometry contract");
  await page.goto("/pitches/3ad36328-5465-474c-965b-46120ae3e186/versions/19bbfb20-c2c3-4d88-b5af-94b56e228fe7?tab=assessments");
  const dossiers = page.locator(".assessment-dossier.complete");
  await expect(dossiers.first()).toBeVisible();
  expect(await dossiers.count()).toBeGreaterThanOrEqual(3);
  await expect(dossiers.first().getByText("Full model analysis")).toBeVisible();
  const geometry = await dossiers.evaluateAll((rows) => rows.map((row) => {
    const summary = row.querySelector<HTMLElement>(".dossier-summary")!;
    const verdict = row.querySelector<HTMLElement>(".dossier-verdict")!;
    const verdictLabel = verdict.querySelector<HTMLElement>(":scope > strong")!;
    const verdictMetrics = verdict.querySelector<HTMLElement>(":scope > dl")!;
    const metricLabel = verdictMetrics.querySelector<HTMLElement>("dt")!;
    const metricValue = verdictMetrics.querySelector<HTMLElement>("dd")!;
    const metricHelp = verdictMetrics.querySelector<HTMLElement>(".metric-help")!;
    const signals = row.querySelector<HTMLElement>(".dossier-signal-grid")!;
    const rationaleTag = signals.querySelector<HTMLElement>(".dossier-rationales strong")!;
    const evidence = row.querySelector<HTMLElement>(".key-evidence")!;
    const actions = row.querySelector<HTMLElement>(".dossier-actions")!;
    const ordered = [verdict, summary, signals, evidence, actions].map(element => element.getBoundingClientRect());
    return {
      display: getComputedStyle(row).display,
      ordered: ordered.every((rect, index) => index === 0 || rect.top >= ordered[index - 1].bottom - 1),
      verdictContentSeparated: verdictLabel.getBoundingClientRect().right <= verdictMetrics.getBoundingClientRect().left - 1,
      verdictLabelFits: verdictLabel.scrollWidth <= verdictLabel.clientWidth + 1,
      verdictTopAligned: Math.abs(verdictLabel.getBoundingClientRect().top - verdictMetrics.getBoundingClientRect().top) <= 1,
      verdictToMetricRatio: parseFloat(getComputedStyle(verdictLabel).fontSize) / parseFloat(getComputedStyle(metricValue).fontSize),
      metricLabelFontSize: parseFloat(getComputedStyle(metricLabel).fontSize),
      metricHelpFontSize: parseFloat(getComputedStyle(metricHelp).fontSize),
      rationaleTagFontSize: parseFloat(getComputedStyle(rationaleTag).fontSize),
      overflow: row.scrollWidth - row.clientWidth,
      height: row.getBoundingClientRect().height,
    };
  }));
  expect(geometry.every(row => row.display === "block")).toBe(true);
  expect(geometry.every(row => row.ordered)).toBe(true);
  expect(geometry.every(row => row.verdictContentSeparated)).toBe(true);
  expect(geometry.filter(row => !row.verdictLabelFits)).toEqual([]);
  expect(geometry.every(row => row.verdictTopAligned)).toBe(true);
  expect(geometry.every(row => row.verdictToMetricRatio >= 1.4 && row.verdictToMetricRatio <= 2.25)).toBe(true);
  expect(geometry.every(row => row.metricLabelFontSize >= 11)).toBe(true);
  expect(geometry.every(row => row.metricHelpFontSize >= 11)).toBe(true);
  expect(geometry.every(row => row.rationaleTagFontSize >= 12)).toBe(true);
  expect(geometry.every(row => row.overflow <= 1)).toBe(true);
  expect(geometry.every(row => row.height < 1150)).toBe(true);
});

test("investor gallery is portrait-led and responsive", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /different investment lens/i })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("img").first()).toBeVisible();
  await expect(page.getByText("Investor-like simulation").first()).toBeVisible();
  await expect(page.locator(".investor-preview")).toBeVisible();
  // Fresh checkouts have no archived assessments; recurrence sections are optional.
  await expect(page.locator(".investor-preview .investor-summary")).not.toBeEmpty();
  const geometry = await galleryGeometry(page);
  expect(geometry.cardCount).toBeGreaterThan(0);
  expect(geometry.summaryCount).toBe(geometry.influenceSectionCount);
  expect(geometry.influenceRowCount).toBeGreaterThanOrEqual(geometry.summaryCount);
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);
});

test("investor gallery cards preserve intrinsic content at 1347px and enlarged text", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "1347px geometry contract");
  await page.setViewportSize({ width: 1347, height: 1000 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /different investment lens/i })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("img").first()).toBeVisible();
  await expect(page.getByText("Investor-like simulation").first()).toBeVisible();
  await expect(page.locator(".investor-preview")).toBeVisible();

  const defaultGeometry = await galleryGeometry(page);
  expect(defaultGeometry.cardCount).toBeGreaterThan(0);
  expect(defaultGeometry.summaryCount).toBe(defaultGeometry.influenceSectionCount);
  expect(defaultGeometry.influenceRowCount).toBeGreaterThanOrEqual(defaultGeometry.summaryCount);
  expect(defaultGeometry.maxCardHeight).toBeLessThanOrEqual(760);
  expect(defaultGeometry.influencesFitWidth).toBe(true);
  expect(defaultGeometry.influenceRowsClearActions).toBe(true);
  expect(defaultGeometry.cardsFitContent).toBe(true);
  expect(defaultGeometry.actionsInFlow).toBe(true);
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);

  await page.locator("html").evaluate(element => { element.style.fontSize = "24px"; });
  const enlargedGeometry = await galleryGeometry(page);
  expect(enlargedGeometry.cardCount).toBe(defaultGeometry.cardCount);
  expect(enlargedGeometry.summaryCount).toBe(enlargedGeometry.influenceSectionCount);
  expect(enlargedGeometry.influenceRowCount).toBeGreaterThanOrEqual(enlargedGeometry.summaryCount);
  expect(enlargedGeometry.influencesFitWidth).toBe(true);
  expect(enlargedGeometry.influenceRowsClearActions).toBe(true);
  expect(enlargedGeometry.cardsFitContent).toBe(true);
  expect(enlargedGeometry.actionsInFlow).toBe(true);
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);
});

test("investor dossier makes the decision signature and one memory chapter legible on desktop", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "1347px profile contract");
  await page.setViewportSize({ width: 1347, height: 1000 });
  await page.goto("/profiles/charles-hudson-precursor-ventures");
  await expect(page.getByRole("heading", { name: "Charles Hudson-like Investor" })).toBeVisible();
  await expect(page.getByRole("link", { name: /photo: the pitch/i })).toBeVisible();
  const designSystem = await page.evaluate(() => {
    const root = document.querySelector<HTMLElement>(".profile-dossier")!;
    const main = document.querySelector<HTMLElement>("main")!;
    const masthead = document.querySelector<HTMLElement>(".dossier-masthead")!;
    const signature = document.querySelector<HTMLElement>(".signature-groups")!;
    const memory = document.querySelector<HTMLElement>(".memory-library-layout")!;
    const action = document.querySelector<HTMLElement>(".dossier-primary-action")!;
    const rootStyles = getComputedStyle(document.documentElement);
    return {
      pageBackground: getComputedStyle(root).backgroundColor,
      sharedPageBackground: getComputedStyle(document.body).backgroundColor,
      rootLeft: root.getBoundingClientRect().left,
      mainLeft: main.getBoundingClientRect().left,
      mastheadRadius: parseFloat(getComputedStyle(masthead).borderRadius),
      signatureOverflow: signature.scrollWidth - signature.clientWidth,
      memoryRadius: parseFloat(getComputedStyle(memory).borderRadius),
      actionBackground: getComputedStyle(action).backgroundColor,
      sharedActionBackground: rootStyles.getPropertyValue("--signal-indigo").trim(),
    };
  });
  expect(designSystem.pageBackground).toBe(designSystem.sharedPageBackground);
  expect(designSystem.rootLeft).toBeGreaterThanOrEqual(designSystem.mainLeft - 1);
  expect(designSystem.mastheadRadius).toBeLessThanOrEqual(8);
  expect(designSystem.signatureOverflow).toBeLessThanOrEqual(1);
  expect(designSystem.memoryRadius).toBeLessThanOrEqual(8);
  expect(designSystem.actionBackground).toBe("rgb(54, 93, 72)");
  expect(designSystem.sharedActionBackground).toBe("#365d48");
  await expect(page.getByRole("heading", { name: "Decision Signature" })).toBeVisible();
  await expect(page.locator(".react-flow")).toHaveCount(0);
  await expect(page.getByLabel("Decision logic visualization")).toHaveCount(0);
  const signatureGroups = page.locator(".signature-group");
  await expect(signatureGroups).toHaveCount(3);
  const rationaleCards = page.locator(".signature-rationale");
  expect(await rationaleCards.count()).toBeGreaterThan(0);
  const pairs = page.getByRole("region", { name: "Often considered together" });
  await expect(pairs).toBeVisible();
  await expect(pairs).toContainText(/co-occurrence, not cause and effect/i);
  const memoryReaders = page.locator(".memory-reader");
  await expect(memoryReaders).toHaveCount(1);
  await expect(memoryReaders.locator("details").first()).not.toHaveAttribute("open", "");
  const chapterButtons = page.locator(".memory-index-desktop .memory-index-group button");
  expect(await chapterButtons.count()).toBeGreaterThan(0);
  const initialChapterTitle = await memoryReaders.getByRole("heading").textContent();
  await chapterButtons.nth(1).click();
  await expect(memoryReaders).toHaveCount(1);
  await expect(memoryReaders.getByRole("heading")).not.toHaveText(initialChapterTitle ?? "");
  const initialDocument = await page.evaluate(() => ({
    scrollHeight: document.documentElement.scrollHeight,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));
  expect(initialDocument.scrollHeight).toBeLessThan(3000);
  expect(initialDocument.overflow).toBeLessThanOrEqual(1);
  await page.getByText(/Browse all \d+ rationales/i).click();
  const inventory = page.locator(".signature-inventory table");
  await expect(inventory).toBeVisible();
  await expect(inventory.getByRole("row")).toHaveCount(43);
  const memorySearch = page.getByRole("region", { name: "Search the Investment Memory" });
  await memorySearch.getByRole("textbox", { name: "Search investment memory" }).fill("founder");
  await memorySearch.getByRole("button", { name: "Search" }).click();
  await expect(memorySearch.getByText(/Showing 1–5 of/)).toBeVisible();
  await expect(memorySearch.locator(".memory-result")).toHaveCount(5);
  await expect(memorySearch.locator(".memory-result details").first()).not.toHaveAttribute("open", "");
  const memoryGeometry = await memorySearch.evaluate((section) => {
    const results = section.querySelector<HTMLElement>(".memory-results");
    return {
      display: results ? getComputedStyle(results).display : "missing",
      overflow: section.scrollWidth - section.clientWidth,
      cardsFit: [...section.querySelectorAll<HTMLElement>(".memory-result")]
        .every((card) => card.scrollWidth <= card.clientWidth + 1),
    };
  });
  expect(memoryGeometry.display).toBe("grid");
  expect(memoryGeometry.overflow).toBeLessThanOrEqual(1);
  expect(memoryGeometry.cardsFit).toBe(true);
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);

  await page.locator("html").evaluate((element) => { element.style.fontSize = "24px"; });
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);
  for (const selector of [".dossier-masthead", ".signature-groups", ".memory-library-layout"]) {
    const region = page.locator(selector);
    await expect(region).toBeVisible();
    expect(await region.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
  }
});

test("investor dossier uses a compact decision signature and chapter controls on mobile", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "390px profile contract");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/profiles/charles-hudson-precursor-ventures");
  await expect(page.getByRole("heading", { name: "Charles Hudson-like Investor" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Decision Signature" })).toBeVisible();
  await expect(page.locator(".signature-group")).toHaveCount(3);
  await expect(page.locator(".react-flow")).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Choose Investment Memory chapter" })).toBeVisible();
  await expect(page.locator(".memory-index-desktop")).not.toBeVisible();
  await expect(page.locator(".memory-reader")).toHaveCount(1);
  const memorySearch = page.getByRole("region", { name: "Search the Investment Memory" });
  await memorySearch.getByRole("textbox", { name: "Search investment memory" }).fill("founder");
  await memorySearch.getByRole("button", { name: "Search" }).click();
  await expect(memorySearch.locator(".memory-result").first()).toBeVisible();
  expect(await memorySearch.evaluate((section) => section.scrollWidth - section.clientWidth)).toBeLessThanOrEqual(1);
  for (const card of await memorySearch.locator(".memory-result").all()) {
    expect(await card.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
  }
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);
});

test("investor dossier remains compact and complete at 768px", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "768px tablet profile contract");
  await page.setViewportSize({ width: 768, height: 900 });
  await page.goto("/profiles/charles-hudson-precursor-ventures");
  await expect(page.getByRole("heading", { name: "Charles Hudson-like Investor" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Decision Signature" })).toBeVisible();
  await expect(page.locator(".signature-group")).toHaveCount(3);
  await expect(page.locator(".memory-reader")).toHaveCount(1);
  await expect(page.locator(".react-flow")).toHaveCount(0);
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);
});

test("pitch briefing preserves investor context and usable editor geometry", async ({ page }, testInfo) => {
  await page.goto("/profiles/charles-hudson-precursor-ventures");
  await expect(page.getByRole("heading", { name: "Charles Hudson-like Investor" })).toBeVisible();
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);
  await page.getByRole("link", { name: /assess your pitch/i }).click();
  await expect(page.getByRole("heading", { name: /assess your pitch/i })).toBeVisible();
  await page.getByRole("tab", { name: /create a new pitch/i }).click();
  await expect(page.getByRole("heading", { name: /create a new pitch/i })).toBeVisible();
  if (testInfo.project.name === "desktop") {
    await expect(page.locator(".identity-photo")).toBeVisible();
    await expect(page.locator(".identity-rail .decision-influence-summary")).toBeVisible();
  } else {
    await expect(page.locator(".identity-rail")).toBeHidden();
  }
  const intakeGeometry = await page.evaluate(() => {
    const rail = document.querySelector<HTMLElement>(".identity-rail");
    const portrait = document.querySelector<HTMLElement>(".identity-photo");
    const editor = document.querySelector<HTMLTextAreaElement>(".new-pitch-choice textarea");
    const summaries = [...document.querySelectorAll<HTMLElement>(".identity-rail .decision-influence-summary")];
    return {
      viewportWidth: document.documentElement.clientWidth,
      railWidth: rail?.getBoundingClientRect().width ?? 0,
      portraitWidth: portrait?.getBoundingClientRect().width ?? 0,
      portraitHeight: portrait?.getBoundingClientRect().height ?? 0,
      editorWidth: editor?.getBoundingClientRect().width ?? 0,
      editorClientHeight: editor?.clientHeight ?? 0,
      influencesFitWidth: summaries.every(summary => summary.scrollWidth <= summary.clientWidth + 1),
    };
  });
  if (testInfo.project.name === "desktop") {
    expect(intakeGeometry.railWidth).toBeGreaterThan(Math.min(250, intakeGeometry.viewportWidth * 0.6));
    expect(intakeGeometry.portraitWidth).toBeGreaterThan(Math.min(250, intakeGeometry.viewportWidth * 0.6));
    expect(intakeGeometry.portraitHeight).toBeGreaterThan(180);
  } else {
    expect(intakeGeometry.railWidth).toBe(0);
  }
  expect(intakeGeometry.editorWidth).toBeGreaterThan(Math.min(500, intakeGeometry.viewportWidth * 0.6));
  expect(intakeGeometry.editorClientHeight).toBeGreaterThanOrEqual(278);
  expect(intakeGeometry.influencesFitWidth).toBe(true);
  expect(await documentOverflow(page)).toBeLessThanOrEqual(1);
});

test("active rehearsal stays focused on the rationale-backed conversation", async ({ page }) => {
  await page.route("**/api/sessions/demo/events", route => route.fulfill({ status: 200, contentType: "text/event-stream", body: "" }));
  await page.route("**/api/investors/charles-hudson-precursor-ventures", route => route.fulfill({ json: {
    investor: { vc_slug: "charles-hudson-precursor-ventures", display_name: "Charles Hudson-like Investor", firm: "Precursor Ventures", role: "Founder and Managing Partner", disclosure: "Simulation; not endorsed.", start_available: true, portrait_path: "/investors/charles-hudson-precursor-ventures.jpg", portrait_alt: "Charles Hudson portrait", recurring_positive_rationales: [], recurring_negative_rationales: [] }, sections: [],
  } }));
  await page.route("**/api/sessions/demo", route => route.fulfill({ json: {
    session_id: "demo", vc_slug: "charles-hudson-precursor-ventures", investor_display_name: "Charles Hudson-like Investor", disclosure: "Simulation reconstructed from public traces; not the real investor and not endorsed by them.", status: "awaiting_answer", rehearsal_depth: "standard", pitch_text: "We have ten paying customers and a growing qualified pipeline, but retention is not yet established.", pitch_sha256: "demo", initial_assessment: { decision: "Out", investment_likelihood: .4, decision_confidence: .7, rationale_counts: { negative: 1 }, decision_justification: "Retention remains unresolved." }, current_assessment: { decision: "Out", investment_likelihood: .52, decision_confidence: .72, review_priority_score: .64, rationale_counts: { positive: 1, negative: 1 }, decision_justification: "Customer evidence improved the case, while repeat behavior remains unclear." }, active_question: { question_id: "q2", text: "How many customers have renewed or expanded?", response_comment: "Ten paying customers is a start; now I need to understand whether they stay.", rationale_labels: ["traction_validation"], decision_relevance: "Repeat behavior could materially change the decision." }, conversation: [{ question_id: "q1", question: "Who is using the product today?", response_comment: "Let’s begin with customer evidence.", rationale_labels: ["customer_validation"], founder_answer: "Ten customers currently pay for the product." }], max_questions: 5, turns: [{ text: "Ten customers currently pay for the product." }], annotations: [{ annotation_id: "a1", start: 8, end: 28, text: "ten paying customers", direction: "positive", rationale_ids: ["traction_validation"], evidence_ids: ["e1"] }], evidence: [{ evidence_id: "e1", source_kind: "pitch", source_path: "pitch.txt", excerpt: "ten paying customers" }], rationale_graph: { nodes: [{ node_id: "traction", taxonomy_label: "traction_validation", title: "Traction Validation", direction: "positive", salience: "primary", confidence: .78, evidence_ids: ["e1"] }, { node_id: "retention", taxonomy_label: "retention_quality", title: "Retention Quality", direction: "unresolved", salience: "unresolved", confidence: .62, evidence_ids: [] }], edges: [] }, usage: {}, findings: [],
  } }));
  await page.goto("/sessions/demo");
  await expect(page.getByRole("heading", { name: "Founder rehearsal" })).toBeVisible();
  await expect(page.getByText("Ten paying customers is a start; now I need to understand whether they stay.")).toBeVisible();
  await expect(page.getByText("How many customers have renewed or expanded?")).toBeVisible();
  await expect(page.getByText("Question 2 · Standard rehearsal")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Your answer" })).toBeVisible();
  await expect(page.getByText("Initial assessment")).toHaveCount(0);
  await expect(page.getByText("Current assessment")).toHaveCount(0);
  await expect(page.getByRole("tablist", { name: "Rehearsal views" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Pitch & evidence" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
