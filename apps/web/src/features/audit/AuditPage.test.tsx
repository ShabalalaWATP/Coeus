import { screen } from "@testing-library/react";

import AuditPage from "./AuditPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders audit events from the API", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          events: [
            {
              eventId: "event-1",
              eventType: "login_success",
              occurredAt: "2026-07-05T22:00:00Z",
              actorUserId: "admin-user",
              metadata: { username: "admin@example.test" },
            },
          ],
        }),
    }),
  );

  renderWithProviders(<AuditPage />, "/audit");

  expect(await screen.findByRole("heading", { name: "Audit" })).toBeVisible();
  expect(await screen.findByText("login_success")).toBeVisible();
  expect(screen.getByText("admin-user")).toBeVisible();
});

test("renders empty audit logs", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ events: [] }),
    }),
  );

  renderWithProviders(<AuditPage />, "/audit");

  expect(await screen.findByText("No audit events recorded.")).toBeVisible();
});

test("renders system audit actors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          events: [
            {
              eventId: "event-system",
              eventType: "system_start",
              occurredAt: "2026-07-05T22:00:00Z",
              actorUserId: null,
              metadata: {},
            },
          ],
        }),
    }),
  );

  renderWithProviders(<AuditPage />, "/audit");

  expect(await screen.findByText("system_start")).toBeVisible();
  expect(screen.getByText("system")).toBeVisible();
});
