import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:8766",
    headless: true,
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
    screenshot: "only-on-failure",
  },
  webServer: {
    command:
      "cd ../.. && PUBLISHER_ORIGIN=http://127.0.0.1:8766 python -m uvicorn publisher.tests.browser_app:app --host 127.0.0.1 --port 8766",
    url: "http://127.0.0.1:8766/healthz",
    reuseExistingServer: false,
  },
});
