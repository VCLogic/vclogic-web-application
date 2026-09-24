import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  workers: 4,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:8766",
    channel: "chrome",
    headless: true,
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: "cd ../.. && uv run vc-clone-web --pipeline-workspace ../vclogic-vc-agentic-assessment --config configs/rehearsal-charles-v41-grounded.toml --host 127.0.0.1 --port 8766",
    url: "http://127.0.0.1:8766/api/health",
    reuseExistingServer: true,
    // Readiness includes validation of the workspace's large investor indexes.
    timeout: 120_000,
  },
});
