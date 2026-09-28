import { afterEach, expect, it, vi } from "vitest";
import { api } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("turns FastAPI validation details into a readable API error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    detail: [{
      type: "extra_forbidden",
      loc: ["body", "rehearsal_depth"],
      msg: "Extra inputs are not permitted",
      input: "standard",
    }],
  }), {
    status: 422,
    headers: { "Content-Type": "application/json" },
  })));

  const result = api.createSession({
    vc_slug: "elizabeth-yin-hustle-fund",
    company_aliases: ["ShiftPilot"],
    pitch_text: "Founder pitch",
    authorize_provider_cost: true,
    rehearsal_depth: "standard",
  });

  await expect(result).rejects.toMatchObject({
    status: 422,
    message: "Rehearsal depth: Extra inputs are not permitted",
  });
});


it("requests specifications for an explicit version or the active version", async () => {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response("{}", {status:200})));
  vi.stubGlobal("fetch", fetch);
  const version = "a".repeat(64);
  await api.investorSpecifications("example vc", version);
  expect(fetch.mock.calls[0][0]).toBe(`/api/settings/investors/example%20vc/specifications?version=${version}`);
  await api.investorSpecifications("example");
  expect(fetch.mock.calls[1][0]).toBe("/api/settings/investors/example/specifications");
  expect(fetch.mock.calls[0][1].method).toBeUndefined();
});
