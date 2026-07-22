import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AdminOverviewPage from "./AdminOverviewPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders admin action links, approvals and AI model controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/admin/registrations")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ registrations: [] }) });
      }
      if (url.includes("/admin/ai-model")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              provider: "gemini_api",
              activeModel: "gemma-4-31b-it",
              availableModels: ["gemma-4-31b-it", "gemini-3.1-pro-preview"],
              providers: [
                {
                  name: "gemini_api",
                  label: "Gemini API (primary)",
                  models: ["gemma-4-31b-it", "gemini-3.1-pro-preview"],
                  activeModel: "gemma-4-31b-it",
                  apiKeyConfigured: false,
                },
              ],
            }),
        });
      }
      if (url.includes("/admin/search-embeddings")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(searchState),
        });
      }
      if (url.includes("/admin/voice-model")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              model: "gpt-realtime-mini",
              availableModels: ["gpt-realtime-mini"],
              enabled: false,
              apiKeyConfigured: false,
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            status: "available",
            scope: "admin-overview",
            userId: "admin-user",
          }),
      });
    }),
  );

  renderWithProviders(<AdminOverviewPage />, "/admin/overview");

  expect(await screen.findByRole("heading", { name: "Available" })).toBeVisible();
  expect(screen.getByText("Gemini API (primary) active")).toBeVisible();
  expect(screen.getAllByText("No key saved")).toHaveLength(2);
  expect(screen.getByText("Voice disabled")).toBeVisible();
  const aiHeading = screen.getByRole("heading", { name: "AI provider and model" });
  expect(aiHeading.closest("details")).not.toHaveAttribute("open");
  await userEvent.click(aiHeading);
  expect(aiHeading.closest("details")).toHaveAttribute("open");
  expect(await screen.findByRole("radio", { name: /gemma-4-31b-it/ })).toBeChecked();
  await userEvent.click(screen.getByRole("heading", { name: "Access requests" }));
  expect(await screen.findByText("No pending access requests")).toBeVisible();
  expect(screen.getByRole("link", { name: /Access groups/ })).toHaveAttribute(
    "href",
    "/admin/acgs",
  );
  expect(screen.getByRole("link", { name: /Users/ })).toHaveAttribute("href", "/admin/users");
  expect(screen.getByRole("link", { name: /Audit log/ })).toHaveAttribute("href", "/audit");
});

test("shows admin service loading independently of the other controls", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/api/v1/admin/overview")) return new Promise(() => undefined);
      if (url.includes("/registrations"))
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ registrations: [] }) });
      if (url.includes("/voice-model"))
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              model: "gpt-realtime-mini",
              availableModels: ["gpt-realtime-mini"],
              enabled: false,
              apiKeyConfigured: false,
            }),
        });
      if (url.includes("/search-embeddings"))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(searchState) });
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            provider: "mock",
            activeModel: "mock",
            embeddingProvider: "local",
            embeddedProductCount: 0,
            providers: [
              {
                name: "mock",
                label: "Mock",
                models: ["mock"],
                activeModel: "mock",
                apiKeyConfigured: true,
              },
            ],
          }),
      });
    }),
  );

  renderWithProviders(<AdminOverviewPage />, "/admin/overview");
  expect(screen.getByText("Checking admin service status")).toBeVisible();
});

test("retries an unavailable overview and renders fallback health details", async () => {
  let overviewCalls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/api/v1/admin/overview")) {
        overviewCalls += 1;
        return Promise.resolve(
          overviewCalls <= 2
            ? {
                ok: false,
                status: 500,
                json: () =>
                  Promise.resolve({ error: { code: "offline", message: "Unavailable." } }),
              }
            : {
                ok: true,
                json: () => Promise.resolve({ status: "starting", scope: null }),
              },
        );
      }
      if (url.includes("/registrations"))
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ registrations: [] }) });
      if (url.includes("/search-embeddings"))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(searchState) });
      if (url.includes("/voice-model"))
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              model: "gpt-realtime-mini",
              availableModels: ["gpt-realtime-mini"],
              enabled: false,
              apiKeyConfigured: false,
            }),
        });
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            provider: "mock",
            activeModel: "mock",
            embeddingProvider: "local",
            embeddedProductCount: 0,
            providers: [
              {
                name: "mock",
                label: "Mock",
                models: ["mock"],
                activeModel: "mock",
                apiKeyConfigured: true,
              },
            ],
          }),
      });
    }),
  );
  renderWithProviders(<AdminOverviewPage />, "/admin/overview");

  await userEvent.click(await screen.findByRole("button", { name: "Retry" }, { timeout: 3_000 }));
  expect(await screen.findByRole("heading", { name: "Checking status" })).toBeVisible();
  expect(screen.getByText("Admin overview service health.")).toBeVisible();
});

const searchState = {
  provider: "mock",
  model: "token-hash-v2",
  dimensions: 1536,
  apiKeyConfigured: false,
  availableProviders: ["mock", "gemini_api"],
  availableModels: ["token-hash-v2"],
  indexStatus: "stale",
  indexGeneration: 1,
  productCount: 0,
  chunkCount: 0,
  ticketCount: 0,
  failedAssetCount: 0,
  corpusVersion: "unindexed",
  spaceId: "mock:token-hash-v2:1536:g1",
  changedBy: null,
  changedAt: null,
  lastIndexedAt: null,
  degradedReason: null,
  releaseId: "mock:token-hash-v2:1536",
  evaluationStatus: "approved",
  definitiveNoMatchEnabled: true,
};
