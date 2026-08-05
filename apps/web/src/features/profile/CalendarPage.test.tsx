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

// The form seeds its weekday selection and date bounds from today, so these
// tests only hold on a fixed day. Only Date is faked: user-event drives its own
// timers and would stall against a fully faked clock.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-08-04T09:00:00Z"));
  resetQueryClientForTests();
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function requestBody(init?: RequestInit) {
  const body = typeof init?.body === "string" ? init.body : "{}";
  return JSON.parse(body) as CalendarMutation;
}

test("adds an all-day personal event through preview and command", async () => {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/calendar/me?")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ events: [] }) });
    }
    const body = requestBody(init);
    if (url.endsWith("/calendar/previews")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ request: body, previewHash: "a".repeat(64) }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ eventId: "new-event", version: 1, replayed: false }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<CalendarPage />, "/account/calendar", session);

  expect(await screen.findByText("No activity has been added.")).toBeVisible();
  await userEvent.clear(screen.getByLabelText("Last day"));
  await userEvent.type(screen.getByLabelText("Last day"), "2026-08-12");
  await userEvent.clear(screen.getByLabelText("First day"));
  await userEvent.type(screen.getByLabelText("First day"), "2026-08-15");
  await userEvent.selectOptions(screen.getByLabelText("Activity"), "training");
  await userEvent.selectOptions(screen.getByLabelText("Availability"), "partial");
  await userEvent.selectOptions(screen.getByLabelText("Team visibility"), "private");
  await userEvent.type(screen.getByLabelText("Note (optional)"), "Course attendance");
  await userEvent.click(screen.getByRole("button", { name: "Add to calendar" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/calendar/commands"))).toBe(
      true,
    ),
  );
  const previewCall = fetchMock.mock.calls.find(([url]) =>
    String(url).endsWith("/calendar/previews"),
  );
  const request = requestBody(previewCall?.[1]);
  expect(request.event).toMatchObject({
    ownerUserId: "user-1",
    source: "personal",
    activity: "training",
    note: "Course attendance",
    availability: "partial",
    privacy: "private",
  });
  expect(request.event.timing.allDayStart).toBe("2026-08-15");
  expect(request.event.timing.allDayEnd).not.toBe(request.event.timing.allDayStart);
});

test("creates a bounded weekly series with accessible weekday controls", async () => {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/calendar/me?"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ events: [] }) });
    const body = requestBody(init);
    if (url.endsWith("/calendar/previews"))
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ request: body, previewHash: "a".repeat(64) }),
      });
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ eventId: "series", version: 1, replayed: false }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<CalendarPage />, "/account/calendar", session);
  await screen.findByText("No activity has been added.");
  await userEvent.selectOptions(screen.getByLabelText("Frequency"), "weekly");
  expect(screen.getByRole("group", { name: "Repeat on" })).toBeVisible();
  await userEvent.click(screen.getByLabelText("Tuesday"));
  expect(screen.getByRole("button", { name: "Add to calendar" })).toBeDisabled();
  await userEvent.click(screen.getByLabelText("Monday"));
  await userEvent.click(screen.getByLabelText("Friday"));
  await userEvent.clear(screen.getByLabelText("Repeat until"));
  await userEvent.type(screen.getByLabelText("Repeat until"), "2026-09-01");
  await userEvent.click(screen.getByRole("button", { name: "Add to calendar" }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/calendar/previews"));
    expect(requestBody(call?.[1]).event.recurrence).toEqual({
      frequency: "weekly",
      interval: 1,
      until: "2026-09-01",
      weekdays: [0, 4],
    });
  });
});

test("confirms and updates the whole recurring series using its seed timing", async () => {
  const recurring = {
    ...event,
    seriesEventId: "event-1",
    occurrenceKey: "2026-08-17",
    seriesTiming: event.timing,
    timing: { ...event.timing, allDayStart: "2026-08-17", allDayEnd: "2026-08-18" },
    recurrence: { frequency: "weekly" as const, interval: 1, until: "2026-09-30", weekdays: [0] },
  };
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/calendar/me?"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ events: [recurring] }) });
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
  await userEvent.click(await screen.findByRole("button", { name: "Edit Training whole series" }));
  await userEvent.selectOptions(screen.getByLabelText("Activity"), "duty");
  await userEvent.click(screen.getByRole("button", { name: "Save whole series" }));
  expect(confirm).toHaveBeenCalledWith("Save changes to every occurrence in this series?");
  await waitFor(() => {
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/calendar/previews"));
    expect(requestBody(call?.[1])).toMatchObject({
      operation: "update",
      expectedVersion: 2,
      event: { eventId: "event-1", activity: "duty", timing: event.timing },
    });
  });
});

test("can decline whole-series edit and cancellation without sending a command", async () => {
  const recurring = {
    ...event,
    seriesEventId: "event-1",
    occurrenceKey: "2026-08-17",
    seriesTiming: event.timing,
    recurrence: {
      frequency: "daily" as const,
      interval: 2,
      until: "2026-08-30",
      weekdays: [],
    },
  };
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes("/calendar/me?") ? { events: [recurring] } : {}),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<CalendarPage />, "/account/calendar", session);

  await userEvent.click(await screen.findByRole("button", { name: "Edit Training whole series" }));
  expect(screen.getByRole("button", { name: "Discard changes" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Save whole series" }));
  await waitFor(() =>
    expect(confirm).toHaveBeenCalledWith("Save changes to every occurrence in this series?"),
  );
  await userEvent.click(screen.getByRole("button", { name: "Discard changes" }));
  await userEvent.click(screen.getByRole("button", { name: "Cancel Training series" }));
  await waitFor(() =>
    expect(confirm).toHaveBeenCalledWith("Cancel every occurrence in this series?"),
  );
  expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/calendar/previews"))).toBe(
    false,
  );
});

test("creates a daily interval and keeps the recurrence end within the series bound", async () => {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/calendar/me?"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ events: [] }) });
    const body = requestBody(init);
    if (url.endsWith("/calendar/previews"))
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ request: body, previewHash: "a".repeat(64) }),
      });
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ eventId: "daily", version: 1, replayed: false }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<CalendarPage />, "/account/calendar", session);
  await screen.findByText("No activity has been added.");
  await userEvent.selectOptions(screen.getByLabelText("Frequency"), "daily");
  await userEvent.clear(screen.getByLabelText("Repeat interval"));
  await userEvent.type(screen.getByLabelText("Repeat interval"), "3");
  await userEvent.clear(screen.getByLabelText("First day"));
  await userEvent.type(screen.getByLabelText("First day"), "2026-08-20");
  expect(screen.getByLabelText("Last day")).toHaveValue("2026-08-20");
  expect(screen.getByLabelText("Repeat until")).toHaveValue("2026-08-20");
  await userEvent.click(screen.getByRole("button", { name: "Add to calendar" }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/calendar/previews"));
    expect(requestBody(call?.[1]).event.recurrence).toEqual({
      frequency: "daily",
      interval: 3,
      until: "2026-08-20",
      weekdays: [],
    });
  });
});

test("edits a non-recurring timed event without asking for series confirmation", async () => {
  const timed = {
    ...event,
    timing: {
      timeZone: "Europe/London",
      startsAt: "2026-08-20T09:00:00Z",
      endsAt: "2026-08-20T10:00:00Z",
      allDayStart: null,
      allDayEnd: null,
    },
  };
  const confirm = vi.spyOn(window, "confirm");
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/calendar/me?"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ events: [timed] }) });
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
  await userEvent.click(await screen.findByRole("button", { name: "Edit Training whole series" }));
  expect(screen.getByLabelText("First day")).toHaveValue("2026-08-20");
  await userEvent.click(screen.getByRole("button", { name: "Save whole series" }));
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/calendar/commands"))).toBe(
      true,
    ),
  );
  expect(confirm).not.toHaveBeenCalled();
});

test("confirms and cancels a recurring series", async () => {
  const recurring = {
    ...event,
    seriesEventId: "event-1",
    occurrenceKey: "2026-08-17",
    seriesTiming: event.timing,
    timing: { ...event.timing, allDayStart: "2026-08-17", allDayEnd: "2026-08-18" },
    recurrence: { frequency: "daily" as const, interval: 1, until: "2026-08-30", weekdays: [] },
  };
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/calendar/me?"))
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ events: [recurring] }) });
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
  await userEvent.click(await screen.findByRole("button", { name: "Cancel Training series" }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/calendar/previews"));
    const request = requestBody(call?.[1]);
    expect(request).toMatchObject({
      operation: "cancel",
      expectedVersion: 2,
      event: { eventId: "event-1", timing: event.timing },
    });
    expect(request.event).not.toHaveProperty("occurrenceKey");
    expect(request.event).not.toHaveProperty("seriesEventId");
    expect(request.event).not.toHaveProperty("seriesTiming");
  });
});
