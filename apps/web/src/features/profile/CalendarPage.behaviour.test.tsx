import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import CalendarPage from "./CalendarPage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import type { CalendarMutation } from "../../lib/api-client/workforce-calendar";
import { renderWithProviders } from "../../test/test-utils";

const session: AuthSession = {
  csrfToken: "csrf",
  user: {
    id: "user-1",
    username: "user@example.test",
    displayName: "John McGinn",
    roles: ["Customer"],
    defaultRoute: "/app/requests",
    passwordResetRequired: false,
    permissions: ["user:read_self"],
  },
};
const event = {
  eventId: "event-1",
  ownerUserId: "user-1",
  source: "personal",
  activity: "training",
  timing: {
    timeZone: "Europe/London",
    startsAt: null,
    endsAt: null,
    allDayStart: "2026-08-10",
    allDayEnd: "2026-08-11",
  },
  availability: "partial",
  privacy: "team_summary",
  createdByUserId: "user-1",
  note: "Synthetic course",
  recurrence: null,
  managerScopeUnitId: null,
  status: "active",
  version: 2,
  createdAt: "2026-08-01T10:00:00Z",
  updatedAt: "2026-08-01T10:00:00Z",
  cancelledAt: null,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

function requestBody(init?: RequestInit) {
  return JSON.parse(typeof init?.body === "string" ? init.body : "{}") as CalendarMutation;
}

test("shows and cancels the user's personal activity", async () => {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/calendar/me?"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ events: [event] }) });
    const body = requestBody(init);
    if (url.endsWith("/calendar/previews"))
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ request: body, previewHash: "a".repeat(64) }),
      });
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ eventId: "event-1", version: 3, replayed: false }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<CalendarPage />, "/account/calendar", session);
  expect(await screen.findByText(/Synthetic course/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Remove Training" }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/calendar/previews") && init?.method === "POST",
    );
    expect(requestBody(call?.[1])).toMatchObject({ operation: "cancel", expectedVersion: 2 });
  });
});

test("renders timed and protected events without exposing unavailable detail", async () => {
  const timed = {
    ...event,
    eventId: "manager-event",
    source: "manager",
    activity: "meeting",
    availability: "available",
    note: "",
    timing: {
      timeZone: "Europe/London",
      startsAt: "2026-08-20T09:00:00Z",
      endsAt: "2026-08-20T10:00:00Z",
      allDayStart: null,
      allDayEnd: null,
    },
  };
  const undated = {
    ...event,
    eventId: "undated-event",
    activity: "other",
    note: null,
    timing: {
      timeZone: "Europe/London",
      startsAt: null,
      endsAt: null,
      allDayStart: null,
      allDayEnd: null,
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      url.includes("/calendar/me?")
        ? Promise.resolve({ ok: true, json: () => Promise.resolve({ events: [timed, undated] }) })
        : Promise.resolve({
            ok: false,
            status: 409,
            json: () => Promise.resolve({ error: { code: "conflict", message: "Changed" } }),
          }),
    ),
  );
  renderWithProviders(<CalendarPage />, "/account/calendar", session);
  expect(await screen.findByText(/Thursday, 20 August 2026/)).toBeVisible();
  expect(screen.getByText("Date unavailable")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Remove Meeting" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Remove Other" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Changed");
});

test("fails closed when the calendar cannot be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 503,
        json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable" } }),
      }),
    ),
  );
  renderWithProviders(<CalendarPage />, "/account/calendar", session);
  expect(
    await screen.findByText(/calendar is not available yet/i, undefined, { timeout: 4_000 }),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "Add to calendar" })).toBeDisabled();
});

test("renders nothing without an authenticated session", () => {
  const { container } = renderWithProviders(<CalendarPage />, "/account/calendar", null);
  expect(container).toBeEmptyDOMElement();
});
