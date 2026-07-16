import { screen } from "@testing-library/react";

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
      if (url.includes("/admin/voice-model")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              model: "gpt-realtime-2.1-mini",
              availableModels: ["gpt-realtime-2.1-mini"],
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
  expect(await screen.findByRole("radio", { name: /gemma-4-31b-it/ })).toBeChecked();
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
              model: "gpt-realtime-2.1-mini",
              availableModels: ["gpt-realtime-2.1-mini"],
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
  expect(screen.getByText("Checking admin service status")).toBeVisible();
});
