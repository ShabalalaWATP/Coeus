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
              provider: "mock",
              activeModel: "gemma-4-31b",
              availableModels: ["gemma-4-31b", "gemini-2.5-pro"],
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
  expect(await screen.findByRole("radio", { name: /gemma-4-31b/ })).toBeChecked();
  expect(await screen.findByText("No pending access requests")).toBeVisible();
  expect(screen.getByRole("link", { name: /Access groups/ })).toHaveAttribute(
    "href",
    "/admin/acgs",
  );
  expect(screen.getByRole("link", { name: /Users/ })).toHaveAttribute("href", "/admin/users");
  expect(screen.getByRole("link", { name: /Audit log/ })).toHaveAttribute("href", "/audit");
});
