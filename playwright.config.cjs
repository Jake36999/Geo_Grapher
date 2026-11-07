const { defineConfig } = require("@playwright/test");
const path = require("path");
const python = path.join(
  __dirname,
  ".venv",
  process.platform === "win32" ? "Scripts" : "bin",
  process.platform === "win32" ? "python.exe" : "python",
);
module.exports = defineConfig({
  testDir: "tests/browser",
  testMatch: "**/*.spec.cjs",
  workers: 1,
  timeout: 45000,
  expect: { timeout: 8000 },
  outputDir: "output/qa/test-results",
  reporter: [["list"], ["json", { outputFile: "output/qa/results.json" }]],
  use: {
    baseURL: "http://127.0.0.1:8771",
    browserName: "chromium",
    channel: "msedge",
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: '"' + python + '" scripts/qa_server.py',
    url: "http://127.0.0.1:8771/api/v1/bootstrap",
    reuseExistingServer: false,
    timeout: 120000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
