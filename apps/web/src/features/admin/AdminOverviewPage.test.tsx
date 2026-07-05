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

test("renders admin action links and live service status", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "available",
          scope: "admin-overview",
          userId: "admin-user",
        }),
    }),
  );

  renderWithProviders(<AdminOverviewPage />, "/admin/overview");

  expect(await screen.findByRole("heading", { name: "Available" })).toBeVisible();
  expect(screen.getByRole("link", { name: /Access groups/ })).toHaveAttribute(
    "href",
    "/admin/acgs",
  );
  expect(screen.getByRole("link", { name: /Audit log/ })).toHaveAttribute("href", "/audit");
});
