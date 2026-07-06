import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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

  expect(await screen.findByText("No audit events recorded")).toBeVisible();
});

test("renders an audit error state with retry", async () => {
  const failure = {
    ok: false,
    status: 500,
    json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(failure)
    .mockResolvedValueOnce(failure)
    .mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ events: [] }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AuditPage />, "/audit");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("No audit events recorded")).toBeVisible();
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
