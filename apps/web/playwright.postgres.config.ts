import { defineConfig, devices } from "@playwright/test";

const databaseUrl = process.env.COEUS_PLAYWRIGHT_DATABASE_URL;
if (!databaseUrl) {
  throw new Error("COEUS_PLAYWRIGHT_DATABASE_URL is required");
}

export default defineConfig({
  testDir: "./tests/e2e-postgres",
  timeout: 300_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  use: {
    actionTimeout: 10_000,
    baseURL: "http://127.0.0.1:5194",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "uv run --directory ../api uvicorn coeus.main:app --host 127.0.0.1 --port 8022 --workers 1",
      env: {
        COEUS_ALLOWED_CORS_ORIGINS: '["http://127.0.0.1:5194"]',
        COEUS_ARGON2_MEMORY_COST: "8192",
        COEUS_DATABASE_URL: databaseUrl,
        COEUS_ENVIRONMENT: "test",
        COEUS_LOCAL_OBJECT_STORAGE_PATH: "../api/.local-data/playwright-postgres-objects",
        COEUS_OBJECT_STORAGE_PROVIDER: "local",
        COEUS_PERSISTENCE_PROVIDER: "postgres",
        COEUS_SEED_DEMO_CONTENT: "false",
        COEUS_TICKET_PERSISTENCE_MODE: "relational",
      },
      reuseExistingServer: false,
      timeout: 120_000,
      url: "http://127.0.0.1:8022/api/v1/health/live",
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5194 --strictPort",
      env: { VITE_API_BASE_URL: "http://127.0.0.1:8022" },
      reuseExistingServer: false,
      timeout: 120_000,
      url: "http://127.0.0.1:5194",
    },
  ],
  projects: [{ name: "chromium-postgres", use: { ...devices["Desktop Chrome"] } }],
});
