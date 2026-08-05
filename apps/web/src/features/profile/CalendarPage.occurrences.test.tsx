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

const recurring = {
  eventId: "series-1",
  seriesEventId: "series-1",
  occurrenceKey: "2026-08-17",
  ownerUserId: "user-1",
  source: "personal",
  activity: "training",
  timing: {
    timeZone: "Europe/London",
    startsAt: null,
    endsAt: null,
    allDayStart: "2026-08-17",
    allDayEnd: "2026-08-18",
  },
  seriesTiming: {
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
  recurrence: { frequency: "weekly", interval: 1, until: "2026-09-30", weekdays: [0] },
  managerScopeUnitId: null,
  status: "active",
  version: 2,
  createdAt: "2026-08-01T10:00:00Z",
  updatedAt: "2026-08-01T10:00:00Z",
  cancelledAt: null,
} as const;

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

function body(init?: RequestInit) {
  return JSON.parse(typeof init?.body === "string" ? init.body : "{}") as CalendarMutation;
}

function calendarFetch(events: object[]) {
  return vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/calendar/me?"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ events }) });
    const request = body(init);
    if (url.endsWith("/calendar/previews"))
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ request, previewHash: "a".repeat(64) }),
      });
    return Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          eventId: request.event?.eventId ?? "new",
          version: 3,
          replayed: false,
          futureEventId: request.futureEventId,
        }),
    });
  });
}

test("creates a timed personal event with an exact availability interval", async () => {
  const fetchMock = calendarFetch([]);
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<CalendarPage />, "/account/calendar", session);
  await screen.findByText("No activity has been added.");
  await userEvent.click(screen.getByLabelText("All day"));
  await userEvent.clear(screen.getByLabelText("First day"));
  await userEvent.type(screen.getByLabelText("First day"), "2026-08-20");
  await userEvent.clear(screen.getByLabelText("Start time"));
  await userEvent.type(screen.getByLabelText("Start time"), "13:15");
  await userEvent.clear(screen.getByLabelText("End time"));
  await userEvent.type(screen.getByLabelText("End time"), "15:45");
  await userEvent.click(screen.getByRole("button", { name: "Add to calendar" }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/calendar/previews"));
    const timing = body(call?.[1]).event.timing;
    expect(timing.allDayStart).toBeNull();
    expect(timing.startsAt).toContain("T");
    expect(timing.endsAt).not.toBe(timing.startsAt);
  });
});

test("updates one occurrence and splits this and future occurrences", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  const fetchMock = calendarFetch([recurring]);
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<CalendarPage />, "/account/calendar", session);

  await userEvent.click(
    await screen.findByRole("button", { name: "Edit Training this occurrence" }),
  );
  expect(screen.getByRole("heading", { name: "Edit this occurrence" })).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText("Activity"), "duty");
  await userEvent.click(screen.getByRole("button", { name: "Save this occurrence" }));
  await waitFor(() =>
    expect(confirm).toHaveBeenCalledWith("Save changes to this occurrence only?"),
  );
  await waitFor(() =>
    expect(previews(fetchMock)[0]).toMatchObject({
      operation: "update_occurrence",
      occurrenceKey: "2026-08-17",
      futureEventId: null,
      event: { activity: "duty", timing: recurring.timing },
    }),
  );

  await userEvent.click(
    screen.getByRole("button", { name: "Edit Training this and future occurrences" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Save this and future occurrences" }));
  await waitFor(() =>
    expect(previews(fetchMock)[1]).toMatchObject({
      operation: "update_future",
      occurrenceKey: "2026-08-17",
      event: { timing: recurring.timing },
    }),
  );
  expect(previews(fetchMock)[1]?.futureEventId).toMatch(/^[0-9a-f-]{36}$/);
});

test("cancels one occurrence without cancelling the series", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const fetchMock = calendarFetch([recurring]);
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<CalendarPage />, "/account/calendar", session);
  await userEvent.click(await screen.findByRole("button", { name: "Cancel Training occurrence" }));
  await waitFor(() =>
    expect(previews(fetchMock)[0]).toMatchObject({
      operation: "cancel_occurrence",
      occurrenceKey: "2026-08-17",
      futureEventId: null,
    }),
  );
});

function previews(fetchMock: ReturnType<typeof calendarFetch>) {
  return fetchMock.mock.calls
    .filter(([url]) => String(url).endsWith("/calendar/previews"))
    .map(([, init]) => body(init));
}
