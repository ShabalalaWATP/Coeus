import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: "http://127.0.0.1:5183",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command:
        "uv run --directory ../api uvicorn coeus.main:app --host 127.0.0.1 --port 8011 --workers 1",
      env: {
        COEUS_ALLOWED_CORS_ORIGINS: '["http://127.0.0.1:5183"]',
        COEUS_ARGON2_MEMORY_COST: "8192",
        COEUS_ENVIRONMENT: "test",
        COEUS_LOCAL_OBJECT_STORAGE_PATH: "../api/.local-data/playwright-objects",
        COEUS_PERSISTENCE_PROVIDER: "memory",
      },
      reuseExistingServer: false,
      timeout: 120_000,
      url: "http://127.0.0.1:8011/api/v1/health/live",
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5183 --strictPort",
      env: { VITE_API_BASE_URL: "http://127.0.0.1:8011" },
      reuseExistingServer: false,
      timeout: 120_000,
      url: "http://127.0.0.1:5183",
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
